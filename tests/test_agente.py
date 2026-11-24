"""Testes ponta a ponta do agente com FakeLLM (sem rede). Usam o youshop.db real, sem gravar."""
import sqlite3

import pytest

import config as C
from agent.graph import investigar
from agent.llm import FakeLLM


def alerta_de(creator_id: str) -> int:
    con = sqlite3.connect(C.DB_PATH)
    row = con.execute("SELECT alerta_id FROM alertas WHERE creator_id = ? AND faixa_risco = 'ALTO'",
                      (creator_id,)).fetchone()
    con.close()
    if row is None:
        pytest.skip(f"{creator_id} não está em ALTO nesta base")
    return row[0]


@pytest.fixture(autouse=True)
def precisa_db():
    if not C.DB_PATH.exists():
        pytest.skip("sem youshop.db")


SQL_OK = ("SELECT COUNT(DISTINCT comprador_id) AS compradores FROM vw_vendas "
          "WHERE creator_id = 'C0016' LIMIT 1")
DOSSIE_OK = {
    "resumo": "Forte indício de autocompra: 25 de 35 vendas (71%) saíram de dispositivo do login do creator.",
    "afirmacoes": [{"texto": "25 de 35 vendas vieram de dispositivo usado no login", "evidencia_id": "E1"}],
    "recomendacao": "MANTER_RETIDO", "confianca": "ALTA",
    "justificativa": "Concentração incompatível com compras de terceiros.",
}


def test_uc01_autocompra_com_sql_rejeitada_e_corrigida():  # UC01 + UC05
    llm = FakeLLM({
        "Plano": [{"hipoteses": ["os compradores são poucas contas?"]}],
        "ConsultaSQL": [{"objetivo": "x", "sql": "UPDATE saques SET status='APROVADO'"},
                        {"objetivo": "x", "sql": SQL_OK}],
        "Analise": [{"achado": "poucas contas", "precisa_mais": False}],
        "DossieLLM": [DOSSIE_OK],
    })
    s = investigar(alerta_de("C0016"), llm, gravar=False, forcar_completa=True)
    status = [x["status"] for x in s["sql_executadas"] if x["origem"] == "llm"]
    assert status == ["rejeitada", "ok"]                 # UC05: rejeitada, conta como iteração
    assert s["iteracao"] == 2
    assert s["problemas"] == [] and s["confianca"] == "ALTA"
    assert s["recomendacao"] == "MANTER_RETIDO"
    assert "25 de 35 vendas" in s["texto_md"]
    assert s["evidencias"][1]["sql"].startswith("SELECT")  # evidência canônica traz a SQL


def test_uc05_tres_sqls_perigosas_param_na_terceira():
    llm = FakeLLM({
        "Plano": [{"hipoteses": ["h"]}],
        "ConsultaSQL": [{"objetivo": "x", "sql": "DELETE FROM vw_vendas"}],
        "DossieLLM": [DOSSIE_OK],
    })
    s = investigar(alerta_de("C0016"), llm, gravar=False, forcar_completa=True)
    assert s["iteracao"] == C.AGENTE_MAX_ITERACOES
    assert all(x["status"] != "ok" for x in s["sql_executadas"] if x["origem"] == "llm")
    assert not any(e.get("tipo") == "llm" for e in s["evidencias"])


def test_numero_inventado_duas_vezes_vira_confianca_baixa():
    ruim = {**DOSSIE_OK, "resumo": "Foram 987 vendas suspeitas."}
    llm = FakeLLM({"Plano": [{"hipoteses": []}], "DossieLLM": [ruim]})
    s = investigar(alerta_de("C0016"), llm, gravar=False, forcar_completa=True)
    assert s["tentativas_redacao"] == 2
    assert s["numero_inventado"] and s["confianca"] == "BAIXA"
    assert "não foram confirmados" in s["texto_md"]


def test_falha_da_api_gera_dossie_de_fallback():
    llm = FakeLLM({"Plano": [RuntimeError("429 quota exceeded")]})
    s = investigar(alerta_de("C0016"), llm, gravar=False, forcar_completa=True)
    assert s["fallback"] and s["confianca"] == "BAIXA" and s["recomendacao"] == "MANTER_RETIDO"
    assert len(s["dossie_llm"]["afirmacoes"]) >= 1


def test_uc02_rede_pix_aparece_no_dossie():
    llm = FakeLLM({"Plano": [{"hipoteses": []}],
                   "DossieLLM": [{**DOSSIE_OK, "resumo": "Rede de contas com a mesma chave Pix.",
                                  "afirmacoes": [{"texto": "Contas compartilham a Pix", "evidencia_id": "E2"}]}]})
    s = investigar(alerta_de("C0040"), llm, gravar=False)
    assert len(s["rede"]["mesma_pix"]) >= 2
    for c in s["rede"]["mesma_pix"]:
        assert c in s["texto_md"]


def test_caso_claro_vai_direto_para_redacao():
    # C0016: autocompra com prob_modelo alta e R1 disparada → só 1 chamada (redigir), sem planejar
    llm = FakeLLM({"DossieLLM": [DOSSIE_OK]})
    s = investigar(alerta_de("C0016"), llm, gravar=False)
    assert s["profundidade"] == "direta"
    assert s["chamadas_llm"] == 1 and [p[0] for p in llm.prompts] == ["DossieLLM"]
    assert s["confianca"] == "ALTA"
