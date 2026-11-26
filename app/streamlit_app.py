"""Sentinela · interface do analista de Operações (Streamlit).

Rodar localmente:  streamlit run app/streamlit_app.py

Telas: Fila de análise → Caso (relatório, provas, fatores, rede, decisão) · Em observação · Decididos · Resultados
Identidade visual e componentes HTML ficam em app/ui.py; consultas e nomenclatura em app/dados.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import config as C  # noqa: E402
from agent.prompts import rotulo  # noqa: E402
from app import dados as D  # noqa: E402
from app import ui as U  # noqa: E402

st.set_page_config(page_title="Sentinela · YouShop", page_icon=str(Path(__file__).parent / "logo.png"),
                   layout="wide", initial_sidebar_state="collapsed")
st.html(U.CSS)

POR_PAGINA = 12
st.session_state.setdefault("analista", "Marina Souza")
st.session_state.setdefault("limite", POR_PAGINA)


# ---------------------------------------------------------------------------- dados (cache)
@st.cache_data(ttl=60)
def _fila():
    return D.fila_principal(D.conectar())


@st.cache_data(ttl=60)
def _monit():
    return D.monitoramento(D.conectar())


@st.cache_data(ttl=60)
def _decididos():
    return D.decididos(D.conectar())


@st.cache_data(ttl=60)
def _metricas():
    return D.metricas(D.conectar())


def _limpar_cache():
    for f in (_fila, _monit, _decididos, _metricas):
        f.clear()


def _relatorio(r) -> str | None:
    if pd.isna(r.dossie_id):
        return None
    return "parcial" if (r.fallback or r.numero_inventado) else "pronto"


# ---------------------------------------------------------------------------- topo
c_top, c_aj = st.columns([6, 1], vertical_alignment="center")
with c_top:
    st.html(U.topo(st.session_state["analista"], f"Hoje · {D.AGORA_DEMO:%d/%m/%Y %H:%M}"))
with c_aj:
    with st.popover("Ajustes", icon=":material/tune:", width="stretch"):
        nome = st.text_input("Analista responsável", value=st.session_state["analista"])
        if nome.strip() and nome != st.session_state["analista"]:
            st.session_state["analista"] = nome.strip()
            st.rerun()
        st.caption("Ambiente de demonstração com dados fictícios.")
        if st.button("Reiniciar demonstração", icon=":material/restart_alt:", width="stretch"):
            D.resetar_demo()
            _limpar_cache()
            st.session_state.pop("aberto", None)
            st.rerun()


# ---------------------------------------------------------------------------- caso
def grafo_rede(rede: dict, investigado: str):
    L = ['graph { rankdir=LR; bgcolor="transparent"; pad=0.2; nodesep=0.35; ranksep=0.55;',
         'node [fontname="Helvetica", fontsize=11, penwidth=1.4]; edge [color="#A9B4C4", penwidth=1.2];']
    for n in rede["nos"]:
        if n["tipo"] == "creator":
            if n["id"] == investigado:
                L.append(f'"{n["id"]}" [label="{n["id"]}", shape=box, style="filled,rounded", fillcolor="{U.NAVY}", '
                         f'fontcolor="white", color="{U.NAVY}"];')
            else:
                L.append(f'"{n["id"]}" [shape=box, style="filled,rounded", fillcolor="white", fontcolor="{U.NAVY}", '
                         f'color="{U.NAVY}"];')
        else:
            pix = n["tipo"] == "pix"
            rot = ("Chave Pix" if pix else "Dispositivo") + "\\n" + n["rotulo"].split(" ", 1)[-1]
            fill, cor = (U.LIME_TINT, U.LIME) if pix else (U.SUBTLE, "#C9D3E0")
            L.append(f'"{n["id"]}" [label="{rot}", shape=ellipse, style=filled, fillcolor="{fill}", color="{cor}", '
                     f'fontcolor="{U.NAVY}"];')
    L += [f'"{a}" -- "{b}";' for a, b in rede["arestas"]] + ["}"]
    st.graphviz_chart("\n".join(L), width="stretch")
    partes = []
    if rede.get("mesma_pix"):
        partes.append(f"{len(rede['mesma_pix']) + 1} contas recebem na mesma chave Pix")
    if rede.get("mesmo_disp"):
        partes.append(f"{len(rede['mesmo_disp'])} acessam pelo mesmo dispositivo")
    st.caption(" · ".join(partes))


def dados_origem(ev: dict):
    if ev.get("linhas"):
        df = pd.DataFrame(ev["linhas"], columns=[D.nome_coluna(c) for c in ev["colunas"]])
        if ev.get("tipo") == "contexto":
            df = pd.DataFrame([{"Indicador": D.nome_coluna(k),
                                "Valor": D.brl(v) if k == "valor_saque" else D.valor_feature(k, v)}
                               for k, v in ev["linhas"]])
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.caption("A consulta não retornou registros.")
    if ev.get("achado"):
        st.caption(f"Leitura da análise: {ev['achado']}")
    if ev.get("sql"):
        st.caption("Consulta técnica utilizada")
        st.code(ev["sql"], language="sql")
    else:
        st.caption("Indicadores calculados automaticamente pelo Sentinela.")


MENSAGENS_CREATOR = {
    "LIBERAR": "Análise concluída. Seu saque foi liberado e será transferido para a sua conta.",
    "NEGAR": "Seu saque não foi aprovado porque identificamos vendas com indício de irregularidade. "
             "Se discordar, você pode contestar a decisão pelo seu painel.",
}


def tela_caso(alerta_id: int):
    a = D.alerta(D.conectar(), alerta_id)
    det = a["detalhes"]
    if st.button("Voltar para a fila", icon=":material/arrow_back:", type="tertiary"):
        st.session_state.pop("aberto", None)
        st.rerun()

    profundidade = (det or {}).get("profundidade")
    meta = [("Saque", D.brl(a["valor"])), ("Pedido em", f"{a['solicitado_em']:%d/%m às %H:%M}"),
            ("Prazo restante", f"{int(a['horas_restantes'])} h úteis")]
    st.html(U.cabecalho_caso(a["nome"], a["creator_id"], meta, a["score_final"], a["prob_modelo"], a["score_regras"]))

    if det:
        st.html(U.fatos([
            U.fato("Recomendação da análise", U.recomendacao(a["recomendacao"], a["confianca"]), "shield-check"),
            U.fato("Sinais identificados", f'<div class="sx-tags" style="margin-top:8px">{U.tags(a["sinais"])}</div>',
                   "eye", 60),
        ], colunas="1.2fr 1fr"))
        if det.get("fallback"):
            st.html(U.aviso("A análise automática não pôde ser concluída. O relatório mostra apenas os sinais calculados; "
                            "revise os dados de origem antes de decidir."))
        if det.get("numero_inventado"):
            st.html(U.aviso("Alguns valores citados no relatório não foram confirmados pelos dados de origem. "
                            "Confira as provas antes de decidir."))
    else:
        st.html(U.aviso("O relatório deste caso ainda está em preparação. Abaixo, os sinais e indicadores já calculados."))

    esq, dir_ = st.columns([1.55, 1], gap="large")
    with esq:
        if det:
            mapa = {}
            for i, x in enumerate(det["afirmacoes"], 1):
                mapa.setdefault(x["evidencia_id"], i)
            st.html(U.titulo("Resumo"))
            st.html(U.cartao(f'<p>{U.esc(D.texto_cliente(det["resumo"], mapa))}</p>'))
            st.html(U.titulo("Provas", f"{len(det['afirmacoes'])} itens · cada um com os dados de origem"))
            for i, x in enumerate(det["afirmacoes"], 1):
                with st.container(key=f"box_prova_{i}"):
                    st.html(U.prova(i, D.texto_cliente(x["texto"], mapa, na_prova=True)))
                    ev = a["evidencias"].get(x["evidencia_id"])
                    if ev:
                        with st.expander("Ver dados de origem", icon=":material/database:"):
                            dados_origem(ev)
            st.html(U.titulo("Justificativa"))
            st.html(U.cartao(f'<p>{U.esc(D.texto_cliente(det["justificativa"], mapa))}</p>'))
            llm_sql = [s for s in a["sql_executadas"] if s["origem"] == "llm"]
            if llm_sql:
                tipo = ("análise aprofundada: caso ambíguo, a IA levantou hipóteses e consultou os dados"
                        if profundidade == "completa" else "análise rápida: sinais fortes, consultas padrão bastaram")
                st.html(U.titulo("Auditoria", tipo))
                with st.expander(f"{len(llm_sql)} consultas registradas", icon=":material/fact_check:"):
                    for s in llm_sql:
                        situacao = {"ok": "Executada", "rejeitada": "Bloqueada pela política de segurança",
                                    "erro": "Falhou ao executar"}[s["status"]]
                        st.markdown(f"**{situacao}** · {s.get('hipotese', '')}")
                        if s.get("motivo"):
                            st.caption(f"Motivo: {s['motivo']}")
                        st.code(s["sql"], language="sql")
        else:
            st.html(U.titulo("Indicadores do creator"))
            st.dataframe(pd.DataFrame([{"Indicador": D.nome_coluna(k), "Valor": "sem informação" if v is None else v}
                                       for k, v in a["features"].items()]), hide_index=True, width="stretch")

    with dir_:
        st.html(U.titulo("O que mais pesou na avaliação"))
        mx = max((abs(s["shap"]) for s in a["shap"]), default=1) or 1
        itens = [{"rotulo": rotulo(s["feature"])[0].upper() + rotulo(s["feature"])[1:],
                  "valor_txt": D.valor_feature(s["feature"], s["valor"]),
                  "impacto": abs(s["shap"]) / mx, "aumenta": s["shap"] > 0} for s in a["shap"]]
        st.html(U.cartao(U.barras_fatores(itens)))

        st.html(U.titulo("Rede de contas"))
        rede = det["rede"] if det else D.rede_sem_dossie(a["creator_id"], f"{a['solicitado_em']:%Y-%m-%d %H:%M:%S}")
        if rede and rede.get("creators_ligados"):
            with st.container(key="box_rede"):
                grafo_rede(rede, a["creator_id"])
        else:
            st.html('<p class="sx-empty">Nenhuma conta ligada por chave Pix ou dispositivo de acesso.</p>')

        st.html(U.titulo("Decisão"))
        with st.container(key="box_decisao"):
            if a["status"] != "RETIDO":
                txt = "liberado" if a["status"] == "APROVADO" else "negado"
                st.html(f'<span class="sx-pill {"free" if a["status"] == "APROVADO" else "hold"}">'
                        f'{U.icon("check", 14)}Saque {txt}</span>')
            else:
                decisao = st.radio("Sua decisão", ["LIBERAR", "NEGAR"], index=None, horizontal=True,
                                   format_func=lambda x: "Liberar saque" if x == "LIBERAR" else "Negar saque")
                comentario = st.text_area("Comentário", placeholder="Descreva o que fundamentou a sua decisão",
                                          help="Obrigatório. Toda decisão fica registrada para auditoria.")
                if decisao:
                    st.html(f'<div class="sx-msg"><small>Mensagem que o creator vai receber</small>'
                            f'{U.esc(MENSAGENS_CREATOR[decisao])}</div>')
                if st.button("Registrar decisão", type="primary", icon=":material/check:", width="stretch"):
                    if not decisao:
                        st.error("Escolha se o saque será liberado ou negado.")
                    elif not comentario.strip():
                        st.error("O comentário é obrigatório: toda decisão fica registrada para auditoria.")
                    else:
                        dossie_id = None if pd.isna(a["dossie_id"]) else int(a["dossie_id"])
                        D.registrar_decisao(alerta_id, dossie_id, st.session_state["analista"], decisao, comentario)
                        _limpar_cache()
                        st.session_state.pop("aberto", None)
                        st.toast("Decisão registrada.", icon=":material/check_circle:")
                        st.rerun()


# ---------------------------------------------------------------------------- páginas
def lista(df: pd.DataFrame, prefixo: str, com_botao: bool, observacao: bool = False):
    atrasos = "".join(f".st-key-{prefixo}_{r.alerta_id}{{animation-delay:{min(i, 14) * 35}ms}}"
                      for i, r in enumerate(df.itertuples()))
    st.html(f"<style>{atrasos}</style>")
    for r in df.itertuples():
        dados = {"risco": r.score_final, "nome": r.nome, "creator_id": r.creator_id, "sinais": r.sinais,
                 "so_modelo": not r.regras, "valor": D.brl(r.valor),
                 "horas": None if observacao else r.horas_restantes,
                 "relatorio": "obs" if observacao else _relatorio(r), "confianca": D.CONF.get(r.confianca, ""),
                 "urgente": D.URGENTE_HORAS_UTEIS}
        with st.container(key=f"{prefixo}_{r.alerta_id}"):
            if com_botao:
                c1, c2 = st.columns([7.4, 1], vertical_alignment="center")
                with c1:
                    st.html(U.linha_fila(dados))
                with c2:
                    if st.button("Analisar", key=f"abrir_{r.alerta_id}", icon=":material/arrow_forward:",
                                 width="stretch"):
                        st.session_state["aberto"] = int(r.alerta_id)
                        st.rerun()
            else:
                st.html(U.linha_fila(dados))


def pagina_fila():
    df = _fila()
    prontos = int(df.dossie_id.notna().sum())
    st.html(U.kpis([
        U.kpi("Saques em análise", str(len(df)), "aguardando decisão do analista", "shield"),
        U.kpi("Valor em análise", D.brl(df.valor.sum()), "retido até a decisão", "wallet", atraso=60),
        U.kpi("Prazo próximo do fim", str(int(df.horas_restantes.lt(D.URGENTE_HORAS_UTEIS).sum())), "vencem em menos de 1 dia útil",
              "hourglass", atraso=120),
        U.kpi("Relatórios prontos", f"{prontos} de {len(df)}", "investigações concluídas", "file",
              barra=prontos / max(1, len(df)), cor_barra=U.LIME, atraso=180),
    ]))

    f1, f2, f3, f4 = st.columns([2.2, 1, 1.2, 1.2], vertical_alignment="bottom")
    sinais = f1.multiselect("Sinais", list(D.NOMES_REGRAS.values()), placeholder="Todos os sinais")
    faixas = {"Qualquer valor": 0, "A partir de R$ 100": 100, "A partir de R$ 500": 500, "A partir de R$ 1.000": 1000}
    vmin = faixas[f2.selectbox("Valor do saque", list(faixas))]
    busca = f3.text_input("Buscar creator", placeholder="Nome ou código")
    ordem = f4.selectbox("Ordenar por", ["Maior risco", "Prazo mais curto", "Maior valor"])

    if sinais:
        df = df[df.sinais.apply(lambda s: any(x in s for x in sinais))]
    df = df[df.valor >= vmin]
    if busca.strip():
        b = busca.strip()
        df = df[df.creator_id.str.contains(b, case=False) | df.nome.str.contains(b, case=False)]
    # Critério de desempate: muitos casos empatam em 99%, então o segundo critério decide a ordem.
    # Sem ele, um caso com 6 h de prazo podia ficar atrás de outro com 15 h.
    chaves = {"Maior risco": (["risco_tela", "horas_restantes", "valor"], [False, True, False]),
              "Prazo mais curto": (["horas_restantes", "risco_tela"], [True, False]),
              "Maior valor": (["valor", "risco_tela"], [False, False])}[ordem]
    df = df.assign(risco_tela=df.score_final.clip(upper=0.99).round(2))  # empata como a tela mostra (99%)
    df = df.sort_values(chaves[0], ascending=chaves[1]).reset_index(drop=True)

    st.html(U.titulo("Fila de análise", f"{len(df)} casos · ordenados por {ordem.lower()}"
                       + (" e, no empate, prazo" if ordem == "Maior risco" else "")))
    if df.empty:
        st.html(U.aviso("Nenhum caso com esses filtros.", "info"))
        return
    lim = st.session_state["limite"]
    lista(df.head(lim), "row", com_botao=True)
    if len(df) > lim:
        if st.button(f"Mostrar mais {min(POR_PAGINA, len(df) - lim)} casos", icon=":material/expand_more:",
                     type="tertiary"):
            st.session_state["limite"] = lim + POR_PAGINA
            st.rerun()


def pagina_observacao():
    df = _monit()
    st.html(U.aviso("Casos de <b>risco médio</b>: o saque foi pago normalmente e o creator segue em observação. "
                    "O próximo pedido de saque será avaliado com atenção redobrada.", "info"))
    st.html(U.titulo("Em observação", f"{len(df)} creators"))
    lista(df, "obs", com_botao=False, observacao=True)


def pagina_decididos():
    df = _decididos()
    st.html(U.titulo("Decisões registradas", "histórico auditável: quem decidiu, quando e por quê"))
    if df.empty:
        st.html(U.aviso("Nenhuma decisão registrada ainda. Abra um caso na fila de análise para decidir.", "info"))
        return
    linhas = []
    for r in df.itertuples():
        liberou = r.decisao == "LIBERAR"
        pill = (f'<span class="sx-pill {"free" if liberou else "hold"}" style="font-size:.78rem">'
                f'{"Liberado" if liberou else "Negado"}</span>')
        rec = D.REC.get(r.recomendacao, "—") if isinstance(r.recomendacao, str) else "—"
        if rec == "—":
            concord = "—"
        else:
            concord = "Seguiu a recomendação" if (rec == "Liberar") == liberou else "Divergiu da recomendação"
        linhas.append([f"{pd.to_datetime(r.decidido_em):%d/%m %H:%M}", f"<b>{U.esc(r.creator_id)}</b>",
                       D.brl(r.valor), pill, U.esc(rec), U.esc(concord), U.esc(r.analista), U.esc(r.comentario)])
    st.html(U.tabela(["Quando", "Creator", "Saque", "Decisão", "Recomendação", "Análise × analista",
                      "Analista", "Comentário"], linhas))


def pagina_resultados():
    m = _metricas()
    # O argumento central para manter o humano no circuito abre a tela, dito com todas as letras.
    st.html(U.aviso(f'<b>Seguida sem revisão, a análise automática teria liberado {m["ia_liberou_fraude"]} '
                    f'fraudadores.</b> Por isso ela só recomenda: a decisão final é sempre do analista, que confere '
                    f'os dados de origem de cada prova.'))
    st.html(U.titulo("Proteção", f"{m['avaliados']:,} saques avaliados".replace(",", ".")))
    st.html(U.kpis([
        U.kpi("Fraudes identificadas", U.pct(m["recall"]), f"{m['tp']} de {m['tp'] + m['fn']} casos · meta 85%",
              "target", barra=m["recall"], cor_barra=U.NAVY, meta=0.85),
        U.kpi("Acerto nas retenções", U.pct(m["precisao"]), f"{m['tp']} de {m['retidos']} retidos · meta 80%",
              "shield-check", barra=m["precisao"], cor_barra=U.NAVY, meta=0.80, atraso=60),
        U.kpi("Valor protegido", D.brl(m["rs_fraude"]), "comissões de fraude que não saíram", "wallet", atraso=120),
        U.kpi("Retidos sem necessidade", str(m["fp"]), f"{D.brl(m['rs_legitimo'])} de creators legítimos",
              "users", atraso=180),
    ]))
    preservados = m["virais_total"] - m["virais_retidos"]
    cards = [U.kpi("Creators em alta preservados", f"{preservados} de {m['virais_total']}",
                   "crescimento rápido não é tratado como suspeita", "trend",
                   barra=preservados / max(1, m["virais_total"]), cor_barra=U.LIME)]
    if m["pct_numero_inventado"] is not None:
        conf = 1 - m["pct_numero_inventado"]
        cards.append(U.kpi("Relatórios com dados conferidos", U.pct(conf), "todo número citado vem dos dados · meta 95%",
                           "file", barra=conf, cor_barra=U.LIME, meta=0.95, atraso=60))
    if m["tempo_medio"] is not None:
        # sem barra: aqui menor é melhor, e uma barra curta parecia resultado ruim
        cards.append(U.kpi("Tempo médio de investigação", f"{m['tempo_medio']:.0f} s", "por caso · meta abaixo de 60 s",
                           "bolt", atraso=120))
    if m["decisoes"]:  # na demo zerada o cartão só mostraria "0"
        cards.append(U.kpi("Decisões registradas", str(m["decisoes"]),
                           f"{m['liberados']} liberadas · {m['negados']} negadas", "check", atraso=180))
    st.html(U.titulo("Qualidade da análise"))
    st.html(U.kpis(cards))

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.html(U.titulo("Fraudes retidas por tipo", f"{m['tp']} casos"))
        st.html(U.cartao(U.barras_simples(list(m["por_tipo"].items()))))
    with c2:
        st.html(U.titulo("Recomendações da análise automática"))
        f, lg = m["ia_fraudes"], m["ia_legitimos"]
        corpo = U.barras_proporcao([
            ("Fraudes com recomendação de manter retido", m["ia_reteve_fraude"], f),
            ("Retidos sem necessidade com recomendação de liberar", m["ia_liberou_legit"], lg),
        ], cor=U.LIME)
        st.html(U.cartao(corpo))


# ---------------------------------------------------------------------------- roteamento
if not C.DB_PATH.exists():
    st.error("Base de dados não encontrada. Gere a base com `python -m data.generator`.")
    st.stop()

if "aberto" in st.session_state:
    tela_caso(st.session_state["aberto"])
else:
    paginas = {"fila": ":material/inbox: Fila de análise", "obs": ":material/visibility: Em observação",
               "dec": ":material/task_alt: Decididos", "res": ":material/insights: Resultados"}
    escolha = st.segmented_control("Navegação", list(paginas), format_func=paginas.get, default="fila",
                                   key="nav", label_visibility="collapsed")
    {"fila": pagina_fila, "obs": pagina_observacao, "dec": pagina_decididos,
     "res": pagina_resultados}[escolha or "fila"]()
