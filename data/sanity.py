"""Checagem de sanidade da base: contagens e sinais por tipo (janela de 30 dias do saque pendente).

Uso:  python -m data.sanity
É uma prévia simplificada do features.py, só para validar que as fraudes plantadas aparecem.
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

con = sqlite3.connect(C.DB_PATH)
q = lambda s: pd.read_sql(s, con)  # noqa: E731

print("== Contagens ==")
for t in ["produtores", "produtos", "creators", "compradores", "links", "logins_creator",
          "cliques", "vendas", "comissoes", "saques"]:
    print(f"{t:16s} {q(f'SELECT COUNT(*) n FROM {t}').n[0]:>8,}")
print(q("SELECT fraude_tipo, COALESCE(observacao,'') obs, COUNT(*) n FROM gabarito "
        "GROUP BY 1,2 ORDER BY 1,2").to_string(index=False))

sq = q("SELECT creator_id, solicitado_em FROM saques WHERE status='SOLICITADO'")
sq["solicitado_em"] = pd.to_datetime(sq.solicitado_em)
v = q("SELECT * FROM vw_vendas")
for c in ["ts", "status_atualizado_em"]:
    v[c] = pd.to_datetime(v[c])
v = v.merge(sq, on="creator_id")
v = v[(v.ts <= v.solicitado_em) & (v.ts > v.solicitado_em - pd.Timedelta(days=C.JANELA_FEATURES_DIAS))]
# status visto no momento do saque (evita vazamento do futuro)
conhecido = v.status_atualizado_em.notna() & (v.status_atualizado_em <= v.solicitado_em)
v["reemb"] = conhecido & (v.status == "REEMBOLSADA")
v["cb"] = conhecido & (v.status == "CHARGEBACK")
v["lib"] = v.ts + pd.Timedelta(days=C.LIBERACAO_COMISSAO_DIAS)
v["estorno_pos_lib"] = v.reemb & (v.status_atualizado_em > v.lib)

logins = q("SELECT DISTINCT creator_id, dispositivo_hash FROM logins_creator")
v = v.merge(logins.assign(disp_proprio=True), on=["creator_id", "dispositivo_hash"], how="left")
v["disp_proprio"] = v.disp_proprio.fillna(False).astype(bool)

g = v.groupby("creator_id").agg(
    qtd_vendas=("venda_id", "count"),
    taxa_reembolso=("reemb", "mean"),
    taxa_chargeback=("cb", "mean"),
    taxa_estorno_pos_liberacao=("estorno_pos_lib", "mean"),
    pct_vendas_disp_creator=("disp_proprio", "mean"),
)
cart = (v.dropna(subset=["cartao_hash"]).groupby(["creator_id", "cartao_hash"]).comprador_id
        .nunique().reset_index())
g["qtd_cartoes_repetidos"] = (cart[cart.comprador_id >= C.MIN_COMPRADORES_CARTAO_REPETIDO]
                              .groupby("creator_id").size())
cr = q("SELECT creator_id, pix_hash FROM creators")
cr["qtd_creators_mesma_pix"] = cr.groupby("pix_hash").creator_id.transform("count") - 1
disp = logins.merge(logins, on="dispositivo_hash")
disp = disp[disp.creator_id_x != disp.creator_id_y]
mesmo_disp = disp.groupby("creator_id_x").creator_id_y.nunique().rename("qtd_creators_mesmo_disp")

gab = q("SELECT creator_id, fraude_tipo, COALESCE(observacao,'') obs FROM gabarito")
df = (gab.merge(sq[["creator_id"]].assign(tem_saque=1), on="creator_id", how="left")
      .merge(g, on="creator_id", how="left")
      .merge(cr[["creator_id", "qtd_creators_mesma_pix"]], on="creator_id")
      .merge(mesmo_disp, left_on="creator_id", right_index=True, how="left"))
df["qtd_cartoes_repetidos"] = df.qtd_cartoes_repetidos.fillna(0)
df["qtd_creators_mesmo_disp"] = df.qtd_creators_mesmo_disp.fillna(0)

cols = ["qtd_vendas", "pct_vendas_disp_creator", "qtd_creators_mesma_pix",
        "taxa_estorno_pos_liberacao", "qtd_cartoes_repetidos", "taxa_chargeback",
        "qtd_creators_mesmo_disp", "taxa_reembolso"]
pd.set_option("display.width", 220)
print("\n== Médias por tipo (janela do saque pendente) ==")
print(df.groupby(["fraude_tipo", "obs"])[["tem_saque"] + cols].agg(
    lambda s: round(s.mean(), 3)).to_string())
print(f"\nCreators com saque pendente: {int(df.tem_saque.sum())} | "
      f"sem vendas na janela (entre os pendentes): "
      f"{int((df.tem_saque.eq(1) & df.qtd_vendas.isna()).sum())}")
