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

AGORA_DEMO = C.DATA_FIM
NOMES_REGRAS = {
    "R1_AUTOCOMPRA": "Autocompra", "R2_PIX_COMPARTILHADA": "Pix compartilhada",
    "R3_ESTORNO_POS_LIB": "Estorno pós-liberação", "R4_CLIQUE_RELAMPAGO": "Clique relâmpago",
    "R5_CARTAO_REPETIDO": "Cartão repetido", "R6_CHARGEBACK_ALTO": "Chargeback alto",
    "R7_DISP_COMPARTILHADO": "Dispositivo compartilhado",
}
CONF = {"ALTA": "Alta", "MEDIA": "Média", "BAIXA": "Baixa"}
REC = {"MANTER_RETIDO": "Manter retido", "LIBERAR": "Liberar"}


def conectar() -> sqlite3.Connection:
    return sqlite3.connect(C.DB_PATH, check_same_thread=False)


def brl(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def sinais(regras: list[str], shap: list[dict]) -> str:
    if regras:
        return ", ".join(NOMES_REGRAS.get(r, r) for r in regras)
    pos = [s for s in shap if s["shap"] > 0]
    return f"Modelo: {rotulo(pos[0]['feature'])}" if pos else "Modelo"


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
    prazo = df.solicitado_em + timedelta(hours=C.PRAZO_RETENCAO_HORAS)
    df["horas_restantes"] = ((prazo - AGORA_DEMO).dt.total_seconds() / 3600).clip(lower=0).round(0)
    det = df.detalhes.apply(lambda d: json.loads(d) if isinstance(d, str) else {})
    df["fallback"] = det.apply(lambda d: d.get("fallback", False))
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
    por_tipo = (d[alto].assign(tipo=lambda x: x.fraude_tipo.where(x.fraude, "Legítimo (falso alarme)"))
                .groupby("tipo").size().sort_values(ascending=False))
    return {
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
