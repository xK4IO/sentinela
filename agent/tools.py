"""Ferramentas determinísticas do agente (sem LLM).

- conectar_ro / executar: toda SQL passa pelo validador E roda numa conexão read-only.
- carregar_alerta: alerta + features + regras + SHAP + saque.
- consultas_canonicas: SQL fixa por regra/sinal. Garante as evidências principais mesmo
  se o LLM falhar, e cada número do dossiê fica com a "prova" ao lado.
- rede_de_contas: grafo creator ↔ Pix ↔ dispositivo (alimenta dossiê e tela).
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import config as C
from agent.sql_guard import VIEWS_PERMITIDAS, validar

FMT = "%Y-%m-%d %H:%M:%S"
TIMEOUT_SQL_SEG = 5


def conectar_ro(db_path: Path = C.DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True, check_same_thread=False)
    con.execute("PRAGMA query_only = ON")
    return con


def restringir_ate(con: sqlite3.Connection, fim: str) -> None:
    """Corte point-in-time: cria views TEMPORÁRIAS com os mesmos nomes vw_*, mostrando o
    banco como ele era no momento do saque. O SQLite resolve nomes sem prefixo procurando
    primeiro no schema temp, e o validador proíbe 'main.', então nem o LLM nem as consultas
    canônicas conseguem enxergar o futuro, mesmo que ignorem o prompt."""
    datetime.strptime(fim, FMT)  # só aceita data válida (evita injeção na string)
    f = f"'{fim}'"
    futuro = f"(status_atualizado_em IS NOT NULL AND status_atualizado_em > {f})"
    con.execute("PRAGMA query_only = OFF")  # temp fica fora do arquivo; o .db continua read-only
    try:
        for v in VIEWS_PERMITIDAS:
            con.execute(f"DROP VIEW IF EXISTS temp.{v}")
        con.executescript(f"""
CREATE TEMP VIEW vw_vendas AS
SELECT venda_id, creator_id, link_id, produto_id, produto_tipo, garantia_dias, comissao_pct, comprador_id,
       ts, valor, meio_pagamento, cartao_hash, dispositivo_hash, ip_hash,
       CASE WHEN {futuro} THEN 'APROVADA' ELSE status END AS status,
       CASE WHEN {futuro} THEN NULL ELSE status_atualizado_em END AS status_atualizado_em
FROM main.vw_vendas WHERE ts <= {f};

CREATE TEMP VIEW vw_comissoes AS
SELECT c.comissao_id, c.venda_id, c.creator_id, c.valor,
       CASE WHEN c.venda_status <> 'APROVADA' AND c.venda_status_atualizado_em <= {f} THEN 'ESTORNADA'
            WHEN c.liberada_em <= {f} THEN 'LIBERADA' ELSE 'PENDENTE' END AS status,
       CASE WHEN c.liberada_em <= {f} THEN c.liberada_em END AS liberada_em,
       CASE WHEN c.venda_status_atualizado_em > {f} THEN 'APROVADA' ELSE c.venda_status END AS venda_status,
       CASE WHEN c.venda_status_atualizado_em > {f} THEN NULL ELSE c.venda_status_atualizado_em END
            AS venda_status_atualizado_em
FROM main.vw_comissoes c JOIN main.vendas v ON v.venda_id = c.venda_id WHERE v.ts <= {f};

CREATE TEMP VIEW vw_saques   AS SELECT * FROM main.vw_saques   WHERE solicitado_em <= {f};
CREATE TEMP VIEW vw_logins   AS SELECT * FROM main.vw_logins   WHERE ts <= {f};
CREATE TEMP VIEW vw_cliques  AS SELECT * FROM main.vw_cliques  WHERE ts <= {f};
CREATE TEMP VIEW vw_creators AS SELECT * FROM main.vw_creators WHERE criado_em <= {f};
""")
    finally:
        con.execute("PRAGMA query_only = ON")


def executar(con: sqlite3.Connection, sql: str) -> tuple[list[str], list[list]]:
    """Valida, executa com timeout e devolve (colunas, linhas). Levanta SQLRejeitada ou sqlite3.Error."""
    sql = validar(sql)
    inicio = time.monotonic()
    # devolver não-zero aborta a consulta: evita uma SQL do LLM travando o agente
    con.set_progress_handler(lambda: int(time.monotonic() - inicio > TIMEOUT_SQL_SEG), 10_000)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        linhas = [list(r) for r in cur.fetchmany(C.AGENTE_LIMIT_MAX)]
    finally:
        con.set_progress_handler(None, 0)
    return cols, linhas


def schema_views(con: sqlite3.Connection) -> str:
    """Descrição das views para o prompt do LLM."""
    partes = []
    for v in sorted(VIEWS_PERMITIDAS):
        cols = [f"{r[1]}" for r in con.execute(f"PRAGMA table_info({v})")]
        partes.append(f"- {v}({', '.join(cols)})")
    return "\n".join(partes)


def mascarar(h: str | None) -> str:
    return f"***{h[-4:]}" if h else "—"


_HASH = re.compile(rf"\b[0-9a-f]{{{C.HASH_LEN}}}\b")


def mascarar_texto(texto: str) -> str:
    """LGPD: troca qualquer hash completo que o LLM tenha copiado por ***abcd."""
    return _HASH.sub(lambda m: mascarar(m.group(0)), texto)


# --------------------------------------------------------------------------- alerta
def carregar_alerta(con: sqlite3.Connection, alerta_id: int) -> dict:
    row = con.execute("""
        SELECT a.alerta_id, a.creator_id, a.saque_id, a.score_regras, a.prob_modelo, a.score_final,
               a.faixa_risco, a.regras_disparadas, a.shap_top, a.features, s.valor, s.solicitado_em
        FROM alertas a JOIN saques s USING (saque_id) WHERE a.alerta_id = ?""", (alerta_id,)).fetchone()
    if row is None:
        raise KeyError(f"alerta {alerta_id} não existe")
    keys = ["alerta_id", "creator_id", "saque_id", "score_regras", "prob_modelo", "score_final",
            "faixa_risco", "regras_disparadas", "shap_top", "features", "valor", "solicitado_em"]
    a = dict(zip(keys, row))
    a["regras_disparadas"] = json.loads(a["regras_disparadas"])
    a["shap_top"] = json.loads(a["shap_top"]) if a["shap_top"] else []
    a["features"] = json.loads(a["features"]) if a["features"] else {}
    fim = datetime.strptime(a["solicitado_em"], FMT)
    a["janela_ini"] = (fim - timedelta(days=C.JANELA_FEATURES_DIAS)).strftime(FMT)
    a["janela_fim"] = a["solicitado_em"]
    return a


# ------------------------------------------------------------ consultas canônicas
# Placeholders {c}, {ini}, {fim} são preenchidos com literais validados (ver _render),
# para que a SQL exibida ao analista seja exatamente a que rodou e possa ser copiada.
_JANELA = "v.creator_id = '{c}' AND v.ts > '{ini}' AND v.ts <= '{fim}'"

CANONICAS = {
    "autocompra": ("Vendas feitas em dispositivo usado no login do creator", f"""
SELECT COUNT(*) AS total_vendas,
       SUM(CASE WHEN v.dispositivo_hash IN (SELECT l.dispositivo_hash FROM vw_logins l
                 WHERE l.creator_id = '{{c}}' AND l.ts <= '{{fim}}') THEN 1 ELSE 0 END) AS vendas_disp_creator
FROM vw_vendas v WHERE {_JANELA} LIMIT 1"""),

    "rede_pix": ("Creators que sacam para a mesma chave Pix e vendas cruzadas entre eles", """
WITH rede AS (SELECT creator_id FROM vw_creators
              WHERE pix_hash = (SELECT pix_hash FROM vw_creators WHERE creator_id = '{c}')),
     disp_rede AS (SELECT DISTINCT l.creator_id, l.dispositivo_hash FROM vw_logins l
                   JOIN rede r ON r.creator_id = l.creator_id)
SELECT r.creator_id,
       (SELECT COUNT(DISTINCT v.venda_id) FROM vw_vendas v JOIN disp_rede d
          ON d.dispositivo_hash = v.dispositivo_hash AND d.creator_id <> v.creator_id
        WHERE v.creator_id = r.creator_id) AS vendas_vindas_de_outro_membro
FROM rede r ORDER BY r.creator_id LIMIT 50"""),

    "estorno": ("Reembolsos depois que a comissão já tinha sido liberada", f"""
SELECT COUNT(*) AS total_vendas,
       SUM(CASE WHEN c.venda_status = 'REEMBOLSADA' AND c.venda_status_atualizado_em <= '{{fim}}'
                 AND c.liberada_em IS NOT NULL AND c.venda_status_atualizado_em > c.liberada_em
                THEN 1 ELSE 0 END) AS estornos_pos_liberacao,
       ROUND(SUM(CASE WHEN c.venda_status = 'REEMBOLSADA' AND c.venda_status_atualizado_em <= '{{fim}}'
                 AND c.liberada_em IS NOT NULL AND c.venda_status_atualizado_em > c.liberada_em
                THEN c.valor ELSE 0 END), 2) AS comissao_paga_de_vendas_estornadas
FROM vw_vendas v JOIN vw_comissoes c ON c.venda_id = v.venda_id WHERE {_JANELA} LIMIT 1"""),

    "clique": ("Vendas com clique do mesmo IP menos de 15 segundos antes", f"""
SELECT COUNT(*) AS total_vendas,
       SUM(CASE WHEN EXISTS (SELECT 1 FROM vw_cliques k WHERE k.link_id = v.link_id
                  AND k.ip_hash = v.ip_hash AND k.ts <= v.ts
                  AND (julianday(v.ts) - julianday(k.ts)) * 86400 < 15) THEN 1 ELSE 0 END) AS vendas_menos_15s,
       COUNT(DISTINCT v.ip_hash) AS ips_distintos
FROM vw_vendas v WHERE {_JANELA} LIMIT 1"""),

    "cartao": ("Cartões usados por 3 ou mais compradores diferentes", f"""
SELECT v.cartao_hash, COUNT(DISTINCT v.comprador_id) AS compradores_distintos, COUNT(*) AS vendas,
       SUM(CASE WHEN v.status = 'CHARGEBACK' AND v.status_atualizado_em <= '{{fim}}' THEN 1 ELSE 0 END) AS chargebacks
FROM vw_vendas v WHERE {_JANELA} AND v.cartao_hash IS NOT NULL
GROUP BY v.cartao_hash HAVING COUNT(DISTINCT v.comprador_id) >= 3
ORDER BY compradores_distintos DESC LIMIT 20"""),

    "chargeback": ("Chargebacks conhecidos até o pedido de saque", f"""
SELECT COUNT(*) AS total_vendas,
       SUM(CASE WHEN v.status = 'CHARGEBACK' AND v.status_atualizado_em <= '{{fim}}' THEN 1 ELSE 0 END) AS chargebacks,
       SUM(CASE WHEN v.status = 'REEMBOLSADA' AND v.status_atualizado_em <= '{{fim}}' THEN 1 ELSE 0 END) AS reembolsos
FROM vw_vendas v WHERE {_JANELA} LIMIT 1"""),

    "disp_compartilhado": ("Outros creators que fizeram login nos mesmos dispositivos", """
SELECT l2.creator_id, COUNT(DISTINCT l2.dispositivo_hash) AS dispositivos_em_comum
FROM vw_logins l1 JOIN vw_logins l2
  ON l1.dispositivo_hash = l2.dispositivo_hash AND l2.creator_id <> l1.creator_id
WHERE l1.creator_id = '{c}' AND l1.ts <= '{fim}' AND l2.ts <= '{fim}'
GROUP BY l2.creator_id ORDER BY dispositivos_em_comum DESC LIMIT 50"""),

    "top_compradores": ("Compradores mais frequentes do creator", f"""
SELECT v.comprador_id, COUNT(*) AS compras, COUNT(DISTINCT v.dispositivo_hash) AS dispositivos,
       SUM(CASE WHEN v.status <> 'APROVADA' AND v.status_atualizado_em <= '{{fim}}' THEN 1 ELSE 0 END) AS estornos
FROM vw_vendas v WHERE {_JANELA}
GROUP BY v.comprador_id ORDER BY compras DESC LIMIT 5"""),
}

# Qual consulta canônica comprova cada regra / feature do SHAP
POR_REGRA = {"R1_AUTOCOMPRA": "autocompra", "R2_PIX_COMPARTILHADA": "rede_pix", "R3_ESTORNO_POS_LIB": "estorno",
             "R4_CLIQUE_RELAMPAGO": "clique", "R5_CARTAO_REPETIDO": "cartao", "R6_CHARGEBACK_ALTO": "chargeback",
             "R7_DISP_COMPARTILHADO": "disp_compartilhado"}
POR_FEATURE = {"pct_vendas_disp_creator": "autocompra", "qtd_creators_mesma_pix": "rede_pix",
               "taxa_estorno_pos_liberacao": "estorno", "taxa_reembolso": "estorno",
               "mediana_seg_clique_compra": "clique", "conversao": "clique",
               "qtd_cartoes_repetidos": "cartao", "taxa_chargeback": "chargeback",
               "qtd_creators_mesmo_disp": "disp_compartilhado", "share_top_comprador": "top_compradores"}


def _render(sql: str, a: dict) -> str:
    assert re.fullmatch(r"C\d{4}", a["creator_id"]), "creator_id fora do formato esperado"
    for k in ("janela_ini", "janela_fim"):
        datetime.strptime(a[k], FMT)  # garante que é data, não texto arbitrário
    return sql.format(c=a["creator_id"], ini=a["janela_ini"], fim=a["janela_fim"]).strip()


def consultas_canonicas(a: dict) -> list[tuple[str, str, str]]:
    """Escolhe as consultas pelas regras disparadas e pelas features do SHAP que empurraram para cima."""
    chaves = [POR_REGRA[r] for r in a["regras_disparadas"] if r in POR_REGRA]
    chaves += [POR_FEATURE[s["feature"]] for s in a["shap_top"]
               if s["shap"] > 0 and s["feature"] in POR_FEATURE]
    chaves = ["autocompra"] + chaves + ["top_compradores"]  # autocompra traz total_vendas: base de tudo
    vistas, out = set(), []
    for k in chaves:
        if k not in vistas:
            vistas.add(k)
            titulo, sql = CANONICAS[k]
            out.append((k, titulo, _render(sql, a)))
    return out


# ----------------------------------------------------------------- rede de contas
def rede_de_contas(con: sqlite3.Connection, creator_id: str, ate: str | None = None) -> dict:
    """Vizinhança de 1 salto: creators que dividem Pix ou dispositivo de login com o investigado."""
    ate = ate or "9999-12-31"
    pix = con.execute("SELECT pix_hash FROM vw_creators WHERE creator_id = ?", (creator_id,)).fetchone()[0]
    mesma_pix = [r[0] for r in con.execute(
        "SELECT creator_id FROM vw_creators WHERE pix_hash = ? AND creator_id <> ? ORDER BY 1", (pix, creator_id))]
    disps = con.execute("""
        SELECT l2.dispositivo_hash, l2.creator_id FROM vw_logins l1
        JOIN vw_logins l2 ON l1.dispositivo_hash = l2.dispositivo_hash AND l2.creator_id <> l1.creator_id
        WHERE l1.creator_id = ? AND l1.ts <= ? AND l2.ts <= ?
        GROUP BY 1, 2 ORDER BY 1, 2""", (creator_id, ate, ate)).fetchall()

    nos = {creator_id: {"id": creator_id, "tipo": "creator", "investigado": True}}
    arestas = []
    if mesma_pix:
        pid = f"pix:{mascarar(pix)}"
        nos[pid] = {"id": pid, "tipo": "pix", "rotulo": f"Pix {mascarar(pix)}"}
        for c in [creator_id] + mesma_pix:
            nos.setdefault(c, {"id": c, "tipo": "creator", "investigado": False})
            arestas.append((c, pid))
    for d, c in disps:
        did = f"disp:{mascarar(d)}"
        nos.setdefault(did, {"id": did, "tipo": "dispositivo", "rotulo": f"Disp. {mascarar(d)}"})
        nos.setdefault(c, {"id": c, "tipo": "creator", "investigado": False})
        for x in (creator_id, c):
            if (x, did) not in arestas:
                arestas.append((x, did))
    ligados = sorted({n for n, v in nos.items() if v["tipo"] == "creator" and n != creator_id})
    return {"nos": list(nos.values()), "arestas": arestas, "creators_ligados": ligados,
            "mesma_pix": mesma_pix, "mesmo_disp": sorted({c for _, c in disps})}
