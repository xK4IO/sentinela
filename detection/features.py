"""Cálculo das features (campos unificados, seção 5.3 da doc técnica), uma linha por saque.

Três princípios guiam este arquivo:

1. JANELA: tudo é medido nos 30 dias anteriores a `solicitado_em`.

2. SEM VAZAMENTO DO FUTURO (data leakage): só contamos o que já era conhecido no
   momento do saque. Uma venda que vira chargeback DEPOIS do saque ainda aparece como
   APROVADA para aquele saque. Se usássemos o status final, o modelo "veria o futuro"
   e as métricas sairiam boas demais, mas falhariam em produção.

3. AUSENTE ≠ ZERO: um creator sem vendas na janela tem taxa_reembolso = NaN (sem
   informação), não 0 (que significaria "creator perfeito"). O LightGBM trata NaN de
   forma nativa e as regras ignoram NaN (UC04).
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

import config as C

FEATURES = [
    "qtd_vendas",
    "taxa_reembolso",
    "taxa_chargeback",
    "taxa_estorno_pos_liberacao",
    "pct_vendas_disp_creator",
    "qtd_creators_mesma_pix",
    "qtd_creators_mesmo_disp",
    "conversao",
    "mediana_seg_clique_compra",
    "share_top_comprador",
    "qtd_cartoes_repetidos",
    "idade_conta_dias",
    "crescimento_vendas_7d",
]

# Features que são taxas: ficam NaN quando não há vendas na janela
TAXAS = ["taxa_reembolso", "taxa_chargeback", "taxa_estorno_pos_liberacao",
         "pct_vendas_disp_creator", "conversao", "mediana_seg_clique_compra",
         "share_top_comprador", "crescimento_vendas_7d"]


def _q(con: sqlite3.Connection, sql: str, datas: list[str] | None = None) -> pd.DataFrame:
    return pd.read_sql(sql, con, parse_dates=datas or [])


def saques_avaliados(con: sqlite3.Connection) -> pd.DataFrame:
    """Saques que o Sentinela avalia: os pendentes (SOLICITADO) e os que já têm alerta
    (porque, depois do score, o status deles muda para RETIDO/APROVADO)."""
    return _q(con, """
        SELECT saque_id, creator_id, valor, solicitado_em FROM saques
        WHERE status = 'SOLICITADO' OR saque_id IN (SELECT saque_id FROM alertas)
        ORDER BY saque_id""", ["solicitado_em"])


def calcular_features(con: sqlite3.Connection, saques: pd.DataFrame) -> pd.DataFrame:
    """Recebe saques (saque_id, creator_id, solicitado_em) e devolve um DataFrame
    indexado por saque_id com as colunas de FEATURES."""
    s = saques[["saque_id", "creator_id", "solicitado_em"]].copy()
    s["solicitado_em"] = pd.to_datetime(s.solicitado_em)
    s["ini"] = s.solicitado_em - pd.Timedelta(days=C.JANELA_FEATURES_DIAS)
    out = pd.DataFrame(index=pd.Index(s.saque_id, name="saque_id"))

    # ---------------------------------------------------------------- vendas na janela
    vendas = _q(con, """
        SELECT v.venda_id, l.creator_id, v.link_id, v.comprador_id, v.ts, v.cartao_hash,
               v.dispositivo_hash, v.ip_hash, v.status, v.status_atualizado_em, c.liberada_em
        FROM vendas v
        JOIN links l USING (link_id)
        LEFT JOIN comissoes c USING (venda_id)""",
        ["ts", "status_atualizado_em", "liberada_em"])
    vendas["seg_clique"] = _segundos_desde_clique(con, vendas)

    vj = s.merge(vendas, on="creator_id")
    vj = vj[(vj.ts > vj.ini) & (vj.ts <= vj.solicitado_em)].copy()

    conhecido = vj.status_atualizado_em.notna() & (vj.status_atualizado_em <= vj.solicitado_em)
    vj["reemb"] = conhecido & (vj.status == "REEMBOLSADA")
    vj["cb"] = conhecido & (vj.status == "CHARGEBACK")
    vj["estorno_pos_lib"] = vj.reemb & vj.liberada_em.notna() & (vj.status_atualizado_em > vj.liberada_em)

    # dispositivos que o próprio creator usou para logar (até a data do saque)
    logins = _q(con, "SELECT creator_id, dispositivo_hash, ts FROM logins_creator", ["ts"])
    proprios = s.merge(logins, on="creator_id")
    proprios = proprios.loc[proprios.ts <= proprios.solicitado_em, ["saque_id", "dispositivo_hash"]]
    proprios = proprios.drop_duplicates().assign(disp_proprio=True)
    vj = vj.merge(proprios, on=["saque_id", "dispositivo_hash"], how="left")
    vj["disp_proprio"] = vj.disp_proprio.eq(True)

    g = vj.groupby("saque_id")
    out["qtd_vendas"] = g.size()
    out["taxa_reembolso"] = g.reemb.mean()
    out["taxa_chargeback"] = g.cb.mean()
    out["taxa_estorno_pos_liberacao"] = g.estorno_pos_lib.mean()
    out["pct_vendas_disp_creator"] = g.disp_proprio.mean()
    out["mediana_seg_clique_compra"] = g.seg_clique.median()  # NaN se nenhuma venda teve clique pareado
    out["share_top_comprador"] = (vj.groupby(["saque_id", "comprador_id"]).size()
                                  .groupby(level=0).max() / out.qtd_vendas)

    cart = (vj.dropna(subset=["cartao_hash"])
            .groupby(["saque_id", "cartao_hash"]).comprador_id.nunique())
    out["qtd_cartoes_repetidos"] = (cart[cart >= C.MIN_COMPRADORES_CARTAO_REPETIDO]
                                    .groupby(level=0).size())

    # crescimento: vendas dos últimos 7 dias ÷ média semanal das 3 semanas anteriores.
    # Suavização +1 em cima e embaixo (Laplace) para não dividir por zero quando o
    # creator não vendeu nas semanas anteriores.
    dias_antes = (vj.solicitado_em - vj.ts).dt.total_seconds() / 86400
    vj["ult7"] = dias_antes <= 7
    vj["sem_ant"] = (dias_antes > 7) & (dias_antes <= 28)
    out["crescimento_vendas_7d"] = (g.ult7.sum() + 1) / (g.sem_ant.sum() / 3 + 1)

    # ---------------------------------------------------------------- cliques
    cliques = _q(con, "SELECT l.creator_id, k.ts FROM cliques k JOIN links l USING (link_id)", ["ts"])
    out["conversao"] = out.qtd_vendas / _contar_na_janela(s, cliques)

    # ---------------------------------------------------------------- rede de contas
    creators = _q(con, "SELECT creator_id, pix_hash, criado_em FROM creators", ["criado_em"])
    creators["qtd_creators_mesma_pix"] = creators.groupby("pix_hash").creator_id.transform("count") - 1
    s2 = s.merge(creators, on="creator_id")
    out["qtd_creators_mesma_pix"] = s2.set_index("saque_id").qtd_creators_mesma_pix
    out["idade_conta_dias"] = ((s2.solicitado_em - s2.criado_em).dt.total_seconds() / 86400).values
    out["qtd_creators_mesmo_disp"] = _creators_mesmo_disp(s, logins)

    # ---------------------------------------------------------------- regras de borda
    out["qtd_vendas"] = out.qtd_vendas.fillna(0).astype(int)
    for col in ["qtd_cartoes_repetidos", "qtd_creators_mesmo_disp", "qtd_creators_mesma_pix"]:
        out[col] = out[col].fillna(0).astype(int)
    sem_vendas = out.qtd_vendas == 0
    out.loc[sem_vendas, TAXAS] = np.nan                       # UC04: ausente ≠ zero
    out.loc[out.idade_conta_dias < 7, "crescimento_vendas_7d"] = np.nan
    out["conversao"] = out.conversao.replace([np.inf], np.nan)  # 0 cliques
    return out[FEATURES]


def _segundos_desde_clique(con: sqlite3.Connection, vendas: pd.DataFrame) -> pd.Series:
    """Para cada venda: segundos desde o último clique do MESMO ip no MESMO link.
    merge_asof faz um 'join pelo mais próximo anterior', que é exatamente o que precisamos."""
    cliques = _q(con, "SELECT link_id, ip_hash, ts AS ts_clique FROM cliques", ["ts_clique"])
    v = vendas[["venda_id", "link_id", "ip_hash", "ts"]].sort_values("ts")
    m = pd.merge_asof(v, cliques.sort_values("ts_clique"), left_on="ts", right_on="ts_clique",
                      by=["link_id", "ip_hash"], direction="backward")
    seg = (m.ts - m.ts_clique).dt.total_seconds()
    return pd.Series(seg.values, index=m.venda_id).reindex(vendas.venda_id).values


def _contar_na_janela(s: pd.DataFrame, eventos: pd.DataFrame) -> pd.Series:
    """Conta eventos (creator_id, ts) dentro de (ini, solicitado_em] de cada saque,
    usando busca binária em vez de um merge gigante."""
    por_creator = {c: np.sort(df.ts.values) for c, df in eventos.groupby("creator_id")}
    vazio = np.array([], dtype="datetime64[ns]")
    contagem = []
    for row in s.itertuples():
        ts = por_creator.get(row.creator_id, vazio)
        fim = np.searchsorted(ts, np.datetime64(row.solicitado_em), side="right")
        ini = np.searchsorted(ts, np.datetime64(row.ini), side="right")
        contagem.append(fim - ini)
    return pd.Series(contagem, index=s.saque_id.values, dtype=float)


def _creators_mesmo_disp(s: pd.DataFrame, logins: pd.DataFrame) -> pd.Series:
    """Quantos OUTROS creators já tinham logado em algum dispositivo do creator até a data do saque."""
    primeiro = logins.groupby(["creator_id", "dispositivo_hash"]).ts.min().reset_index()
    pares = primeiro.merge(primeiro, on="dispositivo_hash", suffixes=("", "_outro"))
    pares = pares[pares.creator_id != pares.creator_id_outro]
    pares["desde"] = pares[["ts", "ts_outro"]].max(axis=1)  # momento em que o vínculo passou a existir
    m = s.merge(pares[["creator_id", "creator_id_outro", "desde"]], on="creator_id")
    m = m[m.desde <= m.solicitado_em]
    return m.groupby("saque_id").creator_id_outro.nunique()
