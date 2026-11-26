"""Edita a narração: encurta pausas e troca respirações por silêncio limpo, usando os tempos do whisper.

Entrada: work/raw.wav (passa-alta 80 Hz) e work/palavras.json
Saída:   work/voz_editada.wav e work/palavras_editadas.json (tempos já no áudio editado)

Ideia: a fala é o que está entre o início e o fim das palavras. Pausa curta (< 0,30 s) fica como está,
porque é respiro natural da frase. Pausa longa vira silêncio digital curto: 0,25 s no meio da frase e
0,45 s depois de ponto. O que havia nela (respiração, ruído) some.
"""
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

W = Path(__file__).parent / "work"
sr, x = wavfile.read(W / "raw.wav")
x = x.astype(np.float32) / 32768
pal = json.loads((W / "palavras.json").read_text(encoding="utf-8"))

# energia em janelas de 10 ms, para não cortar o fim de consoantes que o whisper encurta
hop = sr // 100
nfr = len(x) // hop
db = 20 * np.log10(np.sqrt(np.array([np.mean(x[i * hop:(i + 1) * hop] ** 2) for i in range(nfr)])) + 1e-9)


def estende_fim(t, limite):
    """Avança o fim enquanto ainda há voz (> -40 dB), até 150 ms e sem passar da próxima palavra."""
    i = int(t * 100)
    fim = min(int((t + 0.15) * 100), int(limite * 100), nfr - 1)
    while i < fim and db[i] > -40:
        i += 1
    return i / 100


# blocos de fala contínua: palavras separadas por menos de 0,30 s ficam juntas
blocos = []
for k, (a, b, w) in enumerate(pal):
    prox = pal[k + 1][0] if k + 1 < len(pal) else len(x) / sr
    b = max(b, estende_fim(b, prox - 0.02))
    a = max(0.0, a - 0.04)
    if blocos and a - blocos[-1]["fim"] < 0.30:
        blocos[-1]["fim"] = b
        blocos[-1]["pal"].append(k)
    else:
        blocos.append({"ini": a, "fim": b, "pal": [k]})

FADE = int(sr * 0.010)
rampa = np.linspace(0, 1, FADE, dtype=np.float32)
saida, novos = [np.zeros(int(sr * 0.35), np.float32)], {}
t_out = 0.35
for j, bl in enumerate(blocos):
    i0, i1 = int(bl["ini"] * sr), int(bl["fim"] * sr) + int(sr * 0.04)
    trecho = x[i0:i1].copy()
    trecho[:FADE] *= rampa
    trecho[-FADE:] *= rampa[::-1]
    for k in bl["pal"]:  # tempos das palavras no áudio novo
        a, b, w = pal[k]
        novos[k] = [round(t_out + (a - bl["ini"]), 3), round(t_out + (b - bl["ini"]), 3), w]
    saida.append(trecho)
    t_out += len(trecho) / sr
    if j + 1 < len(blocos):
        ultima = pal[bl["pal"][-1]][2]
        pausa = 0.45 if ultima.endswith((".", "?", "!")) else 0.25
        saida.append(np.zeros(int(sr * pausa), np.float32))
        t_out += pausa
saida.append(np.zeros(int(sr * 0.6), np.float32))
y = np.concatenate(saida)
wavfile.write(W / "voz_editada.wav", sr, (np.clip(y, -1, 1) * 32767).astype(np.int16))
(W / "palavras_editadas.json").write_text(json.dumps([novos[k] for k in sorted(novos)], ensure_ascii=False),
                                          encoding="utf-8")
print(f"original {len(x) / sr:.1f} s  editado {len(y) / sr:.1f} s  blocos {len(blocos)}")
