"""checar_numeros: todo número e todo ID citado no dossiê precisa vir das evidências.

Como funciona:
  1. Junta todos os números das evidências (células numéricas + quantidade de linhas).
  2. Acrescenta as razões entre eles (a/b), porque o LLM pode escrever "14 de 40 (35%)".
  3. Extrai os números do texto em formato brasileiro ("1.850,00", "35%", "0,35") e
     ignora datas, horas, hashes mascarados e números colados em letras (C0417, R1).
  4. Cada número precisa bater, com tolerância de arredondamento, com algum valor do passo 1 ou 2.
  5. IDs de creators/compradores (C1234, B12345) precisam aparecer nas evidências ou na rede.
"""
from __future__ import annotations

import itertools
import re

import config as C

_REMOVER = [
    r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?",  # 2026-11-20 10:00:00
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",                    # 20/11/2026
    r"\b\d{1,2}[:h]\d{2}(?::\d{2})?\b",                # 10:02, 10h02
    r"\*+\w+",                                         # ***8841 (hash mascarado)
    r"\b[0-9a-f]{16}\b",                               # hash completo
    r"\b[A-Z]+\d+(?:_\w+)?\b",                         # C0417, B38898, R1_AUTOCOMPRA, E2
]
_NUM = re.compile(r"(?<![\w.,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)(?!\w)(\s?%)?")
_ID = re.compile(r"\b[CB]\d{4,5}\b")
# números que podem aparecer sem vir de evidência: janela, prazo, limiares do texto ao creator
_CONSTANTES = {0.0, 1.0, float(C.JANELA_FEATURES_DIAS), float(C.PRAZO_RETENCAO_HORAS), 7.0, 15.0}


def _parse(tok: str) -> tuple[float, int]:
    """Converte um número escrito em pt-BR (ou en) e devolve (valor, casas decimais)."""
    if "," in tok:
        inteiro, dec = tok.replace(".", "").split(",")
        return float(f"{inteiro}.{dec}"), len(dec)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", tok):  # 1.850 = mil oitocentos e cinquenta
        return float(tok.replace(".", "")), 0
    if "." in tok:
        return float(tok), len(tok.split(".")[1])
    return float(tok), 0


def numeros_no_texto(texto: str) -> list[tuple[str, float, int, bool]]:
    limpo = texto
    for p in _REMOVER:
        limpo = re.sub(p, " ", limpo)
    out = []
    for m in _NUM.finditer(limpo):
        v, dec = _parse(m.group(1))
        out.append((m.group(0).strip(), v, dec, bool(m.group(2))))
    return out


def numeros_das_evidencias(evidencias: list[dict]) -> set[float]:
    nums: set[float] = set()
    for e in evidencias:
        nums.add(float(len(e.get("linhas", []))))
        for linha in e.get("linhas", []):
            for v in linha:
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    nums.add(float(v))
    return nums


def _suportado(v: float, dec: int, pct: bool, base: set[float], razoes: set[float]) -> bool:
    if v in _CONSTANTES:
        return True
    tol = 0.5 * 10 ** -dec + 1e-9
    if pct:
        tol = max(tol, 0.51)
    for n in itertools.chain(base, razoes):
        if abs(v - n) <= tol:
            return True
        if (pct or abs(n) <= 1) and abs(v - 100 * n) <= max(tol, 0.51 if pct else tol):
            return True
    return False


def checar(textos: list[str], evidencias: list[dict], ids_permitidos: set[str]) -> list[str]:
    """Devolve a lista de problemas (vazia = ok)."""
    base = numeros_das_evidencias(evidencias)
    amostra = sorted(base, key=abs)[:250]  # limita o custo das razões
    razoes = {a / b for a, b in itertools.permutations(amostra, 2) if b not in (0.0,)}
    celulas = {str(v) for e in evidencias for l in e.get("linhas", []) for v in l if isinstance(v, str)}
    ids_ok = ids_permitidos | {c for cel in celulas for c in _ID.findall(cel)}

    problemas = []
    for texto in textos:
        for tok, v, dec, pct in numeros_no_texto(texto):
            if not _suportado(v, dec, pct, base, razoes):
                problemas.append(f"número '{tok}'")
        for i in _ID.findall(texto):
            if i not in ids_ok:
                problemas.append(f"ID '{i}'")
    return sorted(set(problemas))
