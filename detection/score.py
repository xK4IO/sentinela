"""Score final, faixa de risco e gravação dos alertas (seção 6.3, recalibrada no D2).

    score_final = max(prob_modelo, 0,6 * prob_modelo + 0,4 * score_regras)
    faixa = ALTO   se score_final >= 0,50 OU alguma regra crítica disparou
            MEDIO  se 0,30 <= score_final < 0,50
            BAIXO  caso contrário

Por que o max()? Na fórmula original (só a média ponderada), o modelo contribuía no
máximo 0,6, então um creator com prob_modelo = 0,99 e nenhuma regra forte nunca chegava
a ALTO. Com o max(), o modelo pode escalar sozinho e as regras só SOMAM, nunca diluem.

Modo degradado (sem modelo):  score_final = score_regras.

Efeito no saque: ALTO → RETIDO (vai para o analista); MEDIO/BAIXO → APROVADO.

Uso:  python -m detection.score              (usa as predições OOF do train.py)
      python -m detection.score --sem-modelo (modo degradado, só regras)

ATENÇÃO: re-rodar apaga alertas, dossiês e revisões dos saques avaliados.
"""
from __future__ import annotations

import argparse
import json
import sqlite3

import numpy as np
import pandas as pd

import config as C
from detection.features import calcular_features, saques_avaliados
from detection.rules import avaliar_df
from detection.train import OOF_PATH


def faixa(score_final: float, critica: bool) -> str:
    if critica or score_final >= C.LIMIAR_ALTO:
        return "ALTO"
    if score_final >= C.LIMIAR_MEDIO:
        return "MEDIO"
    return "BAIXO"


def combinar(score_regras: pd.Series, prob_modelo: pd.Series) -> pd.Series:
    ponderado = C.PESO_MODELO * prob_modelo + C.PESO_REGRAS * score_regras
    combinado = np.maximum(prob_modelo, ponderado)
    return combinado.where(prob_modelo.notna(), score_regras)  # NaN no modelo → modo degradado


def _json_features(row: pd.Series) -> str:
    return json.dumps({k: (None if pd.isna(v) else round(float(v), 4)) for k, v in row.items()})


def main(sem_modelo: bool = False) -> None:
    con = sqlite3.connect(C.DB_PATH)
    saques = saques_avaliados(con)
    ids = tuple(saques.saque_id)

    # Reinicia o estado dos saques avaliados (idempotência: rodar 2x dá o mesmo resultado)
    ph = ",".join("?" * len(ids))
    con.execute(f"DELETE FROM revisoes WHERE alerta_id IN (SELECT alerta_id FROM alertas WHERE saque_id IN ({ph}))", ids)
    con.execute(f"DELETE FROM dossies WHERE alerta_id IN (SELECT alerta_id FROM alertas WHERE saque_id IN ({ph}))", ids)
    con.execute(f"DELETE FROM alertas WHERE saque_id IN ({ph})", ids)
    con.execute(f"UPDATE saques SET status='SOLICITADO' WHERE saque_id IN ({ph})", ids)

    X = calcular_features(con, saques)
    r = avaliar_df(X)
    df = saques.set_index("saque_id").join(r)

    if sem_modelo or not OOF_PATH.exists():
        print("Modo degradado: score_final = score_regras")
        df["prob_modelo"], df["shap_top"] = np.nan, None
    else:
        oof = pd.read_csv(OOF_PATH, index_col="saque_id")
        df = df.join(oof[["prob_modelo", "shap_top"]])

    df["score_final"] = combinar(df.score_regras, df.prob_modelo)
    df["faixa_risco"] = [faixa(s, c) for s, c in zip(df.score_final, df.critica)]

    linhas = []
    for sid, row in df.iterrows():
        linhas.append((
            row.creator_id, sid, round(row.score_regras, 4),
            None if pd.isna(row.prob_modelo) else round(float(row.prob_modelo), 4),
            round(float(row.score_final), 4), row.faixa_risco,
            json.dumps(row.regras_disparadas), row.shap_top if isinstance(row.shap_top, str) else None,
            _json_features(X.loc[sid]),
            row.solicitado_em.strftime("%Y-%m-%d %H:%M:%S"),  # score calculado no momento do pedido
        ))
    con.executemany("""INSERT INTO alertas (creator_id, saque_id, score_regras, prob_modelo,
                       score_final, faixa_risco, regras_disparadas, shap_top, features, criado_em)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""", linhas)
    con.executemany("UPDATE saques SET status=? WHERE saque_id=?",
                    [("RETIDO" if f == "ALTO" else "APROVADO", sid) for sid, f in df.faixa_risco.items()])
    con.commit()
    print(df.faixa_risco.value_counts().to_string())
    print(f"R$ retido: {df.loc[df.faixa_risco == 'ALTO', 'valor'].sum():,.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-modelo", action="store_true")
    main(ap.parse_args().sem_modelo)
