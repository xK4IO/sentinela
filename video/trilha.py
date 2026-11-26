"""Trilha original sintetizada (sem direitos de terceiros), planejada pela narração.

100 BPM, Am7 - Fmaj7 - Cmaj7 - G6, 2 compassos por acorde. Seções (segundos do vídeo):
  0     a 18,5   intro: só pad (gancho e problema)
  18,5  a 113,6  groove: kick, hi-hat, baixo, arpejo (solução, funcionamento, demo, bastidores, resultados)
  118,2 a 119,2  riser de ruído; impacto grave exatamente no "7" (119,18 s)
  119,2 a 124,9  groove cheio (o humano decide)
  124,9 ao fim   só pad + fade de 2 s (assinatura)
Saída: assets/music.wav (44,1 kHz, estéreo)
"""
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100
DUR = 131.0
BPM = 100
BEAT = 60 / BPM
T0 = 0.4                     # primeira batida
GROOVE, RISER, IMPACTO, CHEIO, OUTRO = 18.5, 118.18, 119.18, 119.18, 124.9
n = int(SR * DUR)
t = np.arange(n) / SR
rng = np.random.default_rng(42)


def hz(midi):
    return 440 * 2 ** ((midi - 69) / 12)


ACORDES = [[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 59], [55, 59, 62, 64]]  # Am7 Fmaj7 Cmaj7 G6
TONICA = [45, 41, 36, 43]
COMPASSO = 4 * BEAT


def acorde_em(s):
    return int(max(0, s - T0) // (2 * COMPASSO)) % 4


def env(x0, x1, a=0.01, r=0.2):
    """Envelope trapezoidal (ataque a, release r) entre x0 e x1."""
    e = np.clip((t - x0) / a, 0, 1) * np.clip((x1 - t) / r, 0, 1)
    return e


def lp(sig, f):
    return sosfilt(butter(4, f, "low", fs=SR, output="sos"), sig)


def hp(sig, f):
    return sosfilt(butter(2, f, "high", fs=SR, output="sos"), sig)


# pad: serras desafinadas, passa-baixa ~1 kHz, troca de acorde suave
pad = np.zeros(n, np.float32)
saw = lambda f, ph=0: 2 * ((t * f + ph) % 1) - 1
inicio = T0
while inicio < DUR:
    fim = inicio + 2 * COMPASSO
    notas = ACORDES[acorde_em(inicio + 0.01)]
    e = env(inicio - 0.3, fim + 0.3, a=0.6, r=0.6)
    for m in notas:
        for d in (-0.08, 0.08):
            pad += (e * saw(hz(m) * 2 ** (d / 12), rng.random())).astype(np.float32) * 0.045
    inicio = fim
pad = lp(pad, 1000)
pad *= np.clip(t / 2.0, 0, 1)

# bateria e baixo só nas seções de groove
def ativo(s):
    return (GROOVE <= s < RISER) or (CHEIO <= s < OUTRO)


kick = np.zeros(n, np.float32)
hat = np.zeros(n, np.float32)
baixo = np.zeros(n, np.float32)
pluck = np.zeros(n, np.float32)
k_len = int(SR * 0.35)
kt = np.arange(k_len) / SR
f_k = 45 + 75 * np.exp(-kt * 28)                      # pitch caindo de 120 para 45 Hz
k_wave = np.sin(2 * np.pi * np.cumsum(f_k) / SR) * np.exp(-kt * 9)
h_len = int(SR * 0.06)
h_wave = hp(rng.standard_normal(h_len), 7000) * np.exp(-np.arange(h_len) / SR * 60)
b = T0
i = 0
while b < DUR:
    if ativo(b):
        j = int(b * SR)
        cheio = b >= CHEIO
        kick[j:j + k_len] += (k_wave[: n - j] * 0.9).astype(np.float32)
        jh = int((b + BEAT / 2) * SR)                   # hi-hat no contratempo
        if jh + h_len < n:
            hat[jh:jh + h_len] += (h_wave * (0.28 if cheio else 0.2)).astype(np.float32)
        # baixo na tônica, uma nota por tempo
        f0 = hz(TONICA[acorde_em(b + 0.01)])
        L = int(SR * BEAT * 0.9)
        seg = np.arange(min(L, n - j)) / SR
        baixo[j:j + len(seg)] += (np.sin(2 * np.pi * f0 * seg) * np.exp(-seg * 3) * 0.35).astype(np.float32)
        # arpejo de pluck em colcheias
        for half in (0, 1):
            jp = int((b + half * BEAT / 2) * SR)
            notas = ACORDES[acorde_em(b + 0.01)]
            fp = hz(notas[(i * 2 + half) % 4] + 12)
            Lp = int(SR * 0.25)
            sp = np.arange(min(Lp, n - jp)) / SR
            pluck[jp:jp + len(sp)] += (np.sign(np.sin(2 * np.pi * fp * sp)) * np.exp(-sp * 18)
                                       * (0.07 if cheio else 0.05)).astype(np.float32)
    b += BEAT
    i += 1
pluck = lp(pluck, 2500)

# riser de ruído (1 s) e impacto grave no "7"
riser = np.zeros(n, np.float32)
j0, j1 = int(RISER * SR), int(IMPACTO * SR)
rr = rng.standard_normal(j1 - j0) * np.linspace(0, 1, j1 - j0) ** 2
riser[j0:j1] = hp(rr, 1500) * 0.35
imp = np.zeros(n, np.float32)
L = int(SR * 1.6)
it = np.arange(L) / SR
imp_wave = np.sin(2 * np.pi * np.cumsum(40 + 60 * np.exp(-it * 6)) / SR) * np.exp(-it * 2.2)
imp[j1:j1 + L] = imp_wave * 1.1

mix = pad + kick + hat + baixo + pluck + riser + imp
mix *= np.clip((DUR - t) / 2.0, 0, 1)                 # fade final de 2 s
mix = np.tanh(mix * 1.2)
mix = mix / np.max(np.abs(mix)) * 0.89
# estéreo leve: hi-hat e pluck um pouco abertos
esq = mix + 0.15 * (hat - pluck)
dir_ = mix - 0.15 * (hat - pluck)
st = np.stack([esq, dir_], 1)
st = st / np.max(np.abs(st)) * 0.89
out = Path(__file__).parent / "assets" / "music.wav"
wavfile.write(out, SR, (st * 32767).astype(np.int16))
print("ok", out, f"{DUR} s")
