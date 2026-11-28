# CLAUDE.md: Sentinela

Protótipo antifraude para o **Desafio de Inovação do Programa de Estágio YouShop 2027**. O sistema analisa
cada pedido de saque de creator **antes de o dinheiro sair**. Quando há sinais de fraude, **retém** o saque
(nunca bloqueia) e entrega ao analista de Operações um relatório com provas e a SQL de origem.
**Quem decide é sempre um humano.** Todos os dados são sintéticos (semente 42).

- Entrega: **29/11/2026 às 23:59**, em slides e vídeo. O formato final ainda não foi fechado.
- Repositório: https://github.com/caio-esteves/sentinela · app: https://sentinela-youshop-caioesteves.streamlit.app/.
- Especificação de origem: `sentinela-doc-tecnica.md` e `sentinela-doc-negocio.md`, que ficam fora do repo.
  Os desvios dessas specs estão registrados em `docs/`.
- **Onde paramos e próximos passos: leia `ESTADO.md` no início de toda sessão e atualize-o no fim.**

## Como trabalhar com este usuário
- Escreva **em português do Brasil**.
- O usuário é estagiário e usa o projeto **também para aprender**. Explique o *porquê* das decisões, deixe
  comentários didáticos no código e feche cada etapa com os conceitos-chave e um exercício curto.
- Para ações em ferramentas (VS Code, extensões, terminal, GitHub), dê o passo a passo.
- Antes de tarefas grandes, apresente o plano. Recomende uma opção em vez de listar todas.
- Visual e textos da interface: o usuário **rejeita aparência de "feito por IA"**. Ver a seção Interface.

## Comandos (PowerShell, na raiz do projeto)
```powershell
.\.venv\Scripts\python.exe -m data.generator        # gera data/youshop.db (~14 s, determinístico)
.\.venv\Scripts\python.exe -m data.sanity           # sinais por tipo de fraude
.\.venv\Scripts\python.exe -m detection.train       # LightGBM OOF → detection/oof_predicoes.csv, model.txt
.\.venv\Scripts\python.exe -m detection.score       # alertas + status dos saques (ver o aviso abaixo)
.\.venv\Scripts\python.exe evaluate.py              # métricas → data/metricas.json
.\.venv\Scripts\python.exe -m agent.batch_dossies   # relatórios com o Gemini (--limite N, --alerta ID, --refazer)
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py   # http://localhost:8501
.\.venv\Scripts\python.exe -m pytest -q -p no:warnings             # 60 testes
```
Para saída com acento no terminal, defina `$env:PYTHONIOENCODING="utf-8"` antes de rodar.

⚠️ **`detection.score` apaga os alertas, dossiês e revisões dos saques avaliados.** Rodá-lo de novo obriga a
regenerar os 90 dossiês, o que gasta a cota do Gemini. Só rode quando a detecção mudar de fato.

## Arquitetura
```
data/generator.py → data/youshop.db (SQLite) → detection/features.py → rules.py + train.py (OOF)
   → score.py (alertas) → agent/graph.py (LangGraph + Gemini) → dossies → app/streamlit_app.py
```

| Pasta | Conteúdo |
|---|---|
| `config.py` | **Todos** os parâmetros: volumes, limiares das regras, pesos do score, modelo do Gemini, cortes do agente |
| `db/` | `schema.sql` (tabelas) e `views.sql` (as `vw_*` expostas ao agente, sem nome, CPF ou gabarito) |
| `data/` | gerador em camadas (base legítima → F1–F5 → virais → ruído → comissões/saques), `sanity.py`, `youshop.db` (~67 MB, versionado) |
| `detection/` | `features.py` (13 features por saque), `rules.py` (funções puras), `train.py`, `score.py` |
| `agent/` | `sql_guard.py`, `tools.py`, `checagem.py`, `prompts.py`, `llm.py` (GeminiLLM/FakeLLM), `graph.py`, `batch_dossies.py` |
| `app/` | `streamlit_app.py` (telas), `ui.py` (CSS, ícones e componentes), `dados.py` (consultas e **nomenclatura**), `requirements.txt` enxuto para o deploy |
| `docs/` | `recalibracao.md` (fórmula do score) e `agente.md` (segurança do agente, escolha de modelo, roteamento) |

## Invariantes: não quebre
1. **Sem vazamento do futuro.** As features só usam eventos com `status_atualizado_em <= solicitado_em`.
   O agente consulta **views temporárias point-in-time** (`tools.restringir_ate`) com o mesmo nome das
   `vw_*`, então nem o LLM consegue enxergar além da data do saque.
2. **Ausente ≠ zero.** Creator sem vendas na janela tem as taxas como `NaN`. As regras ignoram NaN, e o
   LightGBM trata NaN de forma nativa.
3. **Unidade de treino = 1 saque pendente por creator.** O gabarito rotula o creator, e usar saques antigos
   introduziria ruído de rótulo. As métricas vêm de predições **out-of-fold** (5 folds).
4. **Score recalibrado** (não é o da spec v0.1):
   `score_final = max(prob, 0,6·prob + 0,4·regras)`, ALTO ≥ 0,50 ou regra crítica; MÉDIO ≥ 0,30.
   A R2 (Pix compartilhada) só é crítica com 3 ou mais contas (`qtd_creators_mesma_pix ≥ 2`).
5. **Segurança do agente em camadas:** o `sqlglot` valida a árvore (só SELECT, só `vw_*`, LIMIT ≤ 200, sem `main.`)
   **e** a conexão é `mode=ro` + `query_only`. Garantias críticas ficam no código, nunca só no prompt.
6. **Anti-alucinação:** `checagem.py` exige que todo número e ID do relatório venha das evidências (aceita razões,
   ex.: 14/40 = 35%). Se falhar 2 vezes, a confiança vira BAIXA. Hashes são mascarados (`***abcd`) no texto e nas evidências gravadas.
7. **Fallback:** se a API falhar, o relatório é gerado só com as consultas canônicas, com confiança BAIXA, e o saque continua RETIDO.
8. **Roteamento por complexidade:** caso "claro" (prob ≥ 0,90 e ≥ 1 regra) vai direto para a redação (1 chamada).
   Caso ambíguo recebe investigação completa (~6 chamadas, até 3 iterações de SQL).
9. **O gabarito nunca chega ao agente** e só aparece na aba Resultados, apresentado como "resultado confirmado".

## Interface (padrão exigido pelo usuário)
- **Paleta YouShop:** azul-marinho `#1B2F52`, verde-limão `#8CD43A`, fundo `#F5F7FA`, cartões brancos. Fonte Plus Jakarta Sans.
  Tema em `.streamlit/config.toml`.
- **Risco sempre em %**, com escala verde → âmbar → laranja → vermelho (`ui.cor_risco`), **limitado a 99%**.
- **Sem emojis nem ícones genéricos.** Use os ícones SVG de `ui.py` ou `:material/...:` do Streamlit.
- **Sem códigos internos na tela:** `F2_REDE_PIX`, `R1_...`, "gabarito", "E4", "|SHAP|" etc. Toda nomenclatura
  de cliente fica em `app/dados.py` (`NOMES_REGRAS`, `NOMES_TIPOS`, `texto_cliente`, `valor_feature`).
  O teste `tests/test_app.py` varre todas as telas atrás desses códigos.
- Glossário de tela: Dossiê → **Relatório de investigação**; evidência → **Prova N** / "Ver dados de origem";
  MÉDIO → **Em observação**; falso positivo → **Retido sem necessidade**; precisão/recall → **Acerto nas retenções** /
  **Fraudes identificadas**.
- **Prazo em horas úteis** (48 h, seg a sex, das 9h às 18h). O relógio da demo é `dados.AGORA_DEMO` = 26/11/2026 15h.
- **Sempre confira o visual por print** depois de mudar a UI. Os testes passavam com os ícones invisíveis.
  Há um script de captura com Playwright (Chromium já instalado no venv).

## Armadilhas conhecidas
- **`st.html` remove `<svg>` embutido.** Converta para `<img src="data:image/svg+xml;base64,...">` (`ui._img_svg`).
  Animações precisam ir dentro do próprio SVG.
- **`AppTest`:** os botões da barra lateral/popover vêm depois dos da página. Selecione botões pelo `label`, nunca por índice.
- **Gemini:** `gemini-2.5-flash` foi aposentado para contas novas (404). O padrão é `gemini-3.5-flash-lite`
  (~15 s por relatório), e o `3.5-flash` levou 80 s e consultou o futuro. O free tier responde 429 (cota). O `GeminiLLM`
  tenta de novo com espera, e o lote para depois de 3 fallbacks seguidos e retoma de onde parou.
- **`.env`** guarda a `GOOGLE_API_KEY` e fica no `.gitignore`. Nunca leia nem exiba o conteúdo. Para checar a chave, só imprima o tamanho.
- **`git push` precisa ser feito pelo usuário** no terminal dele, porque o shell do agente não autentica no GitHub.
  Commits podem ser feitos aqui, terminando com a linha `Co-Authored-By` indicada pelo sistema.
- **PowerShell 5.1:** aspas duplas dentro de here-string quebram `git commit -m`. Use `git commit -F <arquivo>`.
- **Correlação espúria conhecida:** `qtd_vendas` é a feature de maior ganho porque o gerador planta vendas extras nos
  fraudadores. Está documentada como limite em `docs/recalibracao.md`.

## Resultados atuais (base sintética, 1.158 saques)
Recall 85% · precisão 94% · 0 de 30 virais retidos · R$ 16.158 de fraude × R$ 143 de legítimos retidos ·
90 relatórios, 0 fallbacks, 1,1% com número não confirmado, 14,6 s em média. A IA recomendou liberar 4 dos 5
retidos sem necessidade, mas também 7 dos 85 fraudadores. É o argumento para manter o humano no circuito.

## Próximos passos
Ver `ESTADO.md`.
