"""Métricas do protótipo contra o gabarito (seção 10).

Conceitos:
  - Precisão: dos que RETIVEMOS, quantos eram fraude?  (custo: incomodar creator honesto)
  - Recall:   das FRAUDES que existiam, quantas pegamos? (custo: dinheiro que sai)
  Uma melhora quase sempre piora a outra; o limiar escolhe o equilíbrio.

Também compara 3 estratégias (só regras, só modelo, combinado) para mostrar
o valor de cada camada, um bom material para o slide de métricas.

Uso:  python evaluate.py
"""
from __future__ import annotations

import json
import sqlite3

import pandas as pd

import config as C
from detection.score import faixa
from detection.train import FRAUDE

METRICAS_PATH = C.ROOT / "data" / "metricas.json"
METAS = {"recall": 0.85, "precisao": 0.80, "virais_retidos": 2, "dossies_numero_inventado": 0.05}


def carregar(con: sqlite3.Connection) -> pd.DataFrame:
    # regra de prevalência: vale o alerta mais recente por creator
    return pd.read_sql("""
        WITH ult AS (
            SELECT a.*, ROW_NUMBER() OVER (PARTITION BY creator_id
                                           ORDER BY criado_em DESC, alerta_id DESC) AS rn
            FROM alertas a)
        SELECT u.alerta_id, u.creator_id, u.score_regras, u.prob_modelo, u.score_final,
               u.faixa_risco, u.regras_disparadas, s.valor,
               g.fraude_tipo, COALESCE(g.observacao, '') AS obs
        FROM ult u
        JOIN saques s USING (saque_id)
        JOIN gabarito g USING (creator_id)
        WHERE u.rn = 1""", con)


def resumo(alto: pd.Series, fraude: pd.Series, valor: pd.Series, viral: pd.Series) -> dict:
    tp = int((alto & fraude).sum())
    fp = int((alto & ~fraude).sum())
    fn = int((~alto & fraude).sum())
    return {
        "retidos": int(alto.sum()), "tp": tp, "fp": fp, "fn": fn,
        "precisao": round(tp / max(1, tp + fp), 3),
        "recall": round(tp / max(1, tp + fn), 3),
        "virais_retidos": int((alto & viral).sum()),
        "rs_retido_fraude": round(float(valor[alto & fraude].sum()), 2),
        "rs_retido_legitimo": round(float(valor[alto & ~fraude].sum()), 2),
    }


def metricas_agente(con: sqlite3.Connection) -> dict:
    """Seção 10: número inventado ≤ 5%, tempo < 60 s. Extra: recomendação da IA × gabarito."""
    d = pd.read_sql("""
        SELECT d.recomendacao, d.confianca, d.duracao_seg, d.detalhes, g.fraude_tipo
        FROM dossies d JOIN alertas a USING (alerta_id) JOIN gabarito g USING (creator_id)""", con)
    print("\n== Agente investigador ==")
    if d.empty:
        print("  (nenhum dossiê gerado ainda)")
        return {}
    det = d.detalhes.apply(json.loads)
    d["fallback"] = det.apply(lambda x: x.get("fallback", False))
    d["numero_inventado"] = det.apply(lambda x: x.get("numero_inventado", False))
    d["fraude"] = d.fraude_tipo.isin(FRAUDE)
    ok = d[~d.fallback]
    m = {
        "dossies": len(d), "fallbacks": int(d.fallback.sum()),
        "pct_numero_inventado": round(float(ok.numero_inventado.mean()), 3) if len(ok) else None,
        "tempo_medio_seg": round(float(ok.duracao_seg.mean()), 1) if len(ok) else None,
        "confianca": ok.confianca.value_counts().to_dict(),
        "fraude_recomendou_reter": int((ok.fraude & ok.recomendacao.eq("MANTER_RETIDO")).sum()),
        "fraude_total": int(ok.fraude.sum()),
        "legitimo_recomendou_liberar": int((~ok.fraude & ok.recomendacao.eq("LIBERAR")).sum()),
        "legitimo_total": int((~ok.fraude).sum()),
    }
    meta_n, meta_t = METAS["dossies_numero_inventado"], 60
    print(f"  Dossiês: {m['dossies']} ({m['fallbacks']} em fallback)")
    if len(ok):
        print(("  ✅ " if m["pct_numero_inventado"] <= meta_n else "  ❌ ") +
              f"Número inventado ≤ {meta_n:.0%}: {m['pct_numero_inventado']:.1%}")
        print(("  ✅ " if m["tempo_medio_seg"] < meta_t else "  ❌ ") +
              f"Tempo médio < {meta_t}s: {m['tempo_medio_seg']}s")
        print(f"  IA recomendou reter {m['fraude_recomendou_reter']}/{m['fraude_total']} fraudadores e "
              f"liberar {m['legitimo_recomendou_liberar']}/{m['legitimo_total']} legítimos retidos por engano")
        print(f"  Confiança: {m['confianca']}")
    return m


def main() -> None:
    con = sqlite3.connect(C.DB_PATH)
    d = carregar(con)
    fraude = d.fraude_tipo.isin(FRAUDE)
    viral = d.fraude_tipo.eq("LEGITIMO_VIRAL")
    critica = d.regras_disparadas.apply(lambda s: any(C.REGRAS[r]["critica"] for r in json.loads(s)))

    estrategias = {
        "so_regras": pd.Series([faixa(s, c) == "ALTO" for s, c in zip(d.score_regras, critica)]),
        "so_modelo": d.prob_modelo.fillna(0) >= C.LIMIAR_ALTO,
        "combinado": d.faixa_risco.eq("ALTO"),
    }
    res = {nome: resumo(alto.values, fraude.values, d.valor.values, viral.values)
           for nome, alto in estrategias.items()}
    res = {k: {kk: vv for kk, vv in v.items()} for k, v in res.items()}

    print("== Comparação de estratégias (faixa ALTO) ==")
    print(pd.DataFrame(res).T.to_string())

    c = res["combinado"]
    print("\n== Critérios de aceite (estratégia combinada) ==")
    for nome, ok in [
        (f"Recall ≥ {METAS['recall']}: {c['recall']}", c["recall"] >= METAS["recall"]),
        (f"Precisão ≥ {METAS['precisao']}: {c['precisao']}", c["precisao"] >= METAS["precisao"]),
        (f"Virais retidos ≤ {METAS['virais_retidos']}: {c['virais_retidos']}", c["virais_retidos"] <= METAS["virais_retidos"]),
        (f"R$ fraude > R$ legítimo: {c['rs_retido_fraude']:,.0f} × {c['rs_retido_legitimo']:,.0f}",
         c["rs_retido_fraude"] > c["rs_retido_legitimo"]),
    ]:
        print(("  ✅ " if ok else "  ❌ ") + nome)

    print("\n== % em cada faixa por tipo (gabarito) ==")
    tab = pd.crosstab([d.fraude_tipo, d.obs], d.faixa_risco, normalize="index").round(2)
    tab["n"] = d.groupby(["fraude_tipo", "obs"]).size()
    print(tab.to_string())

    alto = d.faixa_risco.eq("ALTO")
    fps = d[alto & ~fraude][["creator_id", "fraude_tipo", "obs", "score_final", "prob_modelo", "regras_disparadas"]]
    fns = d[~alto & fraude][["creator_id", "fraude_tipo", "obs", "score_final", "prob_modelo", "regras_disparadas"]]
    print(f"\n== Falsos positivos ({len(fps)}) ==\n{fps.to_string(index=False)}")
    print(f"\n== Falsos negativos ({len(fns)}) ==\n{fns.to_string(index=False)}")

    res["agente"] = metricas_agente(con)

    res["por_tipo"] ={f"{t}|{o}": row.drop("n").to_dict() | {"n": int(row.n)} for (t, o), row in tab.iterrows()}
    res["falsos_positivos"] = fps.to_dict("records")
    res["falsos_negativos"] = fns.to_dict("records")
    METRICAS_PATH.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nSalvo em {METRICAS_PATH.relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()
