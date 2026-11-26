"""Alinha o roteiro (texto certo) aos tempos do whisper (texto com erros de reconhecimento).

Compara palavra a palavra com difflib; palavra do roteiro sem par recebe o tempo interpolado das vizinhas.
Saída: work/frases.json  [{"bloco": n, "texto": "...", "ini": s, "fim": s, "palavras": [[ini, fim, w], ...]}]
"""
import difflib
import json
import re
import unicodedata
from pathlib import Path

W = Path(__file__).parent / "work"
pal = json.loads((W / "palavras_editadas.json").read_text(encoding="utf-8"))

ROTEIRO = [
    (1, "Toda semana, creators sacam comissões na YouShop."),
    (1, "E se parte desse dinheiro vier de fraude?"),
    (2, "Autocompra. Cartão de terceiros. Contas diferentes recebendo na mesma chave Pix."),
    (2, "Quando a fraude aparece, o dinheiro já saiu, e o estorno vira prejuízo."),
    (3, "Eu construí o Sentinela."),
    (3, "Ele analisa cada pedido de saque antes de o dinheiro sair."),
    (3, "Se encontra sinais de fraude, não bloqueia ninguém:"),
    (3, "ele retém o saque e entrega ao analista um relatório com provas."),
    (4, "Por baixo, são três camadas."),
    (4, "Sete regras de negócio, objetivas e fáceis de explicar."),
    (4, "Um modelo LightGBM, que compara cada creator com fraudes já vistas."),
    (4, "E um agente de IA, com Gemini, que investiga o caso consultando os dados e escreve o relatório."),
    (4, "Cada número do relatório é conferido na origem."),
    (5, "Na tela do analista, a fila mostra o risco e o prazo de cada caso."),
    (5, "Ao abrir um caso, ele lê as provas, vê a consulta que gerou cada uma e o mapa de contas ligadas."),
    (5, "A decisão é dele: liberar ou negar, com comentário registrado para auditoria."),
    (6, "Três aprendizados mudaram o projeto."),
    (6, "A fórmula de risco da especificação só identificava 51% das fraudes."),
    (6, "Recalibrada, chegou a 85%."),
    (6, "Um modelo de IA maior ignorou o prompt e consultou dados do futuro."),
    (6, "A correção foi no código, não no texto."),
    (6, "E casos claros usam uma única chamada de IA, o que cortou 52% das chamadas."),
    (7, "Numa base simulada de 1.158 saques, o Sentinela identificou 85% das fraudes, com 94% de acerto nas retenções."),
    (7, "Nenhum dos 30 creators em crescimento rápido foi retido."),
    (7, "Foram 16 mil reais de fraude segurados, contra 143 reais de creators legítimos."),
    (8, "Mas o número mais importante é outro."),
    (8, "Seguida sem revisão, a IA teria liberado 7 fraudadores."),
    (8, "Por isso ela só recomenda."),
    (8, "Quem decide é sempre uma pessoa."),
    (9, "Sentinela. Proteção de saques antes de o dinheiro sair."),
    (9, "Eu sou Caio Esteves."),
]


def norm(w):
    w = unicodedata.normalize("NFKD", w.lower())
    return re.sub(r"[^a-z0-9%]", "", "".join(c for c in w if not unicodedata.combining(c)))


rot = [(i, w) for i, (_, f) in enumerate(ROTEIRO) for w in f.split()]
a = [norm(w) for _, w in rot]
b = [norm(w[2]) for w in pal]
tempo = [None] * len(rot)
for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
    tag, i1, i2, j1, j2 = blk
    if tag == "equal":
        for k in range(i2 - i1):
            tempo[i1 + k] = pal[j1 + k][:2]
    elif tag == "replace" and j2 > j1:  # trecho trocado: espalha os tempos do whisper pelas palavras do roteiro
        t0, t1 = pal[j1][0], pal[j2 - 1][1]
        n = i2 - i1
        for k in range(n):
            tempo[i1 + k] = [round(t0 + (t1 - t0) * k / n, 3), round(t0 + (t1 - t0) * (k + 1) / n, 3)]
# palavras sem par: interpola entre vizinhas
for k in range(len(tempo)):
    if tempo[k] is None:
        ant = next((tempo[j][1] for j in range(k - 1, -1, -1) if tempo[j]), 0.3)
        pos = next((tempo[j][0] for j in range(k + 1, len(tempo)) if tempo[j]), ant + 0.3)
        tempo[k] = [ant, max(ant + 0.05, pos)]

frases = []
for i, (bloco, f) in enumerate(ROTEIRO):
    ws = [[*tempo[k], w] for k, (fi, w) in enumerate(rot) if fi == i]
    frases.append({"bloco": bloco, "texto": f, "ini": ws[0][0], "fim": ws[-1][1], "palavras": ws})
(W / "frases.json").write_text(json.dumps(frases, ensure_ascii=False, indent=1), encoding="utf-8")
sem_par = sum(1 for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if o[0] != "equal")
print(f"{len(rot)} palavras do roteiro, {len(pal)} do whisper, {sem_par} trechos divergentes")
for fr in frases:
    print(f"{fr['bloco']} {fr['ini']:6.2f}-{fr['fim']:6.2f} {fr['texto'][:70]}")
