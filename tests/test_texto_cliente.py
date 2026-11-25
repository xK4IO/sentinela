"""Limpeza do texto da IA para a tela (app/dados.py: texto_cliente)."""
from app.dados import texto_cliente

MAPA = {"E1": 1, "E2": 2}


def test_chargeback_vira_termo_do_glossario_com_concordancia():
    t = texto_cliente("foram registrados 2 chargebacks confirmados; em um chargeback associado", MAPA)
    assert "chargeback" not in t.lower()
    assert "registradas 2 contestações de cartão confirmadas" in t
    assert "uma contestação de cartão associada" in t


def test_dias_sem_decimais():
    assert texto_cliente("conta com 697,13 dias", MAPA) == "conta com 697 dias"


def test_prova_nao_cita_a_si_mesma_mas_mantem_parenteses_com_dado():
    t = texto_cliente("Foram 30 vendas (E1). Taxa (0% conforme a evidência E1).", MAPA, na_prova=True)
    assert t == "Foram 30 vendas. Taxa (0% conforme a prova 1)."


def test_fora_da_prova_a_referencia_fica():
    assert texto_cliente("ver detalhes (E2)", MAPA) == "ver detalhes (prova 2)"
