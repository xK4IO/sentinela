# Agente investigador: decisões e aprendizados (D3, 24/11/2026)

## Arquitetura híbrida
1. **Consultas canônicas (sem LLM):** para cada regra disparada e cada fator SHAP positivo roda uma SQL
   fixa e auditada. Garante a evidência principal mesmo se o LLM falhar.
2. **LLM (Gemini) investiga hipóteses extras:** no máximo 2 hipóteses e 3 tentativas de SQL.
3. **Dossiê estruturado** (JSON com schema), renderizado em markdown por template Python.

## Camadas de segurança

| Risco | Proteção | Teste |
|---|---|---|
| LLM gerar escrita (UC05) | validador sqlglot (árvore, não texto) **+** conexão `mode=ro` | `test_sql_guard.py` (13 ataques) |
| LLM consultar tabela proibida (gabarito, nomes) | lista de views permitidas e prefixo `main.` bloqueado | idem |
| **LLM olhar o futuro** | views temporárias *point-in-time* com o mesmo nome das `vw_*` | `test_corte_point_in_time_esconde_o_futuro` |
| Número inventado | `checagem.py`: todo número e ID precisa vir das evidências (aceita razões, ex. 14/40 = 35%) | `test_checagem.py` |
| Hash exposto (LGPD) | mascaramento `***abcd` em texto e evidências gravadas | — |
| API fora do ar ou sem cota | fallback determinístico, confiança BAIXA, saque segue RETIDO | `test_falha_da_api...` |

## Escolha do modelo (mesmo alerta, 24/11)

| Modelo | Tempo | Observações |
|---|---|---|
| gemini-2.5-flash | — | aposentado para contas novas (404) |
| gemini-3.5-flash | 80 s | acima da meta de 60 s; **consultou o futuro** (7 chargebacks em vez de 2) e expôs hash de cartão |
| **gemini-3.5-flash-lite** | **10–24 s** | escolhido; errou uma interpretação (conclusão causada pelo próprio JOIN) |

**Lição:** o que é crítico não pode depender de o LLM obedecer ao prompt. As duas falhas do Flash foram
corrigidas *estruturalmente* (views point-in-time, mascaramento), e não com mais texto no prompt.

## Roteamento por complexidade
O lote esbarrou no limite de cota (429) com 6 chamadas por dossiê. Análise dos 90 alertas ALTO:

| Grupo | Alertas | Fraudes | Legítimos |
|---|---|---|---|
| Claro (prob ≥ 0,90 **e** ≥ 1 regra) | 62 | 62 | 0 |
| Ambíguo | 28 | 23 | 5 (todos os falsos positivos) |

Os casos claros vão direto para a redação (1 chamada) e os ambíguos recebem investigação completa (~6 chamadas).
Resultado: cerca de 52% menos chamadas, sem nenhum fallback em 90 dossiês.

## Resultado final (90 dossiês)

| Métrica | Meta | Obtido |
|---|---|---|
| Número não confirmado | ≤ 5% | 1,1% |
| Tempo médio | < 60 s | 14,6 s |
| IA mandou liberar os legítimos retidos por engano | — | 4 de 5 |
| IA mandou reter os fraudadores | — | 78 de 85 |

Exemplo de erro da IA: C1991 (autocompra real) recebeu LIBERAR. A IA aceitou a explicação "vendas para familiares",
que o próprio prompt pede para considerar. É o argumento para manter o humano no circuito.

## Limites conhecidos (para o slide de ética)
- A checagem pega **números e IDs** inventados, mas não **interpretações** erradas nem afirmações
  qualitativas ("horários atípicos"). Por isso a SQL de cada evidência fica visível e o humano decide.
- Os dossiês são gerados em lote antes da demo. Em produção seria por evento (ao pedir o saque).
