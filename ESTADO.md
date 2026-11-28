# ESTADO: ponto de retomada do Sentinela

> Atualizado em **25/11/2026**. Entrega: **29/11/2026 às 23:59** (faltam 4 dias).
> Ao começar uma sessão nova: leia `CLAUDE.md` (regras do projeto) e depois este arquivo (onde paramos).
> Ao terminar uma sessão: atualize as seções "Onde paramos" e "Próximos passos".

## Para retomar em 1 minuto
Cole isto numa sessão nova do Claude Code, aberta na pasta `sentinela`:

```
Leia CLAUDE.md e ESTADO.md e continue o projeto Sentinela de onde paramos.
Antes de mexer em algo, me diga em 3 linhas o que entendeu do estado atual.
```

## Cronograma

| Dia | Etapa | Situação |
|---|---|---|
| D1 · 24/11 | Base sintética, schema, views, testes | ✅ Concluído |
| D2 · 24/11 | Features, regras, LightGBM OOF, score, métricas e recalibração | ✅ Concluído (P 94% · R 85%) |
| D3 · 24/11 | Agente LangGraph + Gemini, 90 relatórios gerados | ✅ Concluído (0 fallbacks) |
| D4 · 24/11 | Interface Streamlit com o visual da YouShop | ✅ Concluído (visual aprovado pelo usuário em 25/11) |
| D5 · 25–28/11 | Push, deploy no Streamlit Cloud, link público | ⏳ Em andamento |
| D6 · 27–28/11 | 12 slides | ⬜ Não iniciado |
| D7 · 29/11 | Vídeo de backup da demo, revisão e envio | ⬜ Não iniciado |

## Onde paramos
1. O usuário **aprovou o visual** em 25/11.
2. A decisão de teste foi apagada (`resetar_demo()`): 0 revisões, 90 saques retidos, 90 relatórios. Os 56 testes passaram.
3. `CLAUDE.md`, `ESTADO.md` e o banco limpo foram commitados. **Falta o `git push`**, que o usuário faz no terminal dele.
4. Nenhum processo fica rodando entre sessões. O Streamlit local precisa ser iniciado de novo (ver comandos no `CLAUDE.md`).
5. **25/11 (tarde): revisão de UX aplicada, ainda sem commit.** Uma crítica por prints virou ajustes em `app/`:
   fila desempata o risco pelo prazo, só a exceção ganha cor no status do relatório, filtro de valor por faixas,
   recomendação e confiança juntas no caso, sem rótulos internos duplicados nos cartões, rede vazia numa linha só,
   Observação sem colunas repetidas, Resultados sem "retido sem necessidade" entre os tipos de fraude e com a frase
   "a IA teria liberado 7 fraudadores", texto da IA limpo na exibição (chargeback → contestação de cartão, sem
   "(prova N)" dentro da própria prova, dias sem decimais). Mais 4 testes (`tests/test_texto_cliente.py`): 60 passam.
   Commitado em `263a614` (é a versão atual da interface).
6. **25/11 (noite):** a skill `impeccable` foi instalada em `~/.claude/skills/impeccable` e `/impeccable critique`
   deu 24/40. Uma rodada de ajustes baseada nela (decisão fixa ao lado, sem cartões, tese em faixa em Resultados etc.)
   foi **rejeitada pelo usuário e descartada**. Não reaplicar sem pedido explícito.
7. **25/11 (noite): vídeo de apresentação v1 pronto** em `video/renders/sentinela-youshop.mp4` (1080x1920, 2 min 11 s,
   −15,9 LUFS). Roteiro em `docs/roteiro-video.md`, gravado pelo usuário. Fonte do vídeo em `video/`:
   `editar_voz.py` (corta pausas), `transcrever.py` (faster-whisper), `alinhar.py`, `trilha.py` (música original),
   `gen.py` + `style.css` + `timeline.js` (HyperFrames). Paleta e logo do Sentinela. Os arquivos pesados ficam no `.gitignore`.
   Resultados ainda não commitados: o banner de Resultados ("7 fraudadores" no topo) em `app/streamlit_app.py` e a pasta `video/`.

## Git

| Item | Situação |
|---|---|
| `625b5e7` protótipo completo (D1–D3 + UI v1) | ✅ No GitHub |
| `1927a95` interface com a identidade da YouShop | ⚠️ Só local: **falta o push** |
| Commit de 25/11 (`CLAUDE.md`, `ESTADO.md`, banco limpo) | ⚠️ Só local: **falta o push** |

Se testar decisões na demo local, rode de novo "Reiniciar demonstração" antes de commitar o banco.

## Próximos passos (em ordem)
1. O usuário roda `git push` e confere no GitHub que os 3 commits subiram.
2. Deploy no Streamlit Community Cloud (o usuário faz pelo site):
   repo `caio-esteves/sentinela` · branch `main` · arquivo `app/streamlit_app.py` · Python 3.12 · **sem secrets**.
   Depois, abra o link público e confira as 4 abas e um caso.
3. Slides: 12, conforme o mapa da seção 12.3 da doc técnica. Material pronto em `docs/recalibracao.md`,
   `docs/agente.md`, `README.md` e na aba Resultados. Formato (PDF, Google Slides etc.) a combinar com o usuário.
4. Gravar o vídeo de backup da demo (até 8 min) e fazer a revisão final.

## Decisões em aberto
- Nome final da solução ("Sentinela" ainda é provisório).
- Formato da entrega: slides **e** vídeo, mas o formato exato não foi definido.
- O plugin `frontend-design` foi sugerido pelo usuário. Ele instala com
  `claude plugin install frontend-design@claude-plugins-official` e só vale numa sessão nova.

## Histórias boas para a apresentação (já medidas)
- **A fórmula da spec falhava:** a média ponderada impedia o modelo de chegar a ALTO sozinho (recall 51%). Com o `max()`
  e a R2 exigindo 3 ou mais contas, chegou a 85% de recall e 94% de precisão. Ver `docs/recalibracao.md`.
- **Prompt não é controle de segurança:** o modelo maior ignorou o prompt e consultou o futuro (7 chargebacks em vez
  de 2). A correção foi estrutural, com as views point-in-time. Ver `docs/agente.md`.
- **Roteamento por complexidade:** todos os 5 falsos positivos estavam nos 28 casos ambíguos. Os casos claros usam 1 chamada (−52% no total).
- **Humano no circuito:** a IA liberou 4 dos 5 legítimos retidos, mas também 7 fraudadores (ex.: C1991, autocompra, que
  a IA aceitou como "vendas para familiares"). Seguida às cegas, a cobertura cairia de 85% para 78%.
- **Casos para a demo:** C0040 (rede Pix com grafo), C1805 (legítimo que o modelo errou e a IA mandou liberar),
  C1991 (fraudador que a IA mandou liberar) e algum caso com análise "Aprofundada" (auditoria das SQLs).
