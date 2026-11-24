import math

import pandas as pd

import config as C
from detection.rules import avaliar
from detection.score import combinar, faixa


def test_nan_nao_dispara_regra():
    r = avaliar({"pct_vendas_disp_creator": math.nan, "mediana_seg_clique_compra": None})
    assert r.disparadas == [] and r.score_regras == 0 and not r.critica


def test_limiar_inclusivo_e_critica():
    r = avaliar({"pct_vendas_disp_creator": 0.20})  # UC01: >= 0,20 dispara
    assert r.disparadas == ["R1_AUTOCOMPRA"] and r.critica


def test_r4_e_estrito():
    assert avaliar({"mediana_seg_clique_compra": 15}).disparadas == []
    assert avaliar({"mediana_seg_clique_compra": 14.9}).disparadas == ["R4_CLIQUE_RELAMPAGO"]


def test_pix_de_casal_nao_e_critico():
    assert avaliar({"qtd_creators_mesma_pix": 1}).disparadas == []
    assert avaliar({"qtd_creators_mesma_pix": 4}).critica  # UC02


def test_score_limitado_a_1():
    tudo = {r["feature"]: (0 if r["op"] == "<" else 1e9) for r in C.REGRAS.values()}
    assert avaliar(tudo).score_regras == 1.0


def test_crescimento_sozinho_nao_dispara():  # UC03
    r = avaliar({"crescimento_vendas_7d": 9.5, "pct_vendas_disp_creator": 0.0, "taxa_reembolso": 0.04})
    assert r.disparadas == [] and faixa(0.0, r.critica) == "BAIXO"


def test_faixas_e_combinacao():
    assert faixa(0.1, True) == "ALTO"
    assert faixa(C.LIMIAR_ALTO, False) == "ALTO"
    assert faixa(C.LIMIAR_MEDIO, False) == "MEDIO"
    sf = combinar(pd.Series([0.2, 0.2]), pd.Series([0.99, float("nan")]))
    assert sf[0] == 0.99          # modelo pode escalar sozinho (max)
    assert sf[1] == 0.2           # modo degradado = score_regras
