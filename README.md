# 🛡️ Sentinela: copiloto antifraude para saques de creators

Protótipo do **Desafio de Inovação · Programa de Estágio YouShop 2027**.

A YouShop paga comissão a creators automaticamente a cada venda feita pelo link rastreável. O Sentinela
analisa cada **pedido de saque antes de o dinheiro sair**. Quando encontra sinais de fraude, **retém** o saque
(nunca bloqueia) e entrega ao analista de Operações um **dossiê pronto**, com as evidências e a consulta SQL
que prova cada número. **Quem decide é sempre um humano.**

> Todos os dados são **sintéticos**, gerados com semente fixa. Nenhum dado real de pessoas.

## Como funciona

```
Saque pedido → features (30 dias) → regras explicáveis + LightGBM/SHAP → nota de risco
   BAIXO/MÉDIO → saque pago        ALTO → saque RETIDO → agente investigador (LangGraph + Gemini)
                                                   → dossiê com evidências e SQL → analista decide
```

| Camada | O quê | Onde |
|---|---|---|
| Dados | 2.000 creators, 36 mil vendas, 5 tipos de fraude plantados + virais legítimos + ruído | `data/generator.py` |
| Detecção | 13 features sem vazamento do futuro, 7 regras, LightGBM com validação out-of-fold | `detection/` |
| Investigação | consultas canônicas + LLM em grafo, SQL validada e somente leitura, checagem anti-alucinação | `agent/` |
| Interface | fila, dossiê, rede de contas, decisão com auditoria, métricas | `app/` |

## Resultados (base sintética, 1.158 saques avaliados)

| Métrica | Meta | Obtido |
|---|---|---|
| Fraudes pegas (recall) | ≥ 85% | **85%** |
| Retidos que eram fraude (precisão) | ≥ 80% | **94%** |
| Creators virais legítimos retidos | ≤ 2 | **0** |
| R$ retido de fraudador × de legítimo | fraude > legítimo | **R$ 16.158 × R$ 143** |
| Dossiês com número não confirmado | ≤ 5% | **1,1%** (1 de 90) |
| Tempo médio por dossiê | < 60 s | **14,6 s** |

**A IA recomenda, mas não decide.** Nos 90 saques retidos, a IA recomendou liberar 4 dos 5 legítimos retidos
por engano, mas também 7 dos 85 fraudadores. Seguida às cegas, a precisão subiria para ~99% e a cobertura
cairia de 85% para 78%. Por isso a decisão é do analista, que vê a SQL de cada evidência.

Decisões e aprendizados documentados: [`docs/recalibracao.md`](docs/recalibracao.md) (por que a fórmula
original do score falhava) e [`docs/agente.md`](docs/agente.md) (segurança do agente e escolha do modelo).

## Segurança e ética
- **IA recomenda, humano decide.** Toda decisão exige comentário e fica registrada.
- **LGPD:** dados pessoais só como hash, exibidos mascarados (`***8841`).
- **O agente não escreve:** a SQL é validada pela árvore (sqlglot) e roda numa conexão somente leitura.
- **O agente não vê o futuro:** as views são "congeladas" no momento do saque.
- **Números conferidos:** todo número e ID do dossiê precisa vir de uma consulta. Se não vier, a confiança cai para BAIXA.
- **Ausente ≠ zero:** creator sem histórico não é tratado como "perfeito" nem como suspeito.

## Rodar localmente

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m data.generator          # base sintética
.\.venv\Scripts\python.exe -m detection.train          # LightGBM (OOF)
.\.venv\Scripts\python.exe -m detection.score          # alertas e faixas
.\.venv\Scripts\python.exe evaluate.py                 # métricas
# opcional (precisa de GOOGLE_API_KEY no .env, ver .env.example):
.\.venv\Scripts\python.exe -m agent.batch_dossies      # dossiês com o Gemini
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
.\.venv\Scripts\python.exe -m pytest                   # testes
```

## Limites
Dados sintéticos mostram que a lógica funciona, mas não provam o desempenho em produção. O próximo passo
seria um piloto em **modo sombra**: avaliar saques reais sem reter nada e comparar com as fraudes confirmadas depois.
