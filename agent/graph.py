"""Agente investigador em LangGraph (seção 8.1).

Um grafo LangGraph é uma máquina de estados:
  - o ESTADO (Estado, abaixo) é um dicionário que passa de nó em nó;
  - cada NÓ é uma função que lê o estado e devolve as chaves que quer atualizar;
  - as ARESTAS CONDICIONAIS são funções que olham o estado e escolhem o próximo nó.

    carregar_contexto → planejar ─┬─(sem hipóteses)──────────────────────┐
                                  └→ gerar_sql → validar_sql ─(ok)→ executar_sql → analisar
                                        ↑            │(inválida)          │(erro)       │
                                        └────────────┴─(iteração < 3)─────┘   (precisa mais)
                                                                                      ↓
          redigir_dossie ←────────────────────────────────────────────────────────────┘
               ↓      ↑ (falhou 1ª vez)
          checar_numeros ──(ok ou 2ª falha)→ finalizar → FIM
    Qualquer falha do LLM → fallback (dossiê só com sinais, confiança BAIXA) → finalizar
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

import config as C
from agent import prompts as P
from agent.checagem import checar
from agent.llm import LLM
from agent.sql_guard import SQLRejeitada, validar
from agent.tools import (carregar_alerta, conectar_ro, consultas_canonicas, executar,
                         mascarar_texto, rede_de_contas, restringir_ate, schema_views)


class Estado(TypedDict, total=False):
    alerta_id: int
    alerta: dict
    rede: dict
    evidencias: list[dict]
    sql_executadas: list[dict]
    hipoteses: list[str]
    sql_atual: str
    erro_sql: str | None
    iteracao: int
    precisa_mais: bool
    dossie_llm: dict
    problemas: list[str]
    tentativas_redacao: int
    numero_inventado: bool
    falha: str | None
    fallback: bool
    texto_md: str
    confianca: str
    recomendacao: str
    profundidade: str  # "direta" (caso claro: só redige) ou "completa" (investiga)


def _nova_evidencia(evs: list[dict], **kw) -> dict:
    return {"id": f"E{len(evs)}", "achado": None, **kw}


def caso_claro(a: dict) -> bool:
    return (a["prob_modelo"] or 0) >= C.AGENTE_CLARO_PROB_MIN and \
        len(a["regras_disparadas"]) >= C.AGENTE_CLARO_REGRAS_MIN


def construir_grafo(llm: LLM, con: sqlite3.Connection, forcar_completa: bool = False):
    schema = schema_views(con)

    # ------------------------------------------------------------------ nós
    def carregar_contexto(s: Estado) -> Estado:
        a = carregar_alerta(con, s["alerta_id"])
        restringir_ate(con, a["janela_fim"])  # daqui em diante, o banco "para" no momento do saque
        evs = [P.contexto_como_evidencia(a)]
        sqls = []
        for chave, titulo, sql in consultas_canonicas(a):
            try:
                cols, linhas = executar(con, sql)
                evs.append(_nova_evidencia(evs, titulo=titulo, tipo="canonica", chave=chave,
                                           sql=sql, colunas=cols, linhas=linhas))
                sqls.append({"origem": "canonica", "sql": sql, "status": "ok", "linhas": len(linhas)})
            except (SQLRejeitada, sqlite3.Error) as e:  # não deveria acontecer: são consultas nossas
                sqls.append({"origem": "canonica", "sql": sql, "status": "erro", "motivo": str(e)})
        profundidade = "completa" if forcar_completa or not caso_claro(a) else "direta"
        return {"alerta": a, "rede": rede_de_contas(con, a["creator_id"], a["janela_fim"]),
                "evidencias": evs, "sql_executadas": sqls, "iteracao": 0, "tentativas_redacao": 0,
                "hipoteses": [], "falha": None, "fallback": False, "numero_inventado": False,
                "profundidade": profundidade}

    def planejar(s: Estado) -> Estado:
        try:
            plano = llm.estruturado(P.Plano, P.prompt_planejar(s["alerta"], s["evidencias"]))
            return {"hipoteses": [h for h in plano.hipoteses if h.strip()][:2]}
        except Exception as e:  # noqa: BLE001  (qualquer falha da API → fallback)
            return {"falha": f"planejar: {e}"}

    def gerar_sql(s: Estado) -> Estado:
        anteriores = [x["sql"] for x in s["sql_executadas"] if x["origem"] == "llm"]
        try:
            q = llm.estruturado(P.ConsultaSQL, P.prompt_gerar_sql(
                s["alerta"], s["hipoteses"][0], schema, s.get("erro_sql"), anteriores))
            return {"sql_atual": q.sql, "iteracao": s["iteracao"] + 1, "erro_sql": None}
        except Exception as e:  # noqa: BLE001
            return {"falha": f"gerar_sql: {e}", "iteracao": s["iteracao"] + 1}

    def validar_sql(s: Estado) -> Estado:
        try:
            validar(s["sql_atual"])
            return {"erro_sql": None}
        except SQLRejeitada as e:  # UC05: registra e devolve o erro ao LLM
            reg = {"origem": "llm", "sql": s["sql_atual"], "status": "rejeitada", "motivo": str(e),
                   "hipotese": s["hipoteses"][0]}
            return {"erro_sql": str(e), "sql_executadas": s["sql_executadas"] + [reg]}

    def executar_sql(s: Estado) -> Estado:
        sql, hip = s["sql_atual"], s["hipoteses"][0]
        try:
            cols, linhas = executar(con, sql)
        except (SQLRejeitada, sqlite3.Error) as e:
            reg = {"origem": "llm", "sql": sql, "status": "erro", "motivo": str(e), "hipotese": hip}
            return {"erro_sql": f"erro ao executar: {e}", "sql_executadas": s["sql_executadas"] + [reg]}
        ev = _nova_evidencia(s["evidencias"], titulo=hip, tipo="llm", sql=sql, colunas=cols, linhas=linhas)
        reg = {"origem": "llm", "sql": sql, "status": "ok", "linhas": len(linhas), "hipotese": hip}
        return {"evidencias": s["evidencias"] + [ev], "sql_executadas": s["sql_executadas"] + [reg]}

    def analisar(s: Estado) -> Estado:
        ev = s["evidencias"][-1]
        try:
            an = llm.estruturado(P.Analise, P.prompt_analisar(s["alerta"], s["hipoteses"][0], ev))
        except Exception as e:  # noqa: BLE001
            return {"falha": f"analisar: {e}"}
        evs = s["evidencias"][:-1] + [{**ev, "achado": an.achado}]
        return {"evidencias": evs, "hipoteses": s["hipoteses"][1:], "precisa_mais": an.precisa_mais}

    def redigir_dossie(s: Estado) -> Estado:
        n = s["tentativas_redacao"] + 1
        try:
            d = llm.estruturado(P.DossieLLM, P.prompt_redigir(
                s["alerta"], s["evidencias"], s["rede"], s.get("problemas") if n > 1 else None))
            return {"dossie_llm": d.model_dump(), "tentativas_redacao": n}
        except Exception as e:  # noqa: BLE001
            return {"falha": f"redigir_dossie: {e}", "tentativas_redacao": n}

    def checar_numeros(s: Estado) -> Estado:
        d = s["dossie_llm"]
        textos = [d["resumo"], d["justificativa"]] + [x["texto"] for x in d["afirmacoes"]]
        ids_ok = {s["alerta"]["creator_id"], *s["rede"]["creators_ligados"]}
        problemas = checar(textos, s["evidencias"], ids_ok)
        ids_ev = {e["id"] for e in s["evidencias"]}
        problemas += [f"evidência inexistente '{x['evidencia_id']}'"
                      for x in d["afirmacoes"] if x["evidencia_id"] not in ids_ev]
        return {"problemas": problemas,
                "numero_inventado": bool(problemas) and s["tentativas_redacao"] >= 2}

    def fallback(s: Estado) -> Estado:
        """Dossiê determinístico, só com os sinais e as consultas canônicas (seção 7)."""
        a = s["alerta"]
        afirm = []
        for e in s["evidencias"][1:]:
            if e.get("tipo") != "canonica" or not e["linhas"]:
                continue
            pares = ", ".join(f"{c} = {v}" for c, v in zip(e["colunas"], e["linhas"][0]) if not isinstance(v, str))
            afirm.append({"texto": f"{e['titulo']}: {pares or str(len(e['linhas'])) + ' registros'}",
                          "evidencia_id": e["id"]})
        regras = ", ".join(a["regras_disparadas"]) or "nenhuma regra (nota dada pelo modelo)"
        return {"fallback": True, "dossie_llm": {
            "resumo": (f"A investigação automática não pôde ser concluída. O saque foi retido por: {regras}. "
                       "Revise as evidências abaixo antes de decidir."),
            "afirmacoes": afirm, "recomendacao": "MANTER_RETIDO", "confianca": "BAIXA",
            "justificativa": "Dossiê gerado sem o agente de IA; confiança baixa por padrão."}}

    def finalizar(s: Estado) -> Estado:
        d = s["dossie_llm"]
        d = {**d, "resumo": mascarar_texto(d["resumo"]), "justificativa": mascarar_texto(d["justificativa"]),
             "afirmacoes": [{**x, "texto": mascarar_texto(x["texto"])} for x in d["afirmacoes"]]}
        confianca = "BAIXA" if (s.get("fallback") or s.get("numero_inventado")) else d["confianca"]
        s = {**s, "dossie_llm": d}
        return {"dossie_llm": d, "confianca": confianca, "recomendacao": d["recomendacao"],
                "texto_md": renderizar_md(s, confianca)}

    # ------------------------------------------------------------ roteamento
    def apos_contexto(s: Estado) -> str:
        return "planejar" if s["profundidade"] == "completa" else "redigir_dossie"

    def apos_planejar(s: Estado) -> str:
        if s.get("falha"):
            return "fallback"
        return "gerar_sql" if s["hipoteses"] else "redigir_dossie"

    def apos_gerar(s: Estado) -> str:
        return "fallback" if s.get("falha") else "validar_sql"

    def apos_validar(s: Estado) -> str:
        if s.get("erro_sql"):
            return "gerar_sql" if s["iteracao"] < C.AGENTE_MAX_ITERACOES else "redigir_dossie"
        return "executar_sql"

    def apos_executar(s: Estado) -> str:
        if s.get("erro_sql"):
            return "gerar_sql" if s["iteracao"] < C.AGENTE_MAX_ITERACOES else "redigir_dossie"
        return "analisar"

    def apos_analisar(s: Estado) -> str:
        if s.get("falha"):
            return "fallback"
        if s.get("precisa_mais") and s["hipoteses"] and s["iteracao"] < C.AGENTE_MAX_ITERACOES:
            return "gerar_sql"
        return "redigir_dossie"

    def apos_redigir(s: Estado) -> str:
        return "fallback" if s.get("falha") else "checar_numeros"

    def apos_checar(s: Estado) -> str:
        return "redigir_dossie" if s["problemas"] and s["tentativas_redacao"] < 2 else "finalizar"

    g = StateGraph(Estado)
    for nome, fn in [("carregar_contexto", carregar_contexto), ("planejar", planejar),
                     ("gerar_sql", gerar_sql), ("validar_sql", validar_sql),
                     ("executar_sql", executar_sql), ("analisar", analisar),
                     ("redigir_dossie", redigir_dossie), ("checar_numeros", checar_numeros),
                     ("fallback", fallback), ("finalizar", finalizar)]:
        g.add_node(nome, fn)
    g.add_edge(START, "carregar_contexto")
    g.add_conditional_edges("carregar_contexto", apos_contexto, ["planejar", "redigir_dossie"])
    g.add_conditional_edges("planejar", apos_planejar, ["gerar_sql", "redigir_dossie", "fallback"])
    g.add_conditional_edges("gerar_sql", apos_gerar, ["validar_sql", "fallback"])
    g.add_conditional_edges("validar_sql", apos_validar, ["executar_sql", "gerar_sql", "redigir_dossie"])
    g.add_conditional_edges("executar_sql", apos_executar, ["analisar", "gerar_sql", "redigir_dossie"])
    g.add_conditional_edges("analisar", apos_analisar, ["gerar_sql", "redigir_dossie", "fallback"])
    g.add_conditional_edges("redigir_dossie", apos_redigir, ["checar_numeros", "fallback"])
    g.add_conditional_edges("checar_numeros", apos_checar, ["redigir_dossie", "finalizar"])
    g.add_edge("fallback", "finalizar")
    g.add_edge("finalizar", END)
    return g.compile()


# ---------------------------------------------------------------------- markdown
_REC = {"MANTER_RETIDO": "Manter retido", "LIBERAR": "Liberar"}
_CONF = {"ALTA": "Alta", "MEDIA": "Média", "BAIXA": "Baixa"}


def renderizar_md(s: Estado, confianca: str) -> str:
    """O markdown é montado por TEMPLATE em Python, não pelo LLM: formato sempre igual na tela."""
    d, rede = s["dossie_llm"], s["rede"]
    linhas = [f"**Recomendação da IA:** {_REC[d['recomendacao']]} · **Confiança:** {_CONF[confianca]}", ""]
    if s.get("fallback"):
        linhas += ["> ⚠️ Investigação automática indisponível: dossiê gerado só com os sinais calculados.", ""]
    if s.get("numero_inventado"):
        linhas += ["> ⚠️ A IA citou valores que não foram confirmados pelas consultas. Confira as evidências.", ""]
    linhas += ["### Resumo", d["resumo"], "", "### Evidências"]
    linhas += [f"{i}. {x['texto']} `[{x['evidencia_id']}]`" for i, x in enumerate(d["afirmacoes"], 1)]
    linhas += ["", "### Contas ligadas"]
    if rede["creators_ligados"]:
        if rede["mesma_pix"]:
            linhas.append(f"- Mesma chave Pix: {', '.join(rede['mesma_pix'])}")
        if rede["mesmo_disp"]:
            linhas.append(f"- Mesmo dispositivo de login: {', '.join(rede['mesmo_disp'])}")
    else:
        linhas.append("- Nenhuma conta ligada por Pix ou dispositivo.")
    linhas += ["", "### Justificativa", d["justificativa"]]
    return "\n".join(linhas)


# ---------------------------------------------------------------------- execução
def investigar(alerta_id: int, llm: LLM, db_path=C.DB_PATH, gravar: bool = True,
               forcar_completa: bool = False) -> dict:
    """Roda o grafo para um alerta e (opcionalmente) grava o dossiê. Devolve o estado final."""
    con = conectar_ro(db_path)
    t0 = time.monotonic()
    chamadas0 = llm.chamadas
    try:
        grafo = construir_grafo(llm, con, forcar_completa)
        estado = grafo.invoke({"alerta_id": alerta_id}, {"recursion_limit": 60})
    finally:
        con.close()
    estado["duracao_seg"] = round(time.monotonic() - t0, 2)
    estado["chamadas_llm"] = llm.chamadas - chamadas0
    if gravar:
        salvar(estado, llm.nome, db_path)
    return estado


def salvar(s: dict, modelo: str, db_path=C.DB_PATH) -> int:
    d = s["dossie_llm"]
    def _mask(v):
        return mascarar_texto(v) if isinstance(v, str) else v
    evidencias = [{**e, "linhas": [[_mask(v) for v in l] for l in e.get("linhas", [])[:50]]}
                  for e in s["evidencias"]]
    detalhes = {"resumo": d["resumo"], "afirmacoes": d["afirmacoes"], "justificativa": d["justificativa"],
                "rede": s["rede"], "fallback": s.get("fallback", False), "falha": s.get("falha"),
                "numero_inventado": s.get("numero_inventado", False), "problemas": s.get("problemas", []),
                "tentativas_redacao": s.get("tentativas_redacao"), "iteracoes_sql": s.get("iteracao"),
                "modelo_llm": modelo, "chamadas_llm": s.get("chamadas_llm"),
                "profundidade": s.get("profundidade")}
    con = sqlite3.connect(db_path)
    try:
        con.execute("DELETE FROM dossies WHERE alerta_id = ?", (s["alerta_id"],))
        cur = con.execute("""INSERT INTO dossies (alerta_id, texto_md, evidencias, sql_executadas, confianca,
                             recomendacao, duracao_seg, detalhes, criado_em) VALUES (?,?,?,?,?,?,?,?,?)""",
                          (s["alerta_id"], s["texto_md"], P.dumps(evidencias), P.dumps(s["sql_executadas"]),
                           s["confianca"], s["recomendacao"], s.get("duracao_seg"), P.dumps(detalhes),
                           datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()
