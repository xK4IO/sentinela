# Roteiro do vídeo de apresentação: Sentinela (YouShop)

Formato vertical 1080x1920, cerca de 2 min 20 s. Cerca de 320 palavras, lidas a ~2,5 palavras por segundo.
Leia uma frase por vez, com uma pausa curta entre os blocos. Se errar, repita a frase inteira e siga.
Todos os números vêm da base sintética do projeto (ver `CLAUDE.md`, seção "Resultados atuais").

| # | Bloco | Narração | Na tela |
|---|---|---|---|
| 1 | Gancho (0–8 s) | Toda semana, creators sacam comissões na YouShop. E se parte desse dinheiro vier de fraude? | Valor em reais subindo; a palavra "fraude" aparece em destaque |
| 2 | Problema (8–25 s) | Autocompra. Cartão de terceiros. Contas diferentes recebendo na mesma chave Pix. Quando a fraude aparece, o dinheiro já saiu, e o estorno vira prejuízo. | Os três tipos de fraude entrando um a um; o dinheiro saindo da tela |
| 3 | Solução (25–45 s) | Eu construí o Sentinela. Ele analisa cada pedido de saque antes de o dinheiro sair. Se encontra sinais de fraude, não bloqueia ninguém: ele retém o saque e entrega ao analista um relatório com provas. | Logo do Sentinela; pedido de saque passando por um "portão" e ficando retido |
| 4 | Como funciona (45–75 s) | Por baixo, são três camadas. Sete regras de negócio, objetivas e fáceis de explicar. Um modelo LightGBM, que compara cada creator com fraudes já vistas. E um agente de IA, com Gemini, que investiga o caso consultando os dados e escreve o relatório. Cada número do relatório é conferido na origem. | Pipeline vertical preenchendo camada por camada |
| 5 | Demonstração (75–105 s) | Na tela do analista, a fila mostra o risco e o prazo de cada caso. Ao abrir um caso, ele lê as provas, vê a consulta que gerou cada uma e o mapa de contas ligadas. A decisão é dele: liberar ou negar, com comentário registrado para auditoria. | Prints reais: fila, caso C0040 com o grafo da rede, painel de decisão |
| 6 | Bastidores (105–135 s) | Três aprendizados mudaram o projeto. A fórmula de risco da especificação só identificava 51% das fraudes. Recalibrada, chegou a 85%. Um modelo de IA maior ignorou o prompt e consultou dados do futuro. A correção foi no código, não no texto. E casos claros usam uma única chamada de IA, o que cortou 52% das chamadas. | Três cartões: contador 51% → 85%; "prompt" riscado e "código" no lugar; barra caindo 52% |
| 7 | Resultados (135–155 s) | Numa base simulada de 1.158 saques, o Sentinela identificou 85% das fraudes, com 94% de acerto nas retenções. Nenhum dos 30 creators em crescimento rápido foi retido. Foram 16 mil reais de fraude segurados, contra 143 reais de creators legítimos. | Contadores subindo; grade de pontos (fraude × legítimo) |
| 8 | Clímax (155–170 s) | Mas o número mais importante é outro. Seguida sem revisão, a IA teria liberado 7 fraudadores. Por isso ela só recomenda. Quem decide é sempre uma pessoa. | Pausa; "7" gigante (zoom, único da peça); "quem decide é uma pessoa" |
| 9 | Fechamento (170–178 s) | Sentinela. Proteção de saques antes de o dinheiro sair. Eu sou Caio Esteves. | Assinatura com traço; subtítulo "Desafio de Inovação YouShop 2027" |

## Texto corrido (para ler na gravação)

Toda semana, creators sacam comissões na YouShop. E se parte desse dinheiro vier de fraude?

Autocompra. Cartão de terceiros. Contas diferentes recebendo na mesma chave Pix. Quando a fraude aparece, o dinheiro já saiu, e o estorno vira prejuízo.

Eu construí o Sentinela. Ele analisa cada pedido de saque antes de o dinheiro sair. Se encontra sinais de fraude, não bloqueia ninguém: ele retém o saque e entrega ao analista um relatório com provas.

Por baixo, são três camadas. Sete regras de negócio, objetivas e fáceis de explicar. Um modelo LightGBM, que compara cada creator com fraudes já vistas. E um agente de IA, com Gemini, que investiga o caso consultando os dados e escreve o relatório. Cada número do relatório é conferido na origem.

Na tela do analista, a fila mostra o risco e o prazo de cada caso. Ao abrir um caso, ele lê as provas, vê a consulta que gerou cada uma e o mapa de contas ligadas. A decisão é dele: liberar ou negar, com comentário registrado para auditoria.

Três aprendizados mudaram o projeto. A fórmula de risco da especificação só identificava 51% das fraudes. Recalibrada, chegou a 85%. Um modelo de IA maior ignorou o prompt e consultou dados do futuro. A correção foi no código, não no texto. E casos claros usam uma única chamada de IA, o que cortou 52% das chamadas.

Numa base simulada de 1.158 saques, o Sentinela identificou 85% das fraudes, com 94% de acerto nas retenções. Nenhum dos 30 creators em crescimento rápido foi retido. Foram 16 mil reais de fraude segurados, contra 143 reais de creators legítimos.

Mas o número mais importante é outro. Seguida sem revisão, a IA teria liberado 7 fraudadores. Por isso ela só recomenda. Quem decide é sempre uma pessoa.

Sentinela. Proteção de saques antes de o dinheiro sair. Eu sou Caio Esteves.
