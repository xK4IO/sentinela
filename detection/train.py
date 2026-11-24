"""Treino do LightGBM com validação cruzada out-of-fold (OOF) + SHAP (seção 6.2).

Por que OOF?
  Com 1 split 70/30, só 30% dos creators recebem uma nota "honesta" (de um modelo que
  não os viu no treino). Com 5 folds, cada creator cai no teste exatamente uma vez,
  então TODOS os 1.158 recebem uma nota honesta, e as métricas usam a base inteira.

Por que uma linha por saque pendente (um por creator)?
  O gabarito rotula o creator, não o saque. Saques antigos de um fraudador podem ser
  anteriores à fraude. Rotulá-los como fraude seria ensinar errado (ruído de rótulo).
  Como há um saque avaliado por creator, StratifiedKFold já garante que o mesmo
  creator nunca aparece no treino e no teste.

Por que NÃO balancear as classes (scale_pos_weight)?
  Só ~9% são fraude. Balancear ajuda o modelo a "prestar atenção" nos positivos, mas
  distorce a probabilidade: um 0,8 deixaria de significar ~80% de chance. Como o
  score_final usa prob_modelo com limiares fixos (0,40 / 0,70), queremos que ela seja
  uma probabilidade honesta.

SHAP: para cada creator, quanto cada feature empurrou a nota para cima ou para baixo.
  O LightGBM calcula isso nativamente (pred_contrib=True usa o algoritmo TreeSHAP,
  o mesmo da biblioteca `shap`).

Uso:  python -m detection.train
"""
from __future__ import annotations

import json
import sqlite3

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

import config as C
from detection.features import FEATURES, calcular_features, saques_avaliados

OOF_PATH = C.ROOT / "detection" / "oof_predicoes.csv"
N_FOLDS = 5
PARAMS = dict(
    objective="binary",
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=15,          # árvores pequenas: base pequena, evita decorar (overfitting)
    min_child_samples=10,
    subsample=0.8, subsample_freq=1,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    random_state=C.SEED,
    deterministic=True,
    verbose=-1,
)
FRAUDE = C.FRAUDE


def montar_base(con: sqlite3.Connection) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    saques = saques_avaliados(con)
    X = calcular_features(con, saques)
    gab = pd.read_sql("SELECT creator_id, fraude_tipo FROM gabarito", con)
    meta = saques.merge(gab, on="creator_id").set_index("saque_id").loc[X.index]
    y = meta.fraude_tipo.isin(FRAUDE).astype(int)   # alvo: virais e NENHUMA são 0
    return X, y, meta


def shap_top(contrib: np.ndarray, X: pd.DataFrame, k: int = 3) -> list[str]:
    """contrib tem uma coluna por feature + 1 coluna final (valor base). Pega as k de maior |SHAP|."""
    res = []
    for i in range(len(X)):
        vals = contrib[i, :-1]
        idx = np.argsort(-np.abs(vals))[:k]
        res.append(json.dumps([
            {"feature": FEATURES[j], "shap": round(float(vals[j]), 4),
             "valor": None if pd.isna(X.iat[i, j]) else round(float(X.iat[i, j]), 4)}
            for j in idx], ensure_ascii=False))
    return res


def treinar_oof(X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    oof = pd.DataFrame(index=X.index, columns=["prob_modelo", "shap_top", "fold"], dtype=object)
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=C.SEED)
    for fold, (tr, te) in enumerate(skf.split(X, y)):
        m = lgb.LGBMClassifier(**PARAMS).fit(X.iloc[tr], y.iloc[tr])
        Xte = X.iloc[te]
        oof.iloc[te, 0] = m.predict_proba(Xte)[:, 1]
        oof.iloc[te, 1] = shap_top(m.predict(Xte, pred_contrib=True), Xte)
        oof.iloc[te, 2] = fold
    oof["prob_modelo"] = oof.prob_modelo.astype(float)
    return oof


def main() -> None:
    con = sqlite3.connect(C.DB_PATH)
    X, y, meta = montar_base(con)
    print(f"Base: {len(X)} saques, {int(y.sum())} fraudes ({y.mean():.1%})")

    oof = treinar_oof(X, y)
    auc = roc_auc_score(y, oof.prob_modelo)
    ap = average_precision_score(y, oof.prob_modelo)
    print(f"OOF  ROC-AUC = {auc:.3f} | PR-AUC (average precision) = {ap:.3f}")
    oof.to_csv(OOF_PATH)

    # Modelo final com a base toda: é o que iria para produção avaliar saques NOVOS.
    final = lgb.LGBMClassifier(**PARAMS).fit(X, y)
    final.booster_.save_model(str(C.MODEL_PATH))
    imp = pd.Series(final.booster_.feature_importance("gain"), index=FEATURES)
    print("\nImportância (ganho) no modelo final:")
    print((imp / imp.sum()).sort_values(ascending=False).round(3).to_string())

    por_tipo = meta.assign(prob=oof.prob_modelo).groupby("fraude_tipo").prob.median()
    print("\nprob_modelo mediana por tipo (OOF):")
    print(por_tipo.round(3).to_string())
    print(f"\nSalvos: {OOF_PATH.name}, {C.MODEL_PATH.name}")


if __name__ == "__main__":
    main()
