"""Consultas e ações da interface. Mantém o SQL fora do arquivo de tela.

Relógio da demo: os dados terminam em 22/11/2026 23:59, então o "agora" da interface é
config.DATA_FIM (e não o relógio do computador). Prazo de retenção = pedido + 48 h.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

import pandas as pd

import config as C
from agent.prompts import rotulo

# Relógio da demo: quinta-feira, 26/11 às 15h. Os pedidos pendentes foram feitos entre 20 e 22/11
# (fim de semana), então o prazo de 48 horas ÚTEIS (doc de negócio, seção 5.3) está correndo.
AGORA_DEMO = datetime(2026, 11, 26, 15, 0)
URGENTE_HORAS_UTEIS = 9  # menos de 1 dia útil


def horas_uteis(inicio: datetime, fim: datetime) -> float:
    """Horas úteis (seg a sex, 9h às 18h) entre dois instantes."""
    total, t = 0.0, inicio
    while t < fim:
        prox = min(fim, (t + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0))
        if t.weekday() < 5 and 9 <= t.hour < 18:
            total += (prox - t).total_seconds() / 3600
        t = prox
    return total
# ---- Nomenclatura para o cliente: nenhum código interno (R1_, F2_, gabarito) aparece na tela ----
NOMES_REGRAS = {
    "R1_AUTOCOMPRA": "Autocompra",
    "R2_PIX_COMPARTILHADA": "Chave Pix compartilhada",
    "R3_ESTORNO_POS_LIB": "Reembolso após comissão paga",
    "R4_CLIQUE_RELAMPAGO": "Compra segundos após o clique",
    "R5_CARTAO_REPETIDO": "Cartão usado por várias pessoas",
    "R6_CHARGEBACK_ALTO": "Muitas contestações de cartão",
    "R7_DISP_COMPARTILHADO": "Dispositivo compartilhado",
}
NOMES_TIPOS = {
    "F1_AUTOCOMPRA": "Autocompra",
    "F2_REDE_PIX": "Rede de contas ligadas",
    "F3_COMPRA_ESTORNO": "Compra seguida de reembolso",
    "F4_CLIQUE_INFLADO": "Cliques artificiais",
    "F5_CARTAO_TESTADO": "Cartão de terceiros",
    "LEGITIMO_VIRAL": "Creator em alta (legítimo)",
    "NENHUMA": "Sem fraude",
}
CONF = {"ALTA": "alta", "MEDIA": "média", "BAIXA": "baixa"}
REC = {"MANTER_RETIDO": "Manter retido", "LIBERAR": "Liberar"}


def _feminino(palavra: str) -> str:
    """confirmados → confirmadas; associado → associada (só particípios -ado/-ido)."""
    import re
    return re.sub(r"([ai]d)o(s?)$", r"\1a\2", palavra)


def _sem_chargeback(texto: str) -> str:
    """A tela usa "contestação de cartão" (glossário), mas a IA escreve "chargeback".
    Como "contestação" é feminino, os particípios vizinhos precisam concordar:
    "2 chargebacks confirmados" → "2 contestações de cartão confirmadas"."""
    import re
    # particípio ANTES do número: "registrados 2 chargebacks" → "registradas 2 ..."
    texto = re.sub(r"\b(\w+[ai]dos?)(\s+\d+\s+chargebacks?)\b",
                   lambda m: _feminino(m.group(1)) + m.group(2), texto, flags=re.IGNORECASE)
    # particípio DEPOIS: "chargeback associado" → "... associada"
    texto = re.sub(r"\b(chargebacks?)(\s+)(\w+[ai]dos?)\b",
                   lambda m: m.group(1) + m.group(2) + _feminino(m.group(3)), texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bum chargeback\b", "uma contestação de cartão", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bchargebacks\b", "contestações de cartão", texto, flags=re.IGNORECASE)
    return re.sub(r"\bchargeback\b", "contestação de cartão", texto, flags=re.IGNORECASE)


def texto_cliente(texto: str, mapa_provas: dict[str, int], na_prova: bool = False) -> str:
    """Deixa o texto da IA na linguagem da tela.

    - "E4", "evidência E2" → "prova N" (ou "dados de origem" se a evidência não virou prova);
    - códigos de regra e nomes de coluna → nomes de cliente;
    - "chargeback" → "contestação de cartão" (mesmo termo dos chips de sinal);
    - "697,13 dias" → "697 dias" (ninguém conta idade de conta com centavos de dia);
    - na_prova=True: remove parênteses que só apontam para provas, como "(prova 1)" dentro
      da própria prova 1. Fora das provas a referência é útil e fica.
    A troca é só de exibição: o banco guarda o texto original, que é o que a checagem auditou.
    """
    import re

    def sub(m):
        n = mapa_provas.get(f"E{m.group(2)}")
        return f"prova {n}" if n else "dados de origem"
    texto = re.sub(r"\b(evid[eê]ncia\s+)?E(\d+)\b", sub, texto, flags=re.IGNORECASE)
    for cod, nome in NOMES_REGRAS.items():  # códigos de regra que a IA possa ter copiado
        texto = texto.replace(cod, nome.lower())
    # nomes de coluna em snake_case (ex.: total_vendas) viram texto legível
    texto = re.sub(r"\b[a-z]+(?:_[a-z0-9]+)+\b", lambda m: nome_coluna(m.group(0)).lower(), texto)
    texto = _sem_chargeback(texto)
    texto = re.sub(r"\b(\d+)[.,]\d+(\s+dias)\b", r"\1\2", texto)
    if na_prova:
        def so_ref(m):
            resto = re.sub(r"prova \d+|dados de origem|conforme|\b(?:a|e|os|as|nos|na)\b|[,\s]", "", m.group(1))
            return "" if not resto else m.group(0)
        texto = re.sub(r"\s*\(([^()]*)\)", so_ref, texto)
    return texto


def valor_feature(feature: str, v) -> str:
    """Formata o valor de um indicador do jeito que uma pessoa leria."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "sem informação"
    if feature.startswith(("score_", "prob_")):
        return f"{min(round(v * 100), 99):d}%"
    if feature.startswith(("taxa_", "pct_", "share_")) or feature == "conversao":
        return f"{round(v * 100):d}%"
    if feature == "mediana_seg_clique_compra":
        return f"{v:.0f} s"
    if feature == "idade_conta_dias":
        return f"{v:.0f} dias"
    if feature == "crescimento_vendas_7d":
        return f"{v:.1f}×".replace(".", ",")
    return f"{v:.0f}"


def nome_coluna(c: str) -> str:
    """total_vendas → Total vendas; usa os rótulos amigáveis das features quando existem."""
    r = rotulo(c)
    return r[0].upper() + r[1:] if r != c else c.replace("_", " ").capitalize()


def conectar() -> sqlite3.Connection:
    return sqlite3.connect(C.DB_PATH, check_same_thread=False)


def brl(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def sinais(regras: list[str], shap: list[dict]) -> list[str]:
    if regras:
        return [NOMES_REGRAS.get(r, r) for r in regras]
    pos = [s for s in shap if s["shap"] > 0]
    return [f"Padrão atípico: {rotulo(pos[0]['feature'])}"] if pos else ["Padrão atípico"]


def _alertas(con: sqlite3.Connection, where: str) -> pd.DataFrame:
    df = pd.read_sql(f"""
        SELECT a.alerta_id, a.creator_id, c.nome, s.saque_id, s.valor, s.solicitado_em, s.status,
               a.faixa_risco, a.score_final, a.prob_modelo, a.score_regras, a.regras_disparadas,
               a.shap_top, a.features, d.dossie_id, d.confianca, d.recomendacao, d.detalhes
        FROM alertas a
        JOIN saques s USING (saque_id)
        JOIN creators c USING (creator_id)
        LEFT JOIN dossies d ON d.alerta_id = a.alerta_id
        WHERE {where}
        ORDER BY a.score_final DESC, s.valor DESC""", con, parse_dates=["solicitado_em"])
    df["regras"] = df.regras_disparadas.apply(json.loads)
    df["shap"] = df.shap_top.apply(lambda s: json.loads(s) if s else [])
    df["sinais"] = [sinais(r, s) for r, s in zip(df.regras, df.shap)]
    decorridas = df.solicitado_em.apply(lambda t: horas_uteis(t.to_pydatetime(), AGORA_DEMO))
    df["horas_restantes"] = (C.PRAZO_RETENCAO_HORAS - decorridas).clip(lower=0).round(0)
    det = df.detalhes.apply(lambda d: json.loads(d) if isinstance(d, str) else {})
    df["fallback"] = det.apply(lambda d: d.get("fallback", False))
    df["numero_inventado"] = det.apply(lambda d: d.get("numero_inventado", False))
    df["profundidade"] = det.apply(lambda d: d.get("profundidade"))
    return df


def fila_principal(con) -> pd.DataFrame:
    return _alertas(con, "a.faixa_risco = 'ALTO' AND s.status = 'RETIDO'")


def monitoramento(con) -> pd.DataFrame:
    return _alertas(con, "a.faixa_risco = 'MEDIO'")


def decididos(con) -> pd.DataFrame:
    return pd.read_sql("""
        SELECT r.ts AS decidido_em, r.analista, a.creator_id, s.valor, r.decisao, d.recomendacao,
               r.comentario, a.alerta_id
        FROM revisoes r JOIN alertas a USING (alerta_id) JOIN saques s USING (saque_id)
        LEFT JOIN dossies d ON d.dossie_id = r.dossie_id
        ORDER BY r.revisao_id DESC""", con)


def alerta(con, alerta_id: int) -> dict:
    df = _alertas(con, f"a.alerta_id = {int(alerta_id)}")
    a = df.iloc[0].to_dict()
    a["features"] = json.loads(a["features"]) if a["features"] else {}
    a["detalhes"] = json.loads(a["detalhes"]) if isinstance(a["detalhes"], str) else None
    if a["dossie_id"] and not pd.isna(a["dossie_id"]):
        ev, sq = con.execute("SELECT evidencias, sql_executadas FROM dossies WHERE dossie_id = ?",
                             (int(a["dossie_id"]),)).fetchone()
        a["evidencias"] = {e["id"]: e for e in json.loads(ev)}
        a["sql_executadas"] = json.loads(sq)
    else:
        a["evidencias"], a["sql_executadas"] = {}, []
    return a


def rede_sem_dossie(creator_id: str, ate: str) -> dict:
    from agent.tools import conectar_ro, rede_de_contas
    con = conectar_ro()
    try:
        return rede_de_contas(con, creator_id, ate)
    finally:
        con.close()


def registrar_decisao(alerta_id: int, dossie_id: int | None, analista: str, decisao: str, comentario: str) -> None:
    """Regras de negócio 4 e 5: só o humano decide, e toda decisão tem comentário e fica registrada."""
    if not comentario.strip():
        raise ValueError("comentário obrigatório")
    con = conectar()
    try:
        con.execute("""INSERT INTO revisoes (dossie_id, alerta_id, analista, decisao, comentario, ts)
                       VALUES (?,?,?,?,?,?)""",
                    (dossie_id, alerta_id, analista.strip() or "Analista", decisao, comentario.strip(),
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        novo = "APROVADO" if decisao == "LIBERAR" else "NEGADO"
        con.execute("UPDATE saques SET status = ? WHERE saque_id = (SELECT saque_id FROM alertas WHERE alerta_id = ?)",
                    (novo, alerta_id))
        con.commit()
    finally:
        con.close()


def resetar_demo() -> None:
    """Desfaz todas as decisões: os saques ALTO voltam a RETIDO."""
    con = conectar()
    try:
        con.execute("DELETE FROM revisoes")
        con.execute("""UPDATE saques SET status = 'RETIDO'
                       WHERE saque_id IN (SELECT saque_id FROM alertas WHERE faixa_risco = 'ALTO')""")
        con.commit()
    finally:
        con.close()


# ------------------------------------------------------------------ métricas (modo demo)
def metricas(con) -> dict:
    FRAUDE = C.FRAUDE
    d = pd.read_sql("""SELECT a.faixa_risco, a.score_regras, a.prob_modelo, a.regras_disparadas, s.valor,
                              s.status, g.fraude_tipo, COALESCE(g.observacao, '') AS obs
                       FROM alertas a JOIN saques s USING (saque_id) JOIN gabarito g USING (creator_id)""", con)
    d["fraude"] = d.fraude_tipo.isin(FRAUDE)
    alto = d.faixa_risco.eq("ALTO")
    tp, fp, fn = int((alto & d.fraude).sum()), int((alto & ~d.fraude).sum()), int((~alto & d.fraude).sum())
    rev = pd.read_sql("SELECT decisao FROM revisoes", con)
    dos = pd.read_sql("SELECT duracao_seg, detalhes FROM dossies", con)
    det = dos.detalhes.apply(lambda x: json.loads(x) if isinstance(x, str) else {})
    ok = dos[~det.apply(lambda x: x.get("fallback", False))]
    num_inv = det[~det.apply(lambda x: x.get("fallback", False))].apply(lambda x: x.get("numero_inventado", False))
    # Só fraudes confirmadas: "retido sem necessidade" não é tipo de fraude e já tem cartão próprio.
    por_tipo = (d[alto & d.fraude].assign(tipo=lambda x: x.fraude_tipo.map(NOMES_TIPOS))
                .groupby("tipo").size().sort_values(ascending=False))
    ia = pd.read_sql("""SELECT d.recomendacao, d.detalhes, g.fraude_tipo FROM dossies d
                        JOIN alertas a USING (alerta_id) JOIN gabarito g USING (creator_id)""", con)
    ia = ia[~ia.detalhes.apply(lambda x: json.loads(x).get("fallback", False) if isinstance(x, str) else False)]
    ia_fraude = ia.fraude_tipo.isin(FRAUDE)
    return {
        "ia_reteve_fraude": int((ia_fraude & ia.recomendacao.eq("MANTER_RETIDO")).sum()),
        "ia_fraudes": int(ia_fraude.sum()),
        "ia_liberou_fraude": int((ia_fraude & ia.recomendacao.eq("LIBERAR")).sum()),
        "ia_liberou_legit": int((~ia_fraude & ia.recomendacao.eq("LIBERAR")).sum()),
        "ia_legitimos": int((~ia_fraude).sum()),
        "virais_total": int(d.fraude_tipo.eq("LEGITIMO_VIRAL").sum()),
        "avaliados": len(d), "retidos": int(alto.sum()), "tp": tp, "fp": fp, "fn": fn,
        "precisao": tp / max(1, tp + fp), "recall": tp / max(1, tp + fn),
        "rs_fraude": float(d.loc[alto & d.fraude, "valor"].sum()),
        "rs_legitimo": float(d.loc[alto & ~d.fraude, "valor"].sum()),
        "virais_retidos": int((alto & d.fraude_tipo.eq("LEGITIMO_VIRAL")).sum()),
        "decisoes": len(rev), "liberados": int(rev.decisao.eq("LIBERAR").sum()),
        "negados": int(rev.decisao.eq("NEGAR").sum()),
        "dossies": len(dos), "dossies_ok": len(ok),
        "tempo_medio": float(ok.duracao_seg.mean()) if len(ok) else None,
        "pct_numero_inventado": float(num_inv.mean()) if len(num_inv) else None,
        "por_tipo": por_tipo,
    }
