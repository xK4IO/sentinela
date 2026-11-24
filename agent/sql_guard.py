"""Validador da SQL gerada pelo LLM (UC05).

Defesa em profundidade, em duas camadas independentes:
  1. Este validador (sqlglot): analisa a ÁRVORE da consulta, não o texto. Assim não dá
     para enganar com truques como comentários, maiúsculas ou "SELECT ...; DROP ...".
  2. A conexão somente leitura (tools.py). Mesmo que algo passe por aqui, o SQLite
     recusa a escrita.

Regras: exatamente 1 statement · só SELECT (WITH/UNION permitidos) · só as views vw_*
(ou CTEs declaradas na própria consulta) · LIMIT ≤ 200 obrigatório · sem funções perigosas.
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

import config as C

VIEWS_PERMITIDAS = {"vw_vendas", "vw_comissoes", "vw_saques", "vw_logins", "vw_cliques", "vw_creators"}
FUNCOES_PROIBIDAS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}
_NOS_PROIBIDOS = tuple(getattr(exp, n) for n in
                       ("Insert", "Update", "Delete", "Drop", "Create", "Alter", "Merge",
                        "Command", "Pragma", "Attach", "Detach", "Transaction", "Commit")
                       if hasattr(exp, n))
_CONSULTA = tuple(getattr(exp, n) for n in ("Select", "Union", "Intersect", "Except", "SetOperation")
                  if hasattr(exp, n))


class SQLRejeitada(ValueError):
    """A mensagem volta para o LLM como feedback na próxima tentativa."""


def validar(sql: str) -> str:
    """Devolve a SQL normalizada se for segura; senão levanta SQLRejeitada."""
    try:
        stmts = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except ParseError as e:
        raise SQLRejeitada(f"SQL inválida: {str(e).splitlines()[0]}") from e
    if len(stmts) != 1:
        raise SQLRejeitada(f"envie exatamente 1 consulta (recebi {len(stmts)})")
    st = stmts[0]
    if not isinstance(st, _CONSULTA):
        raise SQLRejeitada(f"só SELECT é permitido (recebi {type(st).__name__.upper()})")
    proibido = st.find(*_NOS_PROIBIDOS)
    if proibido is not None:
        raise SQLRejeitada(f"comando proibido dentro da consulta: {type(proibido).__name__.upper()}")

    ctes = {c.alias_or_name.lower() for c in st.find_all(exp.CTE)}
    for t in st.find_all(exp.Table):
        nome = t.name.lower()
        if t.args.get("db") or t.args.get("catalog"):
            raise SQLRejeitada(f"não use prefixo de schema em '{t.sql()}'")
        if nome not in ctes and nome not in VIEWS_PERMITIDAS:
            raise SQLRejeitada(f"tabela '{t.name}' não permitida. Use só: {', '.join(sorted(VIEWS_PERMITIDAS))}")

    for fn in st.find_all(exp.Anonymous, exp.Func):
        nome = (fn.name if isinstance(fn, exp.Anonymous) else fn.sql_name()).lower()
        if nome in FUNCOES_PROIBIDAS:
            raise SQLRejeitada(f"função proibida: {nome}")

    limite = st.args.get("limit")
    if limite is None:
        raise SQLRejeitada(f"LIMIT é obrigatório (máximo {C.AGENTE_LIMIT_MAX})")
    try:
        n = int(limite.expression.name)
    except (AttributeError, TypeError, ValueError) as e:
        raise SQLRejeitada("LIMIT precisa ser um número inteiro literal") from e
    if n > C.AGENTE_LIMIT_MAX or n < 1:
        raise SQLRejeitada(f"LIMIT {n} fora do permitido (1 a {C.AGENTE_LIMIT_MAX})")
    return st.sql(dialect="sqlite")
