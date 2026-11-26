"""Gera video/index.html: cenas, legendas e timeline GSAP amarradas aos tempos da narração.

A fala manda no relógio: todo instante vem de work/frases.json (palavras do roteiro com tempo real).
Reajustar texto ou tempo = editar aqui e rodar de novo:  python video/gen.py
"""
import html
import json
import re
from pathlib import Path

from PIL import Image

D = Path(__file__).parent
FR = json.loads((D / "work" / "frases.json").read_text(encoding="utf-8"))
DUR = 131.0


def t(palavra, bloco=None, n=0):
    """Instante (início) da n-ésima ocorrência de uma palavra do roteiro (comparação sem pontuação)."""
    alvo = re.sub(r"[^\w%.]", "", palavra.lower())
    achados = [w[0] for f in FR if bloco is None or f["bloco"] == bloco
               for w in f["palavras"] if re.sub(r"[^\w%.]", "", w[2].lower()).rstrip(".") == alvo.rstrip(".")]
    return round(achados[n], 2)


def fim_frase(i):
    return FR[i]["fim"]


# cortes entre cenas (um pouco antes da primeira palavra do bloco seguinte)
C = [0, 7.15, 18.2, 30.95, 51.3, 69.05, 93.3, 114.05, 119.18, 124.65, DUR]
T = {
    # s1
    "s1_dots": 0.5, "fraude1": t("fraude?", 1),
    # s2
    "auto": t("autocompra.", 2), "cartao": t("cartão", 2), "pix": t("contas", 2),
    "saiu": t("saiu,", 2), "prejuizo": t("prejuízo.", 2),
    # s3
    "eu": t("eu", 3), "sent": t("sentinela.", 3), "analisa": t("analisa", 3), "bloqueia": t("bloqueia", 3),
    "retem": t("retém", 3), "relatorio": t("relatório", 3),
    # s4
    "camadas": t("camadas.", 4), "sete": t("sete", 4), "lgbm": t("lightgbm,", 4), "agente": t("agente", 4),
    "conferido": t("cada", 4, 1),
    # s5
    "fila": t("fila", 5), "provas": t("provas,", 5), "mapa": t("mapa", 5), "decisao": t("decisão", 5),
    "liberar": t("liberar", 5), "negar": t("negar,", 5),
    # s6
    "apr": t("aprendizados", 6), "formula": t("fórmula", 6), "p51": t("51%", 6), "recal": t("recalibrada,", 6),
    "modelo": t("maior", 6), "prompt": t("prompt", 6), "codigo": t("código,", 6), "claros": t("claros", 6),
    "p52": t("52%", 6),
    # s7
    "base": t("1.158", 7), "p85": t("85%", 7), "p94": t("94%", 7), "trinta": t("30", 7), "mil16": t("16", 7),
    "r143": t("143", 7),
    # s8 / s9 / s10
    "mas": t("mas", 8), "seguida": t("seguida", 8), "sete7": t("7", 8), "fraudadores": t("fraudadores.", 8),
    "recomenda": t("isso", 8), "quem": t("quem", 8), "pessoa": t("pessoa.", 8),
    "sent2": t("sentinela.", 9), "protecao": t("proteção", 9), "caio": t("caio", 9),
}


def palavras(texto, cls=""):
    return " ".join(f'<span class="w {cls}">{html.escape(p)}</span>' for p in texto.split())


ICON = {
    "auto": '<svg width="92" height="92" viewBox="0 0 24 24" fill="none" stroke="#E5524C" stroke-width="1.8" stroke-linecap="round"><path d="M4 12a8 8 0 0 1 13.7-5.6M20 12a8 8 0 0 1-13.7 5.6"/><path d="M18 3v4h-4M6 21v-4h4"/></svg>',
    "cartao": '<svg width="92" height="92" viewBox="0 0 24 24" fill="none" stroke="#E5524C" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h4"/></svg>',
    "pix": '<svg width="92" height="92" viewBox="0 0 24 24" fill="none" stroke="#E5524C" stroke-width="1.8" stroke-linecap="round"><circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="12" r="2.8"/><path d="M8.2 7.2l7.4 3.6M8.2 16.8l7.4-3.6"/></svg>',
    "check": '<svg width="58" height="58" viewBox="0 0 24 24" fill="none" stroke="#8CD43A" stroke-width="2.4" stroke-linecap="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
}


def tela(id_, arquivo, largura_max=900, altura_max=860):
    w, h = Image.open(D / "assets" / "telas" / arquivo).size
    esc = min(largura_max / w, altura_max / h)
    W, H = round(w * esc), round(h * esc)
    return (f'<div class="tela" id="{id_}" style="width:{W}px;height:{H}px;left:{(900 - W) // 2}px;top:{(880 - H) // 2}px">'
            f'<img src="assets/telas/{arquivo}" alt=""></div>')


dots = "".join(f'<div class="dot" id="d{i}"></div>' for i in range(48))
FRAUDE_DOTS = [5, 13, 22, 30, 41]

CENAS = [
    # s1 gancho
    f'''<div class="mono muted rv" id="s1l" style="font-size:28px;letter-spacing:.16em">CREATORS · SAQUES DE COMISSÃO</div>
<div class="dots">{dots}</div>
<h1 style="text-align:center;margin-top:40px"><span class="rv red" id="s1f" style="display:inline-block">fraude?</span></h1>''',
    # s2 problema
    f'''<div class="chip rv" id="c2"><i>01</i>O problema</div>
<div class="tipo rv" id="t1">{ICON["auto"]}Autocompra</div>
<div class="tipo rv" id="t2">{ICON["cartao"]}Cartão de terceiros</div>
<div class="tipo rv" id="t3">{ICON["pix"]}Mesma chave Pix</div>
<div class="card rv" id="s2din" style="margin-top:30px;display:flex;justify-content:space-between;align-items:center">
  <span style="font-size:42px;font-weight:700">Saque pago</span><span class="mono muted" style="font-size:30px">o dinheiro já saiu</span></div>
<div class="perda rv" id="s2p"><span class="big red">−R$</span><span style="font-size:56px;font-weight:800">prejuízo</span></div>''',
    # s3 solução
    f'''<div class="chip rv" id="c3"><i>02</i>A solução</div>
<div style="display:flex;align-items:center;gap:36px"><img class="logo-big rv" id="s3logo" src="assets/logo.png" alt="">
  <h1 class="rv" id="s3n" style="font-size:118px">Sentinela</h1></div>
<div class="fluxo">
  <div class="card etapa rv" id="s3a"><span>Pedido de saque</span><span class="mono muted" style="font-size:30px">antes de pagar</span></div>
  <div class="card etapa rv" id="s3b"><span>Sinais de fraude</span><span class="badge no">BLOQUEAR</span></div>
  <div class="card etapa rv" id="s3c" style="border-color:var(--amber)"><span>Saque</span><span class="badge ret">RETIDO</span></div>
  <div class="card doc rv" id="s3d"><b style="font-size:40px">Relatório de investigação</b>
    <div class="p"><b>1</b>Prova com dados de origem</div><div class="p"><b>2</b>Prova com dados de origem</div></div>
</div>''',
    # s4 como funciona
    f'''<div class="chip rv" id="c4"><i>03</i>Como funciona</div>
<h2 class="rv" id="s4t">Três camadas</h2>
<div class="camada rv" id="k1"><div class="n">7</div><div><h3>Regras de negócio</h3><p>objetivas e fáceis de explicar</p></div></div>
<div class="camada rv" id="k2"><div class="n" style="font-size:34px">ML</div><div><h3>Modelo LightGBM</h3><p>compara com fraudes já vistas</p></div></div>
<div class="camada rv" id="k3"><div class="n" style="font-size:34px">IA</div><div><h3>Agente de IA · Gemini</h3><p>investiga os dados e escreve o relatório</p></div></div>
<div class="ok rv" id="s4ok">{ICON["check"]}Todo número conferido na origem</div>''',
    # s5 demo
    f'''<div class="chip rv" id="c5"><i>04</i>Na tela do analista</div>
<div class="palco">{tela("v1", "fila_topo.png")}{tela("v2", "prova.png")}{tela("v3", "rede.png")}{tela("v4", "decisao.png", 820, 720)}</div>
<div style="position:relative;height:60px">
  <div class="legenda-tela" id="l1">Fila com risco e prazo</div>
  <div class="legenda-tela" id="l2">Prova + consulta de origem</div>
  <div class="legenda-tela" id="l3">Mapa de contas ligadas</div>
  <div class="legenda-tela" id="l4"><span class="lime">Liberar</span> ou <span class="red">negar</span>: decide o analista</div>
</div>''',
    # s6 bastidores
    f'''<div class="chip rv" id="c6"><i>05</i>Bastidores</div>
<h2 class="rv" id="s6t">3 aprendizados</h2>
<div class="card apr rv" id="a1"><h3>Fórmula de risco</h3><p>a da especificação deixava fraude passar</p><div class="v"><span id="n51">51</span>%</div></div>
<div class="card apr rv" id="a2"><h3><span class="risco" id="rp">Prompt</span> <span class="lime rv" id="cod">Código</span></h3><p>a IA maior consultou dados do futuro</p><div class="v mono" style="font-size:44px;color:var(--muted)">segurança</div></div>
<div class="card apr rv" id="a3"><h3>Casos claros: 1 chamada</h3><div class="barra"><i id="b52"></i></div><div class="v rv lime" id="m52">−52%</div></div>''',
    # s7 resultados
    f'''<div class="chip rv" id="c7"><i>06</i>Resultados</div>
<div class="mono muted rv" id="s7b" style="font-size:30px;letter-spacing:.1em">BASE SIMULADA · <span id="n1158">0</span> SAQUES</div>
<div class="num rv" id="r1"><b class="lime"><span id="n85">0</span>%</b><span>das fraudes identificadas</span></div>
<div class="num rv" id="r2"><b><span id="n94">0</span>%</b><span>de acerto nas retenções</span></div>
<div class="num rv" id="r3"><b>30 de 30</b><span>creators em alta preservados</span></div>
<div class="card cmp rv" id="r4">
  <div class="l"><span>Fraude retida</span><span class="lime">R$ 16 mil</span></div><div class="t"><i id="bf" style="width:0;background:var(--accent)"></i></div>
  <div class="l rv" id="r5l"><span>Legítimos retidos</span><span style="color:var(--amber)">R$ 143</span></div><div class="t rv" id="r5t"><i id="bl" style="width:0;background:var(--amber)"></i></div>
</div>''',
    # s8 antes do clímax
    f'''<div style="flex:1"></div>
<h2 id="s8a" style="font-size:86px">{palavras("Mas o número mais importante é outro.")}</h2>
<div class="muted rv" id="s8b" style="font-size:46px;font-weight:600;line-height:1.3">Seguida sem revisão, a IA teria liberado…</div>
<div style="flex:1.3"></div>''',
    # s9 clímax
    f'''<div style="flex:.6"></div>
<div class="sete rv" id="s9n">7</div>
<div class="rv" id="s9a" style="text-align:center;font-size:60px;font-weight:800;line-height:1.15">fraudadores teriam recebido o saque</div>
<div class="rv muted" id="s9b" style="text-align:center;font-size:44px;font-weight:600;margin-top:30px">Por isso a IA só recomenda.</div>
<div class="rv" id="s9c" style="text-align:center;font-size:62px;font-weight:800">Quem decide é sempre uma <span class="lime">pessoa</span>.</div>''',
    # s10 assinatura
    f'''<div class="ass">
  <img class="logo-big rv" id="s10logo" src="assets/logo.png" alt="" style="width:220px;height:220px;border-radius:52px">
  <h1 class="rv" id="s10n" style="font-size:120px">Sentinela</h1>
  <div class="rv muted" id="s10p" style="font-size:44px;font-weight:600;max-width:820px;line-height:1.3">Proteção de saques antes de o dinheiro sair</div>
  <div class="traco" id="s10tr" style="margin-top:70px"></div>
  <div class="rv" id="s10c" style="font-size:64px;font-weight:800">Caio Esteves</div>
  <div class="rv mono muted" id="s10s" style="font-size:28px;letter-spacing:.14em">DESAFIO DE INOVAÇÃO · YOUSHOP 2027</div>
</div>''',
]

# legendas: frases do roteiro quebradas em pedaços de até 34 caracteres, com tempo da primeira palavra
DESTAQUES = {"fraude?", "Sentinela.", "retém", "LightGBM,", "Gemini,", "51%", "85%", "52%", "94%", "7", "pessoa."}
caps = []
FRACAS = {"a", "o", "e", "de", "do", "da", "na", "no", "em", "um", "uma", "com", "que", "os", "as", "dos", "das", "ao"}


def quebra(ws):
    """Divide uma frase em legendas de até 44 caracteres.
    Prefere quebrar depois de vírgula/dois-pontos e nunca termina em palavra fraca ("na", "e", "de")."""
    if len(" ".join(w for _, _, w in ws)) <= 44 or len(ws) < 2:
        return [ws]
    melhor = None
    for k in range(1, len(ws)):
        esq = " ".join(w for _, _, w in ws[:k])
        if len(esq) > 44:
            break
        if ws[k - 1][2].lower() in FRACAS or len(" ".join(w for _, _, w in ws[k:])) < 12:
            continue  # nem palavra fraca no fim, nem palavra órfã na legenda seguinte
        nota = len(esq) + (30 if ws[k - 1][2].endswith((",", ":", ";")) else 0)
        if melhor is None or nota >= melhor[0]:
            melhor = (nota, k)
    k = melhor[1] if melhor else max(1, len(ws) // 2)
    return quebra(ws[:k]) + quebra(ws[k:])


for f in FR:
    ws = f["palavras"]
    # o "7" do clímax não pode aparecer na legenda antes da hora: vira legenda própria
    corte = next((i for i, w in enumerate(ws) if w[2] == "7"), None)
    partes = [ws[:corte], ws[corte:]] if corte else [ws]
    for parte in partes:
        for ped in quebra(parte):
            caps.append([ped[0][0], [(w, b) for _, b, w in ped]])
caps_html, caps_js = [], []
for k, (ini, ped) in enumerate(caps):
    prox = caps[k + 1][0] if k + 1 < len(caps) else DUR
    fim = min(prox, ped[-1][1] + 0.6)
    texto = " ".join(f"<em>{html.escape(w)}</em>" if w in DESTAQUES else html.escape(w) for w, _ in ped)
    caps_html.append(f'<div class="clip cap" id="cap{k}" data-start="{ini:.2f}" data-duration="{fim - ini:.2f}" '
                     f'data-track-index="3"><span>{texto}</span></div>')
    caps_js.append(f'tl.fromTo("#cap{k} span",{{opacity:0}},{{opacity:1,duration:.12,ease:"none"}},{ini:.2f});')

secoes = "\n".join(
    f'<section class="clip" id="s{i + 1}" data-start="{C[i]:.2f}" data-duration="{C[i + 1] - C[i]:.2f}" data-track-index="1">'
    f'<div class="wrap" id="w{i + 1}">{c}</div></section>' for i, c in enumerate(CENAS))

pagina = f'''<!doctype html>
<html lang="pt-BR" data-resolution="portrait">
<head><meta charset="UTF-8"><meta name="viewport" content="width=1080, height=1920">
<script src="vendor/gsap.min.js"></script><link rel="stylesheet" href="style.css"></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{DUR}">
  <div id="glow"></div><div id="grid"></div>
  <div id="hud"><img src="assets/logo.png" alt=""><b>SENTINELA</b><span>· YOUSHOP 2027</span></div>
  {secoes}
  {"".join(caps_html)}
  <div id="prog"></div>
  <audio id="mix" src="assets/mix.m4a" data-start="0" data-duration="{DUR}" data-track-index="2"></audio>
</div>
<script>const T = {json.dumps(T)}; const C = {json.dumps(C)}; const DUR = {DUR}; const FRAUDE_DOTS = {FRAUDE_DOTS};</script>
<script src="timeline.js"></script>
<script>{"".join(caps_js)} window.__timelines["main"] = tl; tl.seek(0);</script>
</body></html>
'''
(D / "index.html").write_text(pagina, encoding="utf-8")
print("ok index.html", len(caps), "legendas")
print(json.dumps(T, ensure_ascii=False))
