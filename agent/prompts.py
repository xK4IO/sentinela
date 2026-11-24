"""Prompts e schemas de saída do agente.

Boas práticas usadas aqui:
- Papel claro e público-alvo (analista de Operações).
- Saída ESTRUTURADA (pydantic), sem texto livre para fazer parse.
- Regras explícitas contra alucinação: só citar números que estão nas evidências,
  sempre apontar a evidência, e não inventar IDs.
- O LLM NUNCA recebe o gabarito, nem nomes, nem a decisão final (que é humana).
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

import config as C


# ------------------------------------------------------------------ schemas
class Plano(BaseModel):
    hipoteses: list[str] = Field(
        description="Até 2 hipóteses ADICIONAIS a checar no banco (não repita o que as evidências "
                    "já mostram). Lista vazia se as evidências já bastam.")


class ConsultaSQL(BaseModel):
    objetivo: str = Field(description="O que a consulta verifica, em uma frase")
    sql: str = Field(description="Uma única consulta SQLite SELECT com LIMIT <= 200")


class Analise(BaseModel):
    achado: str = Field(description="O que o resultado mostra, em 1 ou 2 frases, citando os números do resultado")
    precisa_mais: bool = Field(description="true se ainda falta evidência importante para concluir")


class Afirmacao(BaseModel):
    texto: str = Field(description="Uma evidência em linguagem simples, com os números exatos")
    evidencia_id: str = Field(description="ID da evidência que comprova, ex.: E1")


class DossieLLM(BaseModel):
    resumo: str = Field(description="2 a 3 frases para o analista: o que aconteceu e por que é (ou não) suspeito")
    afirmacoes: list[Afirmacao] = Field(description="Evidências numeradas, da mais forte para a mais fraca")
    recomendacao: Literal["LIBERAR", "MANTER_RETIDO"]
    confianca: Literal["BAIXA", "MEDIA", "ALTA"]
    justificativa: str = Field(description="Por que essa recomendação e essa confiança; cite explicações legítimas possíveis")


# ------------------------------------------------------------------ helpers
_ROTULOS = {
    "pct_vendas_disp_creator": "% de vendas em dispositivo do login do creator",
    "qtd_creators_mesma_pix": "outros creators com a mesma chave Pix",
    "qtd_creators_mesmo_disp": "outros creators no mesmo dispositivo de login",
    "taxa_estorno_pos_liberacao": "taxa de estorno após liberação da comissão",
    "taxa_reembolso": "taxa de reembolso", "taxa_chargeback": "taxa de chargeback",
    "mediana_seg_clique_compra": "mediana de segundos entre clique e compra",
    "conversao": "conversão (vendas/cliques)", "share_top_comprador": "participação do maior comprador",
    "qtd_cartoes_repetidos": "cartões usados por 3+ compradores", "qtd_vendas": "vendas na janela",
    "idade_conta_dias": "idade da conta (dias)", "crescimento_vendas_7d": "crescimento das vendas em 7 dias",
}


def rotulo(feature: str) -> str:
    return _ROTULOS.get(feature, feature)


def fmt_evidencias(evidencias: list[dict], max_linhas: int = 15) -> str:
    partes = []
    for e in evidencias:
        linhas = e.get("linhas", [])[:max_linhas]
        tabela = "\n".join(" | ".join("" if v is None else str(v) for v in l) for l in linhas)
        extra = f"\n({len(e['linhas'])} linhas no total)" if len(e.get("linhas", [])) > max_linhas else ""
        achado = f"\nAchado: {e['achado']}" if e.get("achado") else ""
        partes.append(f"[{e['id']}] {e['titulo']}\nColunas: {' | '.join(e.get('colunas', []))}\n{tabela}{extra}{achado}")
    return "\n\n".join(partes)


def fmt_contexto(a: dict) -> str:
    regras = ", ".join(a["regras_disparadas"]) or "nenhuma"
    shap = "; ".join(f"{rotulo(s['feature'])} = {s['valor']} (empurrou {'+' if s['shap'] > 0 else ''}{s['shap']})"
                     for s in a["shap_top"]) or "indisponível"
    feats = "; ".join(f"{rotulo(k)} = {v}" for k, v in a["features"].items() if v is not None)
    return (f"Creator {a['creator_id']} pediu saque de R$ {a['valor']:.2f} em {a['solicitado_em']}.\n"
            f"Janela analisada: {a['janela_ini']} a {a['janela_fim']} ({C.JANELA_FEATURES_DIAS} dias).\n"
            f"Nota de risco: {a['score_final']} (modelo {a['prob_modelo']}, regras {a['score_regras']}).\n"
            f"Regras disparadas: {regras}.\nFatores do modelo (SHAP): {shap}.\nIndicadores: {feats}.")


SISTEMA = ("Você é um investigador antifraude da YouShop. Creators ganham comissão por venda feita no "
           "link deles. Você investiga um saque RETIDO e escreve para um analista humano de Operações, "
           "que toma a decisão final. Seja factual, em português do Brasil. Explicações legítimas existem "
           "(família, compra corporativa, viralização): considere-as.")


def prompt_planejar(a: dict, evidencias: list[dict]) -> str:
    return f"""{SISTEMA}

CONTEXTO DO ALERTA
{fmt_contexto(a)}

EVIDÊNCIAS JÁ COLETADAS
{fmt_evidencias(evidencias)}

TAREFA: proponha no máximo 2 hipóteses ADICIONAIS que valham uma consulta no banco para confirmar
ou descartar a fraude (ex.: "os compradores frequentes também compram de outros creators suspeitos?",
"os reembolsos se concentram logo após a liberação da comissão?"). Se as evidências já bastam, devolva lista vazia."""


def prompt_gerar_sql(a: dict, hipotese: str, schema: str, erro: str | None, anteriores: list[str]) -> str:
    erro_txt = f"\nSUA TENTATIVA ANTERIOR FOI REJEITADA: {erro}\nCorrija.\n" if erro else ""
    ant = "\n".join(f"- {s}" for s in anteriores[-3:]) or "nenhuma"
    return f"""{SISTEMA}

Escreva UMA consulta SQLite para verificar a hipótese abaixo.

HIPÓTESE: {hipotese}
CREATOR: '{a['creator_id']}'  ·  JANELA: ts > '{a['janela_ini']}' AND ts <= '{a['janela_fim']}'

VIEWS DISPONÍVEIS (são as ÚNICAS tabelas acessíveis):
{schema}

Observações: datas são texto 'YYYY-MM-DD HH:MM:SS'; status de venda: APROVADA/REEMBOLSADA/CHARGEBACK;
status_atualizado_em é quando a venda virou REEMBOLSADA/CHARGEBACK; considere só eventos <= '{a['janela_fim']}'.
Regras: só SELECT (WITH permitido), LIMIT obrigatório e no máximo {C.AGENTE_LIMIT_MAX}, prefira agregações
(COUNT/SUM/GROUP BY) a listar linhas.
Consultas já feitas:
{ant}{erro_txt}"""


def prompt_analisar(a: dict, hipotese: str, ev: dict) -> str:
    return f"""{SISTEMA}

HIPÓTESE: {hipotese}
CONSULTA E RESULTADO:
SQL: {ev['sql']}
{fmt_evidencias([ev], max_linhas=30)}

TAREFA: diga o que o resultado mostra (só com números que aparecem nele) e se ainda falta evidência importante.
CUIDADO: não conclua nada que seja consequência do próprio filtro ou JOIN da consulta (ex.: se a consulta
filtrou ou juntou pelo creator investigado, é óbvio que todas as linhas terão a Pix/os dados dele)."""


def prompt_redigir(a: dict, evidencias: list[dict], rede: dict, problemas: list[str] | None) -> str:
    corr = ""
    if problemas:
        corr = ("\nATENÇÃO: a versão anterior citou números ou IDs que NÃO aparecem nas evidências: "
                f"{', '.join(problemas)}. Reescreva usando só valores presentes nas evidências.\n")
    rede_txt = (f"mesma Pix: {', '.join(rede['mesma_pix']) or 'nenhum'}; "
                f"mesmo dispositivo: {', '.join(rede['mesmo_disp']) or 'nenhum'}")
    return f"""{SISTEMA}

CONTEXTO DO ALERTA
{fmt_contexto(a)}

REDE DE CONTAS LIGADAS: {rede_txt}

EVIDÊNCIAS
{fmt_evidencias(evidencias)}

TAREFA: escreva o dossiê.
- Cada afirmação precisa citar a evidência (evidencia_id, ex.: E1) e usar SÓ números presentes nas evidências
  ou no contexto. Pode calcular porcentagens a partir delas (ex.: 14 de 40 = 35%).
- Não invente IDs de creators ou compradores.
- MANTER_RETIDO se há indício concreto de fraude; LIBERAR se as evidências apontam explicação legítima.
- Confiança ALTA só se houver mais de uma evidência forte e consistente.
- Não exponha limiares ou regras internas de detecção.
- Nunca copie hashes (cartão, dispositivo, Pix): diga "um cartão", "o dispositivo de login".
- Valores em formato brasileiro: R$ 1.850,00 · 35% · 0,35.
- Não tire conclusões do que é efeito do próprio filtro/JOIN de uma consulta.
- Em "afirmacoes", só o que aponta para fraude. Sinais que NÃO apontam fraude (ex.: nenhuma venda no
  dispositivo do creator) vão na justificativa, como atenuantes.
- Não faça afirmações qualitativas que nenhuma consulta mediu (ex.: "horários atípicos").{corr}"""


def contexto_como_evidencia(a: dict) -> dict:
    """E0: o próprio alerta vira uma evidência, para que os números dele possam ser citados."""
    linhas = [["valor_saque", a["valor"]], ["score_final", a["score_final"]],
              ["prob_modelo", a["prob_modelo"]], ["score_regras", a["score_regras"]]]
    linhas += [[k, v] for k, v in a["features"].items() if v is not None]
    return {"id": "E0", "titulo": "Indicadores do alerta (calculados pelo Sentinela)", "tipo": "contexto",
            "sql": None, "colunas": ["indicador", "valor"], "linhas": linhas}


def dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)
