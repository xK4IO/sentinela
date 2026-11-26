"""Captura recortes das telas do Sentinela para o vídeo (escala 2x, nítido em 1080 px de largura).

Só lê: nunca clica em registrar decisão nem em reiniciar a demonstração.
Uso: python video/capturas.py  (com o app em http://localhost:8502)
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "assets" / "telas"
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:8502"


def pronto(p, ms=3500):
    p.wait_for_timeout(ms)


def recorte(p, nome, locator):
    locator.scroll_into_view_if_needed()
    p.wait_for_timeout(600)
    locator.screenshot(path=str(OUT / f"{nome}.png"))
    print("ok", nome)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1100, "height": 1600}, device_scale_factor=2)
    p = ctx.new_page()
    p.goto(URL)
    p.wait_for_selector("[data-testid=stButtonGroup]", timeout=60000)
    pronto(p, 5000)
    # fila: as 4 primeiras linhas
    linhas = p.locator('div[class*="st-key-row_"]')
    recorte(p, "fila_linha1", linhas.nth(0))
    p.screenshot(path=str(OUT / "fila_topo.png"), clip={"x": 0, "y": 0, "width": 1100, "height": 900})
    print("ok fila_topo")
    # caso C0040 (rede de contas)
    p.get_by_placeholder("Nome ou código").fill("C0040")
    p.keyboard.press("Enter")
    pronto(p)
    p.locator("button:visible", has_text="Analisar").first.click()
    pronto(p, 4500)
    p.screenshot(path=str(OUT / "caso_topo.png"), clip={"x": 0, "y": 0, "width": 1100, "height": 1000})
    print("ok caso_topo")
    recorte(p, "rede", p.locator("div.st-key-box_rede"))
    recorte(p, "decisao", p.locator("div.st-key-box_decisao"))
    # primeira prova com os dados de origem abertos
    caixa = p.locator('div[class*="st-key-box_prova_1"]')
    caixa.locator("summary").first.click()
    pronto(p, 2500)
    recorte(p, "prova", caixa)
    # resultados
    p.locator("button", has_text="Voltar para a fila").click()
    pronto(p)
    p.locator("[data-testid=stButtonGroup] button", has_text="Resultados").first.click()
    pronto(p, 4000)
    p.screenshot(path=str(OUT / "resultados.png"), full_page=False, clip={"x": 0, "y": 0, "width": 1100, "height": 1100})
    print("ok resultados")
    b.close()
