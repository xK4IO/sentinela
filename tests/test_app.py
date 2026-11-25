"""Smoke test da interface: renderiza as telas sem navegador (streamlit.testing)."""
import re
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

import config as C

APP = str(C.ROOT / "app" / "streamlit_app.py")
# códigos internos que nunca podem aparecer para o cliente
PROIBIDOS = re.compile(r"F[1-5]_[A-Z]|R[1-7]_[A-Z]|LEGITIMO_VIRAL|gabarito|MANTER_RETIDO|\bE\d+\b|\|SHAP\|")


@pytest.fixture(autouse=True)
def precisa_db():
    if not C.DB_PATH.exists():
        pytest.skip("sem youshop.db")


def _texto_visivel(at) -> str:
    partes = [h.proto.body for h in at.get("html")] + [m.value for m in at.markdown] + [c.value for c in at.caption]
    sem_css = re.sub(r"<style>.*?</style>", "", "\n".join(partes), flags=re.S)
    return re.sub(r"<[^>]+>", " ", sem_css)  # só o texto, sem tags/atributos


@pytest.mark.parametrize("pagina", ["fila", "obs", "dec", "res"])
def test_paginas_renderizam_sem_codigos_internos(pagina):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["nav"] = pagina
    at.run()
    assert not at.exception, at.exception
    achados = PROIBIDOS.findall(_texto_visivel(at))
    assert not achados, f"códigos internos na tela: {set(achados)}"


def _alerta_retido() -> int:
    con = sqlite3.connect(C.DB_PATH)
    row = con.execute("""SELECT a.alerta_id FROM alertas a JOIN saques s USING (saque_id)
                         WHERE a.faixa_risco = 'ALTO' AND s.status = 'RETIDO' LIMIT 1""").fetchone()
    con.close()
    if row is None:
        pytest.skip("nenhum caso retido")
    return row[0]


def test_caso_renderiza_sem_codigos_internos():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["aberto"] = _alerta_retido()
    at.run()
    assert not at.exception, at.exception
    assert "Saque em análise" in _texto_visivel(at)
    assert not PROIBIDOS.findall(_texto_visivel(at))


def test_decisao_exige_comentario():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["aberto"] = _alerta_retido()
    at.run()
    at.radio[0].set_value("NEGAR").run()
    next(b for b in at.button if b.label == "Registrar decisão").click().run()
    assert any("obrigatório" in e.value for e in at.error)
