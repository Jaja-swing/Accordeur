"""
pitch.py — Détection de la fréquence fondamentale et conversion en note.

Chaîne de traitement (identique à celle décrite dans docs/rapport.pdf) :
    signal -> fenêtrage (Hann) -> FFT -> détection du pic -> fréquence -> note

Ce module ne dépend NI de tkinter NI de sounddevice : il peut être testé seul
(`python pitch.py` lance un auto-test sur des signaux synthétiques).
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

import config


@dataclass
class PitchResult:
    """Résultat d'une détection."""
    frequency: float   # Hz, fréquence fondamentale mesurée
    note: str          # ex. "La" ou "Do#"
    octave: int        # ex. 4 pour La4
    cents: float       # écart à la note la plus proche, de -50 à +50
    target_freq: float # fréquence exacte de la note la plus proche (Hz)


# --------------------------------------------------------------------------
# Conversion fréquence -> note
# --------------------------------------------------------------------------
def freq_to_note(freq: float, a4: float = config.A4_FREQ) -> PitchResult:
    """Convertit une fréquence en note + écart en cents.

    n = 69 + 12 * log2(f / A4)   (numéro MIDI "flottant", 69 = La4)
    La note est l'entier le plus proche ; l'écart en cents vaut 100 * (n - arrondi).
    """
    midi_float = 69.0 + 12.0 * np.log2(freq / a4)
    midi = int(round(midi_float))
    cents = (midi_float - midi) * 100.0
    name = config.NOTE_NAMES[midi % 12]
    octave = midi // 12 - 1
    target = a4 * 2.0 ** ((midi - 69) / 12.0)
    return PitchResult(freq, name, octave, cents, target)


# --------------------------------------------------------------------------
# Détection du fondamental
# --------------------------------------------------------------------------
def _parabolic_peak(mag: np.ndarray, k: int) -> float:
    """Affine la position d'un pic (en bins) par interpolation parabolique
    sur le log du spectre. Retourne une position fractionnaire."""
    if k <= 0 or k >= len(mag) - 1:
        return float(k)
    a, b, c = np.log(mag[k - 1:k + 2] + 1e-12)
    denom = a - 2.0 * b + c
    if abs(denom) < 1e-12:
        return float(k)
    return k + 0.5 * (a - c) / denom


def detect_pitch(samples: np.ndarray, sample_rate: float) -> Optional[PitchResult]:
    """Détecte la fréquence fondamentale d'un bloc de samples mono (float, -1..1).

    Retourne None si le signal est trop faible ou sans hauteur claire.
    """
    x = np.asarray(samples, dtype=np.float64)
    if x.size < 1024:
        return None

    # 1) Retirer la composante continue puis vérifier le niveau (porte de bruit)
    x = x - x.mean()
    if np.sqrt(np.mean(x ** 2)) < config.MIN_RMS:
        return None

    # 2) Fenêtrage de Hann : limite les "fuites" spectrales
    x = x * np.hanning(x.size)

    # 3) FFT (zero-padding pour un spectre plus finement échantillonné)
    n_fft = x.size * config.ZERO_PAD
    mag = np.abs(np.fft.rfft(x, n=n_fft))
    bin_hz = sample_rate / n_fft

    # 4) Produit spectral harmonique (HPS) : on multiplie le spectre par ses
    #    versions sous-échantillonnées (÷2, ÷3, ÷4). Seule la vraie fondamentale
    #    voit ses harmoniques s'aligner -> évite les erreurs d'octave.
    n_h = config.HPS_HARMONICS
    m = len(mag[::n_h])
    hps = mag[:m].copy()
    for h in range(2, n_h + 1):
        hps *= mag[::h][:m]

    k_min = max(1, int(config.MIN_FREQ / bin_hz))
    k_max = min(m - 1, int(config.MAX_FREQ / bin_hz))
    if k_max <= k_min + 2:
        return None

    k_hps = k_min + int(np.argmax(hps[k_min:k_max]))

    # 5) Recaler sur le vrai maximum du spectre brut (±3 bins) puis interpoler
    lo, hi = max(1, k_hps - 3), min(len(mag) - 2, k_hps + 3)
    k = lo + int(np.argmax(mag[lo:hi + 1]))

    # Cas des sons quasi purs (diapason, sifflement) : sans harmoniques, le HPS
    # n'a rien à aligner. Si le candidat HPS n'a presque aucune énergie réelle
    # (< 5 % du plus gros pic), on retombe sur le pic brut du spectre.
    k_raw = k_min + int(np.argmax(mag[k_min:k_max]))
    if mag[k] < 0.05 * mag[k_raw]:
        k = k_raw

    # Porte de confiance : le pic doit nettement dépasser le bruit de fond
    floor = np.median(mag[k_min:k_max]) + 1e-12
    if mag[k] / floor < config.MIN_PEAK_RATIO:
        return None

    freq = _parabolic_peak(mag, k) * bin_hz
    if not (config.MIN_FREQ <= freq <= config.MAX_FREQ):
        return None

    return freq_to_note(freq)


# --------------------------------------------------------------------------
# Lissage temporel
# --------------------------------------------------------------------------
class PitchSmoother:
    """Médiane glissante sur les dernières fréquences : supprime les sauts
    isolés. L'historique est vidé si la note change franchement (> 1 demi-ton)."""

    def __init__(self, window: int = config.SMOOTH_WINDOW):
        self._hist = deque(maxlen=window)

    def reset(self) -> None:
        self._hist.clear()

    def update(self, freq: float) -> float:
        if self._hist:
            ref = float(np.median(self._hist))
            if abs(12.0 * np.log2(freq / ref)) > 1.0:
                self._hist.clear()
        self._hist.append(freq)
        return float(np.median(self._hist))


# --------------------------------------------------------------------------
# Auto-test : python pitch.py
# --------------------------------------------------------------------------
def _synth(freq, sr=44100, n=config.BUFFER_SIZE, harmonics=(1.0, 0.5, 0.3, 0.2),
           noise=0.0, seed=0):
    t = np.arange(n) / sr
    sig = sum(a * np.sin(2 * np.pi * freq * (i + 1) * t) for i, a in enumerate(harmonics))
    sig = 0.2 * sig / max(harmonics)
    rng = np.random.default_rng(seed)
    return sig + noise * rng.standard_normal(n)


def _selftest() -> bool:
    cases = [
        ("Mi grave guitare E2", 82.41, {}),
        ("La2", 110.0, {}),
        ("Sol3", 196.0, {}),
        ("La4 diapason", 440.0, {}),
        ("Mi aigu E4", 329.63, {}),
        ("Do6", 1046.5, {}),
        ("La3 +20 cents", 220.0 * 2 ** (20 / 1200), {}),
        ("La3 fondamentale faible", 220.0, {"harmonics": (0.15, 1.0, 0.6, 0.4)}),
        ("La3 bruité", 220.0, {"noise": 0.03}),
        ("Sinus pur 261.63", 261.63, {"harmonics": (1.0,)}),
    ]
    ok_all = True
    for label, f, kw in cases:
        for sr in (44100, 48000):
            r = detect_pitch(_synth(f, sr=sr, **kw), sr)
            good = r is not None and abs(1200 * np.log2(r.frequency / f)) < 3.0
            ok_all &= good
            shown = f"{r.frequency:8.2f} Hz  {r.note}{r.octave} {r.cents:+6.1f}c" if r else "   aucune détection"
            print(f"[{'OK ' if good else 'ÉCHEC'}] {label:26s} sr={sr}  attendu {f:8.2f}  ->  {shown}")
    silence = detect_pitch(np.zeros(config.BUFFER_SIZE), 44100)
    bruit = detect_pitch(0.05 * np.random.default_rng(1).standard_normal(config.BUFFER_SIZE), 44100)
    for label, r in (("Silence", silence), ("Bruit blanc", bruit)):
        good = r is None
        ok_all &= good
        print(f"[{'OK ' if good else 'ÉCHEC'}] {label:26s} -> {'rien détecté (attendu)' if good else 'FAUX POSITIF'}")
    print("\nTOUS LES TESTS PASSENT" if ok_all else "\nDES TESTS ÉCHOUENT")
    return ok_all


if __name__ == "__main__":
    raise SystemExit(0 if _selftest() else 1)
