"""Transcreve a narração com tempo por palavra (faster-whisper, local, CPU).

Saída: video/work/palavras.json  [[inicio, fim, "palavra"], ...]
Uso: <venv do whisper>/python video/transcrever.py video/work/raw.wav
"""
import json
import sys
from pathlib import Path

from faster_whisper import WhisperModel

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

# O decodificador do faster-whisper (PyAV) quebrou nesta versão; lemos o WAV e entregamos 16 kHz float32.
sr, x = wavfile.read(sys.argv[1])
x = x.astype(np.float32) / 32768
audio = resample_poly(x, 16000, sr).astype(np.float32)
modelo = WhisperModel("small", device="cpu", compute_type="int8")
segs, info = modelo.transcribe(audio, language="pt", word_timestamps=True, vad_filter=False,
                               initial_prompt="Sentinela, YouShop, creators, LightGBM, Gemini, chave Pix, Caio Esteves.")
palavras, linhas = [], []
for s in segs:
    linhas.append(f"[{s.start:6.2f}-{s.end:6.2f}] {s.text.strip()}")
    for w in s.words:
        palavras.append([round(w.start, 3), round(w.end, 3), w.word.strip()])
out = Path(__file__).parent / "work"
(out / "palavras.json").write_text(json.dumps(palavras, ensure_ascii=False), encoding="utf-8")
(out / "transcricao.txt").write_text("\n".join(linhas), encoding="utf-8")
print("\n".join(linhas))
