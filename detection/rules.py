"""Regras explicáveis (seção 6.1).

As regras são a camada que QUALQUER analista entende: "35% das vendas saíram do celular
do creator". São funções puras: recebem as features e devolvem quais regras dispararam,
sem acessar banco nem modelo. Isso as torna fáceis de testar e de auditar.

Os limiares e pontos ficam em config.REGRAS, nunca no código, para recalibrar sem mexer aqui.
"""
from __future__ import annotations

import math
import operator
from dataclasses import dataclass
from typing import Mapping

import pandas as pd

import config as C

OPS = {">=": operator.ge, ">": operator.gt, "<": operator.lt, "<=": operator.le}


@dataclass
class ResultadoRegras:
    disparadas: list[str]
    pontos: int
    score_regras: float   # 0 a 1
    critica: bool         # alguma regra crítica disparou → ALTO direto


def _ausente(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def avaliar(features: Mapping[str, float], regras: Mapping[str, dict] = C.REGRAS) -> ResultadoRegras:
    disparadas, pontos, critica = [], 0, False
    for nome, r in regras.items():
        v = features.get(r["feature"])
        if _ausente(v):          # sem informação: a regra NÃO dispara (regra de borda, seção 7)
            continue
        if OPS[r["op"]](v, r["limiar"]):
            disparadas.append(nome)
            pontos += r["pontos"]
            critica = critica or r["critica"]
    return ResultadoRegras(disparadas, pontos, min(100, pontos) / 100, critica)


def avaliar_df(feats: pd.DataFrame, regras: Mapping[str, dict] = C.REGRAS) -> pd.DataFrame:
    res = [avaliar(row, regras) for row in feats.to_dict("records")]
    return pd.DataFrame({
        "regras_disparadas": [r.disparadas for r in res],
        "score_regras": [r.score_regras for r in res],
        "critica": [r.critica for r in res],
    }, index=feats.index)
