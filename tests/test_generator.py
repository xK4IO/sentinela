"""Testes da base sintética (D1). Requer data/youshop.db gerado: python -m data.generator"""
import sqlite3

import pytest

import config as C


@pytest.fixture(scope="module")
def con():
    if not C.DB_PATH.exists():
        pytest.skip("rode `python -m data.generator` antes")
    c = sqlite3.connect(C.DB_PATH)
    yield c
    c.close()


def um(con, sql):
    return con.execute(sql).fetchone()[0]


def test_volumes(con):
    assert um(con, "SELECT COUNT(*) FROM produtores") == C.N_PRODUTORES
    assert um(con, "SELECT COUNT(*) FROM produtos") == C.N_PRODUTOS
    assert um(con, "SELECT COUNT(*) FROM creators") == C.N_CREATORS
    assert um(con, "SELECT COUNT(*) FROM compradores") == C.N_COMPRADORES


def test_gabarito(con):
    rows = dict(con.execute("SELECT fraude_tipo, COUNT(*) FROM gabarito GROUP BY 1"))
    for t in C.TIPOS_FRAUDE:
        assert rows[t] == C.N_FRAUDE_POR_TIPO
    assert rows["LEGITIMO_VIRAL"] == C.N_VIRAIS


def test_todo_fraudador_e_viral_tem_saque_pendente(con):
    faltando = um(con, """
        SELECT COUNT(*) FROM gabarito g
        WHERE g.fraude_tipo <> 'NENHUMA'
          AND NOT EXISTS (SELECT 1 FROM saques s
                          WHERE s.creator_id = g.creator_id
                            AND (s.status = 'SOLICITADO'
                                 OR s.saque_id IN (SELECT saque_id FROM alertas)))""")
    assert faltando == 0


def test_pii_so_hash(con):
    for col, tab in [("cpf_hash", "creators"), ("pix_hash", "creators"), ("cpf_hash", "compradores")]:
        assert um(con, f"SELECT COUNT(*) FROM {tab} WHERE length({col}) <> {C.HASH_LEN}") == 0


def test_cartao_nulo_fora_de_cartao(con):
    assert um(con, "SELECT COUNT(*) FROM vendas WHERE meio_pagamento <> 'CARTAO' "
                   "AND cartao_hash IS NOT NULL") == 0


def test_status_atualizado_coerente(con):
    assert um(con, "SELECT COUNT(*) FROM vendas WHERE status = 'APROVADA' "
                   "AND status_atualizado_em IS NOT NULL") == 0
    assert um(con, "SELECT COUNT(*) FROM vendas WHERE status <> 'APROVADA' "
                   "AND (status_atualizado_em IS NULL OR status_atualizado_em < ts)") == 0


def test_reembolso_dentro_da_garantia(con):
    assert um(con, """
        SELECT COUNT(*) FROM vw_vendas
        WHERE status = 'REEMBOLSADA'
          AND julianday(status_atualizado_em) - julianday(ts) > garantia_dias""") == 0


def test_comissao_liberada_d_mais_2(con):
    assert um(con, f"""
        SELECT COUNT(*) FROM comissoes c JOIN vendas v USING (venda_id)
        WHERE c.liberada_em IS NOT NULL
          AND abs(julianday(c.liberada_em) - julianday(v.ts) - {C.LIBERACAO_COMISSAO_DIAS}) > 1e-4""") == 0


def test_rede_pix_tem_aneis(con):
    tamanhos = [n for (n,) in con.execute("""
        SELECT COUNT(*) FROM creators c JOIN gabarito g USING (creator_id)
        WHERE g.fraude_tipo = 'F2_REDE_PIX' GROUP BY c.pix_hash""")]
    assert all(4 <= n <= 6 for n in tamanhos) and sum(tamanhos) == C.N_FRAUDE_POR_TIPO


def test_views_sem_dados_sensiveis(con):
    for v in ["vw_creators", "vw_vendas", "vw_comissoes", "vw_saques", "vw_logins", "vw_cliques"]:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({v})")]
        assert "nome" not in cols and "fraude_tipo" not in cols and "cpf_hash" not in cols
