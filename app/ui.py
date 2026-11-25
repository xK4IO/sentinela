"""Identidade visual do Sentinela: paleta YouShop, CSS, ícones SVG e componentes HTML.

Tudo que é "visual puro" fica aqui. O arquivo de tela só monta as peças.
"""
from __future__ import annotations

import base64
import html as _h
from pathlib import Path

NAVY = "#1B2F52"
NAVY_2 = "#2C4775"
LIME = "#8CD43A"
LIME_TINT = "#EEF8E3"
INK = "#1F2A44"
MUTED = "#6B7A90"
BORDER = "#E3E8EF"
SUBTLE = "#EEF2F7"
BG = "#F5F7FA"

# Escala de risco (0 → 1): verde → âmbar → laranja → vermelho
_ESCALA = [(0.00, (124, 194, 58)), (0.40, (233, 162, 59)), (0.70, (232, 116, 59)), (1.00, (217, 68, 63))]


def cor_risco(p: float) -> str:
    p = max(0.0, min(1.0, float(p or 0)))
    for (a, ca), (b, cb) in zip(_ESCALA, _ESCALA[1:]):
        if p <= b:
            t = (p - a) / (b - a)
            r, g, bl = (round(x + (y - x) * t) for x, y in zip(ca, cb))
            return f"#{r:02x}{g:02x}{bl:02x}"
    return "#d9443f"


def pct(p: float | None, risco: bool = False) -> str:
    """risco=True limita a 99%: um modelo nunca tem certeza absoluta, e '100%' passaria essa ideia."""
    if p is None:
        return "—"
    v = round(float(p) * 100)
    return f"{min(v, 99) if risco else v:d}%"


def _img_svg(svg: str, w: int, h: int, extra: str = "") -> str:
    """st.html remove <svg> embutido por segurança; como imagem (data URI) ele é aceito.
    Animações vão DENTRO do SVG (<style>), porque o CSS da página não alcança o conteúdo da imagem."""
    b64 = base64.b64encode(svg.encode()).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" width="{w}" height="{h}" alt="" {extra}>'


def esc(s) -> str:
    return _h.escape(str(s))


def logo_b64() -> str:
    return base64.b64encode((Path(__file__).parent / "logo.png").read_bytes()).decode()


# ------------------------------------------------------------------------------ ícones
_PATHS = {
    "hourglass": '<path d="M6 2h12M6 22h12M7 2c0 5 5 6 5 10s-5 5-5 10M17 2c0 5-5 6-5 10s5 5 5 10"/>',
    "wallet": '<path d="M3 7a2 2 0 0 1 2-2h13v4"/><path d="M3 7v11a2 2 0 0 0 2 2h15V9H5a2 2 0 0 1-2-2z"/><circle cx="16" cy="14.5" r="1.2"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z"/>',
    "shield-check": '<path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    "users": '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.6c2.4.2 4 1.8 4.5 4.4"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.6v.2"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.3"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
}


def icon(nome: str, tam: int = 16, cor: str = MUTED) -> str:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{tam}" height="{tam}" viewBox="0 0 24 24" fill="none" '
           f'stroke="{cor}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{_PATHS[nome]}</svg>')
    return _img_svg(svg, tam, tam, 'style="flex:none;vertical-align:middle"')


# ------------------------------------------------------------------------------ CSS global
CSS = f"""
<style>
:root {{ --navy:{NAVY}; --lime:{LIME}; --ink:{INK}; --muted:{MUTED}; --border:{BORDER}; --subtle:{SUBTLE}; }}
header[data-testid="stHeader"] {{ background: transparent; height: 0; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer {{ display: none !important; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none; }}
.block-container {{ padding-top: 1.25rem !important; padding-bottom: 4rem !important; max-width: 1280px; }}

@keyframes sx-rise {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes sx-grow {{ from {{ width: 0; }} }}
@keyframes sx-ring {{ from {{ stroke-dashoffset: var(--len); }} }}
@keyframes sx-pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .45; }} }}

/* barra superior */
.sx-top {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:6px; animation: sx-rise .4s ease both; }}
.sx-brand {{ display:flex; align-items:center; gap:12px; }}
.sx-brand img {{ width:40px; height:40px; border-radius:10px; }}
.sx-brand b {{ display:block; font-size:1.15rem; font-weight:800; color:var(--navy); letter-spacing:-.01em; }}
.sx-brand span {{ font-size:.8rem; color:var(--muted); }}
.sx-chip {{ display:inline-flex; align-items:center; gap:6px; padding:5px 11px; border-radius:999px; background:#fff;
           border:1px solid var(--border); font-size:.78rem; color:var(--muted); font-weight:500; white-space:nowrap; }}
.sx-dot {{ width:7px; height:7px; border-radius:50%; background:var(--lime); animation: sx-pulse 2.4s ease-in-out infinite; }}

/* navegação (segmented control) */
div[data-testid="stButtonGroup"] button {{ font-weight:600; }}
div[data-testid="stButtonGroup"] button[aria-checked="true"], div[data-testid="stButtonGroup"] button[kind*="Active"] {{
  box-shadow: inset 0 -2px 0 var(--lime); }}

/* títulos de seção */
.sx-h {{ display:flex; align-items:baseline; justify-content:space-between; margin:18px 0 10px; }}
.sx-h h3 {{ margin:0; font-size:1.02rem; font-weight:700; color:var(--navy); }}
.sx-h span {{ font-size:.8rem; color:var(--muted); }}

/* KPIs */
.sx-kpis {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap:12px; margin:8px 0 4px; }}
.sx-kpi {{ background:#fff; border:1px solid var(--border); border-radius:14px; padding:16px 18px; position:relative;
          overflow:hidden; animation: sx-rise .45s ease both; transition: box-shadow .2s, transform .2s; }}
.sx-kpi:hover {{ box-shadow: 0 6px 22px rgba(27,47,82,.07); transform: translateY(-1px); }}
.sx-kpi .lbl {{ display:flex; align-items:center; gap:7px; color:var(--muted); font-size:.8rem; font-weight:600; }}
.sx-kpi .val {{ font-size:1.65rem; font-weight:800; color:var(--navy); letter-spacing:-.02em; margin-top:6px; line-height:1.15; }}
.sx-kpi .sub {{ font-size:.78rem; color:var(--muted); margin-top:4px; }}
.sx-kpi.accent::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--lime); }}
.sx-bar {{ height:6px; background:var(--subtle); border-radius:99px; margin-top:10px; position:relative; overflow:visible; }}
.sx-bar > i {{ display:block; height:100%; border-radius:99px; animation: sx-grow .9s cubic-bezier(.2,.7,.2,1) both; }}
.sx-bar > em {{ position:absolute; top:-4px; width:2px; height:14px; background:var(--navy); opacity:.55; border-radius:2px; }}

/* linhas da fila */
div[class*="st-key-row_"] {{ background:#fff; border:1px solid var(--border); border-radius:14px; padding:12px 16px 12px 14px;
  animation: sx-rise .4s ease both; transition: box-shadow .2s ease, border-color .2s ease, transform .2s ease; }}
div[class*="st-key-row_"]:hover {{ border-color:#C9D3E0; box-shadow: 0 8px 26px rgba(27,47,82,.08); transform: translateY(-1px); }}
div[class*="st-key-row_"] button {{ white-space:nowrap; }}
.sx-row {{ display:grid; grid-template-columns: 58px minmax(220px, 2.4fr) 1fr 1fr 1.15fr; align-items:center; gap:14px; }}
.sx-who b {{ color:var(--navy); font-weight:700; font-size:.95rem; }}
.sx-who small {{ color:var(--muted); font-weight:500; margin-left:6px; }}
.sx-tags {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }}
.sx-tag {{ font-size:.72rem; font-weight:600; color:{NAVY_2}; background:var(--subtle); padding:3px 9px; border-radius:999px; }}
.sx-tag.model {{ background:#F1EEFB; color:#5B4B9A; }}
.sx-cell small {{ display:block; color:var(--muted); font-size:.72rem; font-weight:500; margin-bottom:2px; }}
.sx-cell b {{ color:var(--ink); font-weight:700; font-size:.92rem; }}
.sx-cell .warn {{ color:#C0571F; }}
.sx-cell .row {{ display:flex; align-items:center; gap:6px; }}
.sx-status {{ display:inline-flex; align-items:center; gap:6px; font-size:.82rem; font-weight:600; color:var(--ink); }}
.sx-status i {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
@media (max-width: 900px) {{ .sx-row {{ grid-template-columns: 52px 1fr 1fr; }} .sx-row .hide-sm {{ display:none; }} }}

/* anel de risco */
.sx-ring {{ position:relative; width:52px; height:52px; }}
.sx-ring svg circle.v {{ animation: sx-ring 1s cubic-bezier(.2,.7,.2,1) both; }}
.sx-ring span {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:.8rem; font-weight:800; color:var(--ink); }}

/* caixas nativas do Streamlit com visual de cartão (st.container(key="box_...")) */
div[class*="st-key-box_"] {{ background:#fff; border:1px solid var(--border); border-radius:16px; padding:16px 18px;
  animation: sx-rise .45s ease both; }}
div[class*="st-key-box_"] .sx-card {{ border:none; padding:0; animation:none; }}

/* cartões genéricos */
.sx-card {{ background:#fff; border:1px solid var(--border); border-radius:16px; padding:18px 20px; animation: sx-rise .45s ease both; }}
.sx-card p {{ margin:0; color:var(--ink); line-height:1.6; }}
.sx-card .eyebrow {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; font-weight:700; color:var(--muted); margin-bottom:8px; display:flex; align-items:center; gap:6px; }}

/* cabeçalho do caso */
.sx-case {{ display:grid; grid-template-columns: 1fr auto; gap:24px; align-items:center; }}
.sx-case h1 {{ font-size:1.6rem; font-weight:800; color:var(--navy); margin:2px 0 6px; letter-spacing:-.02em; padding:0; }}
.sx-meta {{ display:flex; flex-wrap:wrap; gap:8px 18px; color:var(--muted); font-size:.85rem; }}
.sx-meta b {{ color:var(--ink); font-weight:700; }}
.sx-gauge {{ text-align:center; }}
.sx-gauge path.v {{ animation: sx-ring 1.1s cubic-bezier(.2,.7,.2,1) both; }}
.sx-gauge .num {{ font-size:1.7rem; font-weight:800; color:var(--navy); margin-top:-34px; }}
.sx-gauge .cap {{ font-size:.75rem; color:var(--muted); font-weight:600; }}
.sx-split {{ display:flex; gap:14px; justify-content:center; margin-top:6px; font-size:.74rem; color:var(--muted); }}

/* indicadores do caso */
.sx-facts {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(190px,1fr)); gap:12px; margin-top:12px; }}
.sx-fact {{ background:#fff; border:1px solid var(--border); border-radius:14px; padding:14px 16px; animation: sx-rise .45s ease both; }}
.sx-fact small {{ display:flex; align-items:center; gap:6px; color:var(--muted); font-size:.75rem; font-weight:600; }}
.sx-fact b {{ display:block; margin-top:6px; font-size:1.05rem; font-weight:800; color:var(--navy); }}
.sx-pill {{ display:inline-flex; align-items:center; gap:6px; padding:4px 11px; border-radius:999px; font-size:.85rem; font-weight:700; }}
.sx-pill.hold {{ background:#FDECEB; color:#B23A35; }}
.sx-pill.free {{ background:{LIME_TINT}; color:#3E7A12; }}
.sx-meter {{ display:flex; gap:4px; margin-top:8px; }}
.sx-meter i {{ flex:1; height:6px; border-radius:99px; background:var(--subtle); }}
.sx-meter i.on {{ background:var(--navy); }}

/* avisos */
.sx-note {{ display:flex; gap:10px; align-items:flex-start; padding:12px 14px; border-radius:12px; background:#FFF6EC;
           border:1px solid #F6DFC4; color:#7A4A14; font-size:.86rem; margin-top:12px; animation: sx-rise .4s ease both; }}
.sx-note.info {{ background:#F0F5FC; border-color:#D9E4F3; color:{NAVY_2}; }}

/* provas */
.sx-proof {{ display:flex; gap:12px; align-items:flex-start; }}
.sx-proof .n {{ flex:0 0 26px; height:26px; border-radius:8px; background:var(--navy); color:#fff; font-size:.78rem; font-weight:800;
               display:flex; align-items:center; justify-content:center; margin-top:1px; }}
.sx-proof p {{ margin:0; line-height:1.55; color:var(--ink); }}

/* barras horizontais (fatores, tipos) */
.sx-hbars {{ display:flex; flex-direction:column; gap:12px; }}
.sx-hbar .t {{ display:flex; justify-content:space-between; gap:10px; font-size:.84rem; color:var(--ink); font-weight:600; }}
.sx-hbar .t span {{ color:var(--muted); font-weight:500; font-size:.78rem; white-space:nowrap; }}
.sx-hbar .b {{ height:8px; background:var(--subtle); border-radius:99px; margin-top:6px; }}
.sx-hbar .b > i {{ display:block; height:100%; border-radius:99px; animation: sx-grow .9s cubic-bezier(.2,.7,.2,1) both; }}

/* tabela simples */
.sx-table {{ width:100%; border-collapse:separate; border-spacing:0; background:#fff; border:1px solid var(--border); border-radius:14px; overflow:hidden; font-size:.86rem; }}
.sx-table th {{ text-align:left; color:var(--muted); font-weight:600; font-size:.75rem; padding:11px 14px; background:#FAFBFD; border-bottom:1px solid var(--border); }}
.sx-table td {{ padding:12px 14px; border-bottom:1px solid var(--border); color:var(--ink); vertical-align:top; }}
.sx-table tr:last-child td {{ border-bottom:none; }}
.sx-table tr {{ animation: sx-rise .4s ease both; }}

/* expanders, formulários e mensagens */
div[data-testid="stExpander"] details {{ border-radius:12px; background:#fff; }}
div[data-testid="stExpander"] summary p {{ font-weight:600; font-size:.86rem; color:{NAVY_2}; }}
div[data-testid="stForm"] {{ background:#fff; border-radius:16px; }}
.sx-msg {{ background:var(--subtle); border-radius:12px; padding:12px 14px; font-size:.86rem; color:var(--ink); margin-top:8px; }}
.sx-msg small {{ display:block; color:var(--muted); font-weight:600; margin-bottom:4px; font-size:.74rem; }}

@media (prefers-reduced-motion: reduce) {{ *, *::before {{ animation: none !important; transition: none !important; }} }}
</style>
"""


# ------------------------------------------------------------------------------ componentes
def topo(analista: str, relogio: str) -> str:
    return (f'<div class="sx-top"><div class="sx-brand"><img src="data:image/png;base64,{logo_b64()}" alt="YouShop">'
            f'<div><b>Sentinela</b><span>Proteção de saques · Operações</span></div></div>'
            f'<div style="display:flex;gap:8px;flex-wrap:wrap">'
            f'<span class="sx-chip"><i class="sx-dot"></i>Monitorando saques</span>'
            f'<span class="sx-chip">{icon("clock", 13)}{esc(relogio)}</span>'
            f'<span class="sx-chip">{icon("users", 13)}{esc(analista)}</span></div></div>')


def titulo(texto: str, sub: str = "") -> str:
    return f'<div class="sx-h"><h3>{esc(texto)}</h3><span>{esc(sub)}</span></div>'


def kpi(rotulo: str, valor: str, sub: str = "", ic: str = "layers", accent: bool = False,
        barra: float | None = None, cor_barra: str = NAVY, meta: float | None = None, atraso: int = 0) -> str:
    bar = ""
    if barra is not None:
        marca = f'<em style="left:{meta * 100:.1f}%"></em>' if meta is not None else ""
        bar = f'<div class="sx-bar"><i style="width:{max(0, min(1, barra)) * 100:.1f}%;background:{cor_barra}"></i>{marca}</div>'
    return (f'<div class="sx-kpi{" accent" if accent else ""}" style="animation-delay:{atraso}ms">'
            f'<div class="lbl">{icon(ic, 15)}{esc(rotulo)}</div><div class="val">{esc(valor)}</div>'
            f'<div class="sub">{esc(sub)}</div>{bar}</div>')


def kpis(cartoes: list[str]) -> str:
    return f'<div class="sx-kpis">{"".join(cartoes)}</div>'


_ANIM = ("<style>@keyframes f{{from{{stroke-dashoffset:{L:.1f}}}}}.v{{animation:f 1.1s cubic-bezier(.2,.7,.2,1) both}}"
         "@media (prefers-reduced-motion:reduce){{.v{{animation:none}}}}</style>")


def anel(p: float, tam: int = 52) -> str:
    """Anel de risco: cor e preenchimento seguem a escala verde → vermelho."""
    r = 21
    c = 2 * 3.14159 * r
    vis = min(max(0.0, float(p or 0)), 0.99)
    off = c * (1 - vis)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">{_ANIM.format(L=c)}'
           f'<circle cx="26" cy="26" r="{r}" fill="none" stroke="{SUBTLE}" stroke-width="5"/>'
           f'<circle class="v" cx="26" cy="26" r="{r}" fill="none" stroke="{cor_risco(p)}" stroke-width="5" '
           f'stroke-linecap="round" stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.1f}" transform="rotate(-90 26 26)"/></svg>')
    return (f'<div class="sx-ring" style="width:{tam}px;height:{tam}px">{_img_svg(svg, tam, tam)}'
            f'<span>{pct(p, risco=True)}</span></div>')


def medidor(p: float, modelo: float | None, regras: float) -> str:
    """Semicírculo com o gradiente da escala de risco."""
    L = 3.14159 * 70
    off = L * (1 - min(max(0.0, float(p or 0)), 0.99))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="180" height="104" viewBox="0 0 180 104">{_ANIM.format(L=L)}'
           f'<defs><linearGradient id="gr" gradientUnits="userSpaceOnUse" x1="20" y1="0" x2="160" y2="0">'
           f'<stop offset="0" stop-color="{cor_risco(0)}"/><stop offset=".45" stop-color="{cor_risco(.45)}"/>'
           f'<stop offset=".75" stop-color="{cor_risco(.75)}"/><stop offset="1" stop-color="{cor_risco(1)}"/>'
           f'</linearGradient></defs>'
           f'<path d="M20 94 A70 70 0 0 1 160 94" fill="none" stroke="{SUBTLE}" stroke-width="12" stroke-linecap="round"/>'
           f'<path class="v" d="M20 94 A70 70 0 0 1 160 94" fill="none" stroke="url(#gr)" stroke-width="12" '
           f'stroke-linecap="round" stroke-dasharray="{L:.1f}" stroke-dashoffset="{off:.1f}"/></svg>')
    return (f'<div class="sx-gauge">{_img_svg(svg, 180, 104)}'
            f'<div class="num">{pct(p, risco=True)}</div><div class="cap">Risco do saque</div>'
            f'<div class="sx-split"><span>Modelo {pct(modelo, risco=True)}</span><span>Regras {pct(regras)}</span></div></div>')


def tags(itens: list[str], modelo: bool = False) -> str:
    return "".join(f'<span class="sx-tag{" model" if modelo else ""}">{esc(t)}</span>' for t in itens)


def linha_fila(r: dict) -> str:
    if r.get("horas") is None:
        prazo = f'<div class="row">{icon("check", 14)}<b>Saque pago</b></div>'
    else:
        prazo_h = int(r["horas"])
        urgente = prazo_h < r.get("urgente", 9)
        prazo = (f'<div class="row">{icon("hourglass", 14, "#C0571F" if urgente else MUTED)}'
                 f'<b class="{"warn" if urgente else ""}">{prazo_h} h úteis</b></div>')
    if r["relatorio"] == "obs":
        st_cor, st_txt = "#E9A23B", "Em observação"
    elif r["relatorio"] == "pronto":
        st_cor, st_txt = LIME, f"Pronto · confiança {r['confianca']}"
    elif r["relatorio"] == "parcial":
        st_cor, st_txt = "#E9A23B", "Parcial · revisar"
    else:
        st_cor, st_txt = "#C3CBD6", "Em preparação"
    return (f'<div class="sx-row"><div>{anel(r["risco"])}</div>'
            f'<div class="sx-who"><b>{esc(r["nome"])}</b><small>{esc(r["creator_id"])}</small>'
            f'<div class="sx-tags">{tags(r["sinais"], r["so_modelo"])}</div></div>'
            f'<div class="sx-cell"><small>Saque</small><b>{esc(r["valor"])}</b></div>'
            f'<div class="sx-cell hide-sm"><small>{"Situação" if r.get("horas") is None else "Prazo restante"}</small>{prazo}</div>'
            f'<div class="sx-cell hide-sm"><small>Relatório</small><span class="sx-status"><i style="background:{st_cor}"></i>'
            f'{esc(st_txt)}</span></div></div>')


def cabecalho_caso(nome: str, creator_id: str, meta: list[tuple[str, str]], risco: float,
                   modelo: float | None, regras: float) -> str:
    itens = "".join(f"<span>{esc(k)} <b>{esc(v)}</b></span>" for k, v in meta)
    return (f'<div class="sx-card"><div class="sx-case"><div>'
            f'<div class="eyebrow">{icon("shield", 13)}Saque em análise · {esc(creator_id)}</div>'
            f'<h1>{esc(nome)}</h1><div class="sx-meta">{itens}</div></div>'
            f'{medidor(risco, modelo, regras)}</div></div>')


def fatos(cartoes: list[str]) -> str:
    return f'<div class="sx-facts">{"".join(cartoes)}</div>'


def fato(rotulo: str, conteudo: str, ic: str, atraso: int = 0) -> str:
    return (f'<div class="sx-fact" style="animation-delay:{atraso}ms"><small>{icon(ic, 14)}{esc(rotulo)}</small>'
            f'{conteudo}</div>')


def recomendacao(rec: str) -> str:
    if rec == "LIBERAR":
        return f'<div style="margin-top:6px"><span class="sx-pill free">{icon("check", 14)}Liberar saque</span></div>'
    return f'<div style="margin-top:6px"><span class="sx-pill hold">{icon("shield", 14)}Manter retido</span></div>'


def confianca(nivel: str) -> str:
    n = {"BAIXA": 1, "MEDIA": 2, "ALTA": 3}.get(nivel, 0)
    nome = {"BAIXA": "Baixa", "MEDIA": "Média", "ALTA": "Alta"}.get(nivel, "—")
    barras = "".join(f'<i class="{"on" if i < n else ""}"></i>' for i in range(3))
    return f'<b>{nome}</b><div class="sx-meter">{barras}</div>'


def aviso(texto: str, tipo: str = "warn") -> str:
    return f'<div class="sx-note {"info" if tipo == "info" else ""}">{icon("info", 17)}<div>{texto}</div></div>'


def cartao(eyebrow: str, corpo_html: str, ic: str = "file", atraso: int = 0) -> str:
    return (f'<div class="sx-card" style="animation-delay:{atraso}ms"><div class="eyebrow">{icon(ic, 13)}{esc(eyebrow)}</div>'
            f'{corpo_html}</div>')


def prova(n: int, texto: str) -> str:
    return f'<div class="sx-proof"><div class="n">{n}</div><p>{esc(texto)}</p></div>'


def barras_fatores(itens: list[dict]) -> str:
    """itens: {rotulo, valor_txt, impacto (0-1), aumenta (bool)}"""
    if not itens:
        return '<p style="color:var(--muted)">Fatores indisponíveis.</p>'
    linhas = []
    for i, x in enumerate(itens):
        cor = cor_risco(.85) if x["aumenta"] else cor_risco(.05)
        efeito = "eleva o risco" if x["aumenta"] else "reduz o risco"
        linhas.append(f'<div class="sx-hbar"><div class="t">{esc(x["rotulo"])}<span>{esc(x["valor_txt"])} · {efeito}</span></div>'
                      f'<div class="b"><i style="width:{max(4, x["impacto"] * 100):.0f}%;background:{cor};'
                      f'animation-delay:{i * 120}ms"></i></div></div>')
    return f'<div class="sx-hbars">{"".join(linhas)}</div>'


def barras_simples(itens: list[tuple[str, int]], cor: str = NAVY) -> str:
    """Contagens comparadas entre si (a maior barra = 100%)."""
    m = max((v for _, v in itens), default=1) or 1
    return '<div class="sx-hbars">' + "".join(
        f'<div class="sx-hbar"><div class="t">{esc(k)}<span>{v}</span></div><div class="b">'
        f'<i style="width:{v / m * 100:.0f}%;background:{cor};animation-delay:{i * 90}ms"></i></div></div>'
        for i, (k, v) in enumerate(itens)) + "</div>"


def barras_proporcao(itens: list[tuple[str, int, int]], cor: str = NAVY) -> str:
    """Cada barra é uma proporção própria (x de n), para comparar taxas e não volumes."""
    return '<div class="sx-hbars">' + "".join(
        f'<div class="sx-hbar"><div class="t">{esc(k)}<span>{x} de {n} · {pct(x / max(1, n))}</span></div>'
        f'<div class="b"><i style="width:{x / max(1, n) * 100:.0f}%;background:{cor};animation-delay:{i * 90}ms"></i>'
        f'</div></div>' for i, (k, x, n) in enumerate(itens)) + "</div>"


def tabela(cab: list[str], linhas: list[list[str]]) -> str:
    th = "".join(f"<th>{esc(c)}</th>" for c in cab)
    trs = "".join(f'<tr style="animation-delay:{i * 40}ms">' + "".join(f"<td>{c}</td>" for c in l) + "</tr>"
                  for i, l in enumerate(linhas))
    return f'<table class="sx-table"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'
