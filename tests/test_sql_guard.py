import sqlite3

import pytest

import config as C
from agent.sql_guard import SQLRejeitada, validar


@pytest.mark.parametrize("sql, motivo", [
    ("UPDATE saques SET status='APROVADO'", "só SELECT"),                       # UC05
    ("DELETE FROM vw_vendas", "só SELECT"),
    ("SELECT * FROM vw_vendas LIMIT 5; DROP TABLE vendas", "exatamente 1"),
    ("SELECT * FROM gabarito LIMIT 5", "não permitida"),
    ("SELECT nome FROM creators LIMIT 5", "não permitida"),
    ("SELECT * FROM main.vw_vendas LIMIT 5", "schema"),
    ("SELECT * FROM vw_vendas", "LIMIT é obrigatório"),
    ("SELECT * FROM vw_vendas LIMIT 500", "fora do permitido"),
    ("PRAGMA table_info(vendas)", ""),
    ("ATTACH DATABASE 'x.db' AS x", ""),
    ("SELECT load_extension('x') FROM vw_vendas LIMIT 1", "proibida"),
    ("SELECT * FROM vw_vendas WHERE creator_id IN (SELECT creator_id FROM gabarito) LIMIT 5", "não permitida"),
    ("SELEC * FROM", ""),
])
def test_rejeita(sql, motivo):
    with pytest.raises(SQLRejeitada, match=motivo or None):
        validar(sql)


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM vw_vendas WHERE creator_id = 'C0001' LIMIT 1",
    "WITH rede AS (SELECT creator_id FROM vw_creators WHERE pix_hash = 'x') "
    "SELECT v.* FROM vw_vendas v JOIN rede r ON r.creator_id = v.creator_id LIMIT 200",
    "SELECT creator_id FROM vw_logins UNION SELECT creator_id FROM vw_cliques LIMIT 10",
    "select comprador_id, count(*) n from VW_VENDAS group by 1 order by n desc limit 5",
])
def test_aceita(sql):
    assert validar(sql)


def test_corte_point_in_time_esconde_o_futuro():
    if not C.DB_PATH.exists():
        pytest.skip("sem youshop.db")
    from agent.tools import conectar_ro, executar, restringir_ate
    con = conectar_ro()
    # uma venda que virou chargeback: antes da data do chargeback ela precisa aparecer APROVADA
    vid, ts, quando = con.execute("SELECT venda_id, ts, status_atualizado_em FROM vendas "
                                  "WHERE status = 'CHARGEBACK' LIMIT 1").fetchone()
    restringir_ate(con, ts)
    _, linhas = executar(con, f"SELECT status, status_atualizado_em FROM vw_vendas WHERE venda_id = '{vid}' LIMIT 1")
    assert linhas == [["APROVADA", None]]
    _, futuro = executar(con, f"SELECT COUNT(*) FROM vw_vendas WHERE ts > '{ts}' LIMIT 1")
    assert futuro == [[0]]
    with pytest.raises(sqlite3.OperationalError):  # continua somente leitura
        con.execute("UPDATE vendas SET status='APROVADA'")


def test_conexao_somente_leitura_barra_escrita_mesmo_sem_validador():
    if not C.DB_PATH.exists():
        pytest.skip("sem youshop.db")
    from agent.tools import conectar_ro
    con = conectar_ro()
    with pytest.raises(sqlite3.OperationalError):
        con.execute("UPDATE saques SET status='APROVADO'")
