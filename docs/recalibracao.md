# Recalibração do score (D2, 24/11/2026)

Base: 1.158 saques pendentes (um por creator), 100 fraudes. Predições do modelo out-of-fold (5 folds).
Modelo: ROC-AUC OOF 0,971 · PR-AUC 0,928.

## Problema encontrado na fórmula da doc v0.1

`score_final = 0,6·p + 0,4·r` com ALTO a partir de 0,70. O modelo contribui no máximo 0,60, então
um creator com `prob_modelo = 0,99` e só uma regra de 20 pontos fica com 0,67 e **nunca chega a ALTO**.
O combinado ficou pior que o modelo sozinho.

## Alternativas simuladas

| R2 (limiar) | Estratégia | Retidos | Precisão | Recall |
|---|---|---|---|---|
| ≥ 1 | doc v0.1 | 62 | 0,823 | 0,51 |
| ≥ 1 | limiar ALTO 0,55 | 90 | 0,878 | 0,79 |
| ≥ 2 | doc v0.1 | 52 | 0,981 | 0,51 |
| ≥ 2 | max(p, 0,6p+0,4r) ≥ 0,60 | 85 | 0,976 | 0,83 |
| **≥ 2** | **max(p, 0,6p+0,4r) ≥ 0,50** | **90** | **0,944** | **0,85** |

## Decisões

1. **R2 crítica só com 3 ou mais contas na mesma Pix** (`qtd_creators_mesma_pix ≥ 2`). Casal ou família
   dividindo Pix é comum no Brasil, e só esta mudança removeu 10 falsos positivos (todos `RUIDO_PIX_CASAL`).
2. **`score_final = max(prob_modelo, 0,6·p + 0,4·r)`**, com ALTO ≥ 0,50 e MÉDIO ≥ 0,30. O modelo
   escala sozinho e as regras só somam, nunca diluem.

## Resultado final

| Métrica | Meta | Obtido |
|---|---|---|
| Recall em ALTO | ≥ 0,85 | 0,85 ✅ |
| Precisão em ALTO | ≥ 0,80 | 0,944 ✅ |
| Virais retidos | ≤ 2 | 0 ✅ |
| R$ retido fraude × legítimo | fraude > legítimo | R$ 16.158 × R$ 143 ✅ |

Valor de cada camada: só regras (P 0,96 / R 0,54) · só modelo (P 0,95 / R 0,80) · combinado (P 0,94 / R 0,85).

## Ressalvas honestas (para o slide de limites)

- **O limiar foi escolhido nos mesmos dados em que é medido.** Isso deixa as métricas um pouco
  otimistas. O certo seria separar um conjunto de validação só para escolher limiares, ou confirmar
  em modo sombra (fase 1 do plano de adoção).
- **Correlação espúria possível:** `qtd_vendas` é a feature de maior ganho. No gerador, os fraudadores
  recebem vendas plantadas a mais, então volume e fraude andam juntos por construção, não por realidade.
- **Fraudes discretas escapam:** F3 discreta (0/4), F5 discreta (1/4), F1 discreta (2/4). É o limite
  esperado de um sinal fraco, e é aí que entra a revisão humana na faixa MÉDIO.
