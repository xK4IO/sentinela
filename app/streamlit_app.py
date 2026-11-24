"""Sentinela · interface do analista de Operações (Streamlit).

Rodar localmente:  streamlit run app/streamlit_app.py

Telas (wireframes da seção 6 do doc de negócio):
  Fila principal → Dossiê do caso (evidências + SQL, SHAP, rede de contas, decisão)
  Monitoramento (MÉDIO) · Decididos · Métricas (modo demo, compara com o gabarito)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import config as C  # noqa: E402
from agent.prompts import rotulo  # noqa: E402
from app import dados as D  # noqa: E402

AZUL = "#2a78d6"        # tom único para magnitude (barras)
AZUL_CLARO = "#cde2fb"
CINZA = "#f0efec"

st.set_page_config(page_title="Sentinela · Operações", page_icon="🛡️", layout="wide")


# ---------------------------------------------------------------------------- dados (cache)
@st.cache_data(ttl=60)
def _fila():
    return D.fila_principal(D.conectar())


@st.cache_data(ttl=60)
def _monit():
    return D.monitoramento(D.conectar())


@st.cache_data(ttl=60)
def _decididos():
    return D.decididos(D.conectar())


@st.cache_data(ttl=60)
def _metricas():
    return D.metricas(D.conectar())


def _limpar_cache():
    for f in (_fila, _monit, _decididos, _metricas):
        f.clear()


# ---------------------------------------------------------------------------- barra lateral
with st.sidebar:
    st.markdown("### 🛡️ Sentinela")
    st.caption("Copiloto antifraude para saques de creators")
    analista = st.text_input("Analista", value=st.session_state.get("analista", "Analista demo"))
    st.session_state["analista"] = analista
    st.divider()
    st.caption(f"🕒 Relógio da demo: **{D.AGORA_DEMO:%d/%m/%Y %H:%M}**")
    st.info("Protótipo com **dados sintéticos**. Nenhum dado real de pessoas.", icon="ℹ️")
    if st.button("Desfazer todas as decisões", help="Volta todos os saques ALTO para RETIDO"):
        D.resetar_demo()
        _limpar_cache()
        st.session_state.pop("aberto", None)
        st.rerun()


# ---------------------------------------------------------------------------- componentes
def grafico_shap(shap: list[dict]):
    if not shap:
        st.caption("Fatores do modelo indisponíveis (modo degradado).")
        return
    df = pd.DataFrame([{
        "fator": rotulo(s["feature"]),
        "impacto": abs(s["shap"]),
        "direcao": "↑ aumenta o risco" if s["shap"] > 0 else "↓ reduz o risco",
        "valor": "sem informação" if s["valor"] is None else s["valor"],
    } for s in shap])
    df["rotulo"] = df.fator + "  (" + df.direcao + ")"
    ch = (alt.Chart(df).mark_bar(color=AZUL, cornerRadiusEnd=4, size=18)
          .encode(x=alt.X("impacto:Q", title="Peso na nota (|SHAP|)", axis=alt.Axis(grid=False)),
                  y=alt.Y("rotulo:N", sort="-x", title=None, axis=alt.Axis(labelLimit=420)),
                  tooltip=[alt.Tooltip("fator:N", title="Fator"), alt.Tooltip("valor:N", title="Valor do creator"),
                           alt.Tooltip("direcao:N", title="Efeito"), alt.Tooltip("impacto:Q", title="|SHAP|", format=".3f")])
          .properties(height=40 * len(df) + 30))
    st.altair_chart(ch, width="stretch")


def grafo_rede(rede: dict, investigado: str):
    if not rede or not rede.get("creators_ligados"):
        st.caption("Nenhuma conta ligada por chave Pix ou dispositivo de login.")
        return
    linhas = ['graph { rankdir=LR; bgcolor="transparent"; node [fontname="Helvetica", fontsize=11];',
              'edge [color="#8a8a86"];']
    for n in rede["nos"]:
        if n["tipo"] == "creator":
            cor, fonte = (AZUL, "white") if n["id"] == investigado else (AZUL_CLARO, "#0b0b0b")
            rot = f'{n["id"]}\\n(investigado)' if n["id"] == investigado else n["id"]
            linhas.append(f'"{n["id"]}" [label="{rot}", shape=box, style="filled,rounded", '
                          f'fillcolor="{cor}", fontcolor="{fonte}", color="{cor}"];')
        else:
            icone = "Chave Pix" if n["tipo"] == "pix" else "Dispositivo"
            linhas.append(f'"{n["id"]}" [label="{icone}\\n{n["rotulo"].split(" ", 1)[-1]}", shape=ellipse, '
                          f'style=filled, fillcolor="{CINZA}", color="#c3c2b7"];')
    for a, b in rede["arestas"]:
        linhas.append(f'"{a}" -- "{b}";')
    linhas.append("}")
    st.graphviz_chart("\n".join(linhas), width="stretch")
    partes = []
    if rede.get("mesma_pix"):
        partes.append(f"**{len(rede['mesma_pix']) + 1} contas** sacam para a mesma chave Pix")
    if rede.get("mesmo_disp"):
        partes.append(f"**{len(rede['mesmo_disp'])}** fazem login em dispositivo do investigado")
    st.caption("Lê-se: " + " · ".join(partes) + ".")


def tabela_evidencia(ev: dict):
    if ev.get("sql"):
        st.code(ev["sql"], language="sql")
    else:
        st.caption("Indicadores calculados pelo Sentinela (não é uma consulta do agente).")
    if ev.get("linhas"):
        st.dataframe(pd.DataFrame(ev["linhas"], columns=ev["colunas"]), hide_index=True, width="stretch")
    else:
        st.caption("Consulta sem resultados.")
    if ev.get("achado"):
        st.caption(f"Leitura do agente: {ev['achado']}")


MENSAGENS_CREATOR = {
    "RETIDO": "Seu saque de {valor} está em análise de segurança. Ele será concluído em até 48 horas úteis. "
              "Você não precisa fazer nada agora.",
    "LIBERAR": "Análise concluída. Seu saque foi liberado.",
    "NEGAR": "Seu saque não foi aprovado porque identificamos vendas com indício de irregularidade. "
             "Se discordar, você pode contestar a decisão.",
}


# ---------------------------------------------------------------------------- tela: dossiê
def tela_dossie(alerta_id: int):
    a = D.alerta(D.conectar(), alerta_id)
    det = a["detalhes"]
    if st.button("← Voltar para a fila"):
        st.session_state.pop("aberto", None)
        st.rerun()

    st.markdown(f"## Caso #A-{alerta_id} · Creator {a['creator_id']} ({a['nome'].split()[0]}) · "
                f"Saque {D.brl(a['valor'])}")
    st.caption(f"Pedido em {a['solicitado_em']:%d/%m/%Y %H:%M} · prazo restante: {int(a['horas_restantes'])} h · "
               f"nota de risco {a['score_final']:.2f} (modelo {a['prob_modelo'] or 0:.2f}, regras {a['score_regras']:.2f})")

    if det:
        c1, c2, c3 = st.columns(3)
        c1.metric("Recomendação da IA", D.REC[a["recomendacao"]])
        c2.metric("Confiança", D.CONF[a["confianca"]])
        c3.metric("Investigação", "Completa" if det.get("profundidade") == "completa" else "Direta",
                  help="Direta: modelo e regras concordam com força, então a IA só redige a partir das consultas "
                       "padrão. Completa: caso ambíguo, a IA levanta hipóteses e consulta o banco.")
        if det.get("fallback"):
            st.warning("Investigação automática indisponível: dossiê gerado só com os sinais calculados.", icon="⚠️")
        if det.get("numero_inventado"):
            st.warning("A IA citou valores que não foram confirmados pelas consultas. Confira as evidências.", icon="⚠️")
    else:
        st.warning("Dossiê ainda não gerado. Exibindo só regras e fatores do modelo (confiança **Baixa**).", icon="⚠️")

    col_esq, col_dir = st.columns([3, 2], gap="large")
    with col_esq:
        if det:
            st.markdown("#### Resumo")
            st.write(det["resumo"])
            st.markdown("#### Evidências")
            for i, x in enumerate(det["afirmacoes"], 1):
                st.markdown(f"**[{i}]** {x['texto']}")
                ev = a["evidencias"].get(x["evidencia_id"])
                if ev:
                    with st.expander(f"Ver consulta · {x['evidencia_id']} · {ev['titulo']}"):
                        tabela_evidencia(ev)
            st.markdown("#### Justificativa")
            st.write(det["justificativa"])
            llm_sql = [s for s in a["sql_executadas"] if s["origem"] == "llm"]
            if llm_sql:
                with st.expander(f"Log das consultas geradas pela IA ({len(llm_sql)})"):
                    for s in llm_sql:
                        icone = {"ok": "✅", "rejeitada": "⛔", "erro": "⚠️"}[s["status"]]
                        st.markdown(f"{icone} **{s['status']}** · {s.get('hipotese', '')}")
                        if s.get("motivo"):
                            st.caption(f"Motivo: {s['motivo']}")
                        st.code(s["sql"], language="sql")
        else:
            st.markdown("#### Regras disparadas")
            st.write(a["sinais"])
            st.markdown("#### Indicadores")
            st.dataframe(pd.DataFrame([{"indicador": rotulo(k), "valor": "sem informação" if v is None else v}
                                       for k, v in a["features"].items()]), hide_index=True)

    with col_dir:
        st.markdown("#### Por que a nota ficou alta")
        grafico_shap(a["shap"])
        st.markdown("#### Rede de contas")
        rede = det["rede"] if det else D.rede_sem_dossie(a["creator_id"], f"{a['solicitado_em']:%Y-%m-%d %H:%M:%S}")
        grafo_rede(rede, a["creator_id"])

    st.divider()
    st.markdown("#### Decisão")
    if a["status"] != "RETIDO":
        st.success(f"Caso já decidido: saque **{a['status']}**.")
        return
    with st.form("decisao"):
        decisao = st.radio("Decisão", ["LIBERAR", "NEGAR"], horizontal=True, index=None,
                           format_func=lambda x: "Liberar saque" if x == "LIBERAR" else "Negar saque")
        comentario = st.text_area("Comentário (obrigatório)", placeholder="Por que você decidiu assim?")
        enviar = st.form_submit_button("Confirmar decisão", type="primary")
    if decisao:
        st.caption("Mensagem que o creator vai receber:")
        st.info(MENSAGENS_CREATOR[decisao])
    if enviar:
        if not decisao:
            st.error("Escolha Liberar ou Negar.")
        elif not comentario.strip():
            st.error("O comentário é obrigatório: toda decisão fica registrada para auditoria.")
        else:
            dossie_id = None if pd.isna(a["dossie_id"]) else int(a["dossie_id"])
            D.registrar_decisao(alerta_id, dossie_id, st.session_state["analista"], decisao, comentario)
            _limpar_cache()
            st.session_state.pop("aberto", None)
            st.toast(f"Decisão registrada: {'saque liberado' if decisao == 'LIBERAR' else 'saque negado'}.", icon="✅")
            st.rerun()


# ---------------------------------------------------------------------------- tela: abas
def tabela_alertas(df: pd.DataFrame, chave: str, selecionavel: bool = True):
    vis = pd.DataFrame({
        "Risco": df.faixa_risco,
        "Creator": df.creator_id + " " + df.nome.str.split().str[0],
        "Saque": df.valor,
        "Nota": df.score_final,
        "Sinais": df.sinais,
        "Dossiê": [("—" if pd.isna(c) else ("⚠️ Baixa" if fb else D.CONF[c]))
                   for c, fb in zip(df.confianca, df.fallback)],
        "Prazo": df.horas_restantes.astype(int).astype(str) + " h" +
                 df.horas_restantes.lt(12).map({True: " ⚠️", False: ""}),
    })
    cfg = {"Saque": st.column_config.NumberColumn(format="R$ %.2f"),
           "Nota": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f")}
    if not selecionavel:
        vis = vis.drop(columns=["Dossiê", "Prazo"])
        return st.dataframe(vis, hide_index=True, width="stretch", column_config=cfg)
    ev = st.dataframe(vis, hide_index=True, width="stretch", column_config=cfg,
                      on_select="rerun", selection_mode="single-row", key=chave)
    if ev.selection.rows:
        st.session_state["aberto"] = int(df.iloc[ev.selection.rows[0]].alerta_id)
        st.rerun()


def aba_fila():
    df = _fila()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Retidos aguardando decisão", len(df))
    c2.metric("Valor retido", D.brl(df.valor.sum()))
    c3.metric("Prazo vencendo (< 12 h)", int(df.horas_restantes.lt(12).sum()))
    c4.metric("Dossiês prontos", f"{df.dossie_id.notna().sum()} de {len(df)}")

    f1, f2, f3 = st.columns([2, 1, 1])
    regras = f1.multiselect("Regra", list(D.NOMES_REGRAS.values()), placeholder="Todas")
    vmin = f2.number_input("Valor mínimo (R$)", min_value=0.0, step=50.0)
    busca = f3.text_input("Buscar creator", placeholder="C0417")
    if regras:
        df = df[df.sinais.apply(lambda s: any(r in s for r in regras))]
    df = df[df.valor >= vmin]
    if busca.strip():
        df = df[df.creator_id.str.contains(busca.strip(), case=False) | df.nome.str.contains(busca.strip(), case=False)]
    st.caption("Clique numa linha para abrir o dossiê.")
    tabela_alertas(df.reset_index(drop=True), "fila")


def aba_monitoramento():
    df = _monit()
    st.caption("Risco **médio**: o saque foi pago normalmente e o creator fica em observação. Sem dossiê.")
    tabela_alertas(df, "monit", selecionavel=False)


def aba_decididos():
    df = _decididos()
    if df.empty:
        st.caption("Nenhuma decisão registrada ainda.")
        return
    df = df.assign(decisao=df.decisao.map({"LIBERAR": "Liberado", "NEGAR": "Negado"}),
                   recomendacao=df.recomendacao.map(D.REC).fillna("—"))
    df["IA × analista"] = [("✅ concordou" if (d == "Liberado") == (r == "Liberar") else "↔ divergiu")
                           if r != "—" else "—" for d, r in zip(df.decisao, df.recomendacao)]
    st.dataframe(df.drop(columns=["alerta_id"]).rename(columns={
        "decidido_em": "Quando", "analista": "Analista", "creator_id": "Creator", "valor": "Saque",
        "decisao": "Decisão", "recomendacao": "Recomendação da IA", "comentario": "Comentário"}),
        hide_index=True, width="stretch",
        column_config={"Saque": st.column_config.NumberColumn(format="R$ %.2f")})


def aba_metricas():
    m = _metricas()
    st.caption("**Modo demo:** como a base é sintética, conhecemos a resposta certa (gabarito) e podemos medir "
               "o acerto exatamente. O gabarito nunca é mostrado ao agente nem nas outras telas.")
    c = st.columns(4)
    c[0].metric("Saques avaliados", f"{m['avaliados']:,}".replace(",", "."))
    c[1].metric("Retidos", m["retidos"], f"{m['retidos'] / m['avaliados']:.1%} dos saques", delta_color="off")
    c[2].metric("Eram fraude (precisão)", f"{m['precisao']:.0%}", f"{m['tp']} de {m['retidos']}", delta_color="off")
    c[3].metric("Fraudes pegas (recall)", f"{m['recall']:.0%}", f"{m['tp']} de {m['tp'] + m['fn']}", delta_color="off")
    c = st.columns(4)
    c[0].metric("R$ barrado de fraude", D.brl(m["rs_fraude"]))
    c[1].metric("R$ retido de legítimos", D.brl(m["rs_legitimo"]), f"{m['fp']} falsos alarmes", delta_color="off")
    c[2].metric("Virais retidos", m["virais_retidos"], "meta: no máximo 2", delta_color="off")
    if m["tempo_medio"] is not None:
        c[3].metric("Tempo médio por dossiê", f"{m['tempo_medio']:.0f} s", "meta: < 60 s", delta_color="off")

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Retidos por tipo (gabarito)")
        df = m["por_tipo"].rename_axis("tipo").reset_index(name="retidos")
        ch = (alt.Chart(df).mark_bar(color=AZUL, cornerRadiusEnd=4, size=18)
              .encode(x=alt.X("retidos:Q", title="Saques retidos", axis=alt.Axis(grid=False, tickMinStep=1)),
                      y=alt.Y("tipo:N", sort="-x", title=None, axis=alt.Axis(labelLimit=300)),
                      tooltip=[alt.Tooltip("tipo:N", title="Tipo"), alt.Tooltip("retidos:Q", title="Retidos")])
              .properties(height=36 * len(df) + 30))
        st.altair_chart(ch, width="stretch")
        with st.expander("Ver como tabela"):
            st.dataframe(df, hide_index=True)
    with col2:
        st.markdown("#### Agente e decisões")
        st.metric("Dossiês gerados", f"{m['dossies_ok']} de {m['retidos']}")
        if m["pct_numero_inventado"] is not None:
            st.metric("Dossiês com número não confirmado", f"{m['pct_numero_inventado']:.1%}", "meta: ≤ 5%",
                      delta_color="off")
        st.metric("Decisões do analista", m["decisoes"], f"{m['liberados']} liberados · {m['negados']} negados",
                  delta_color="off")


# ---------------------------------------------------------------------------- roteamento
if not C.DB_PATH.exists():
    st.error("Base não encontrada. Rode `python -m data.generator` e o pipeline de detecção.")
    st.stop()

if "aberto" in st.session_state:
    tela_dossie(st.session_state["aberto"])
else:
    st.markdown("## Sentinela · Operações")
    t1, t2, t3, t4 = st.tabs(["Fila principal", "Monitoramento (médio)", "Decididos", "Métricas"])
    with t1:
        aba_fila()
    with t2:
        aba_monitoramento()
    with t3:
        aba_decididos()
    with t4:
        aba_metricas()
