"""Smoke test da interface: renderiza as telas sem navegador (streamlit.testing)."""
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

import config as C

APP = str(C.ROOT / "app" / "streamlit_app.py")


@pytest.fixture(autouse=True)
def precisa_db():
    if not C.DB_PATH.exists():
        pytest.skip("sem youshop.db")


def test_tela_inicial_renderiza_sem_erro():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 4
    assert any("Retidos aguardando" in m.label for m in at.metric)


def _alerta(com_dossie: bool) -> int:
    con = sqlite3.connect(C.DB_PATH)
    cond = "EXISTS" if com_dossie else "NOT EXISTS"
    row = con.execute(f"""SELECT alerta_id FROM alertas a JOIN saques s USING (saque_id)
                          WHERE faixa_risco = 'ALTO' AND s.status = 'RETIDO'
                          AND {cond} (SELECT 1 FROM dossies d WHERE d.alerta_id = a.alerta_id) LIMIT 1""").fetchone()
    con.close()
    if row is None:
        pytest.skip("sem alerta nessa condição")
    return row[0]


@pytest.mark.parametrize("com_dossie", [True, False])
def test_dossie_renderiza(com_dossie):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["aberto"] = _alerta(com_dossie)
    at.run()
    assert not at.exception, at.exception
    assert any("Caso #A-" in m.value for m in at.markdown)


def test_decisao_exige_comentario():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["aberto"] = _alerta(True)
    at.run()
    if not at.radio:
        pytest.skip("caso já decidido")
    at.radio[0].set_value("NEGAR")
    confirmar = next(b for b in at.button if b.label == "Confirmar decisão")
    confirmar.click().run()  # confirmar sem comentário
    assert any("obrigatório" in e.value for e in at.error)
