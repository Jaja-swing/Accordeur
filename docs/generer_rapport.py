"""
generer_rapport.py — Génère docs/rapport.pdf (1 page A4).

Contenu : un schéma signal temporel -> spectre FFT (fondamentale + harmoniques
annotées) et l'explication de l'extraction de la fréquence fondamentale.

Dépendances : pip install numpy matplotlib reportlab
Usage       : python docs/generer_rapport.py      (ou depuis docs/ : python generer_rapport.py)
"""

import os
import tempfile

import matplotlib
matplotlib.use("Agg")  # pas de fenêtre : on écrit directement dans un fichier
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

NOTES = ["Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rapport.pdf")

# Couleurs
C_SIG, C_F0, C_HARM, C_GREY = "#2b6cb0", "#e53e3e", "#dd8a1b", "#718096"


# ---------------------------------------------------------------------------
# 1) Signal synthétique réaliste : La3 légèrement haut + harmoniques + bruit
# ---------------------------------------------------------------------------
SR = 8000                      # Hz  (échantillonnage de la démo)
N = 4096                       # échantillons analysés
F_TRUE = 220.0 * 2 ** (11 / 1200)   # La3 + 11 cents : exemple d'instrument un peu haut
AMPS = [1.0, 0.65, 0.42, 0.26, 0.15]  # amplitudes de H1..H5

t = np.arange(N) / SR
rng = np.random.default_rng(3)
signal = sum(a * np.sin(2 * np.pi * F_TRUE * (i + 1) * t) for i, a in enumerate(AMPS))
signal = signal / np.max(np.abs(signal)) * 0.9 + 0.03 * rng.standard_normal(N)

# ---------------------------------------------------------------------------
# 2) Chaîne : fenêtrage -> FFT -> pic -> fréquence -> note
# ---------------------------------------------------------------------------
windowed = signal * np.hanning(N)
NFFT = N * 4                                   # zero-padding
spec = np.abs(np.fft.rfft(windowed, n=NFFT))
freqs = np.fft.rfftfreq(NFFT, 1 / SR)
spec_db = 20 * np.log10(spec / spec.max() + 1e-9)

band = (freqs > 60) & (freqs < 1500)
k = np.argmax(np.where(band, spec, 0))
# interpolation parabolique autour du pic (précision < 1 bin)
a_, b_, c_ = np.log(spec[k - 1:k + 2])
delta = 0.5 * (a_ - c_) / (a_ - 2 * b_ + c_)
f0 = (k + delta) * SR / NFFT

midi_f = 69 + 12 * np.log2(f0 / 440.0)
midi = int(round(midi_f))
cents = (midi_f - midi) * 100
note_name = f"{NOTES[midi % 12]}{midi // 12 - 1}"


# ---------------------------------------------------------------------------
# 3) Figure : temporel -> spectre
# ---------------------------------------------------------------------------
FIG_W, FIG_H = 7.2, 6.3   # pouces


def make_figure(path: str) -> None:
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False})
    fig = plt.figure(figsize=(FIG_W, FIG_H))
    ax1 = fig.add_axes([0.09, 0.735, 0.89, 0.20])
    ax2 = fig.add_axes([0.09, 0.085, 0.89, 0.44])

    # --- Panneau 1 : domaine temporel -------------------------------------
    n_show = int(0.045 * SR)  # 45 ms
    ax1.plot(t[:n_show] * 1000, signal[:n_show], color=C_SIG, lw=1.3)
    ax1.set_title("1. Signal capté — domaine temporel", loc="left",
                  fontweight="bold", pad=22)
    ax1.set_xlabel("Temps (ms)")
    ax1.set_ylabel("Amplitude")
    ax1.set_ylim(-1.2, 1.2)
    ax1.grid(alpha=0.25)
    # une période annotée entre deux maxima successifs (au-dessus du tracé)
    T_ms = 1000 / f0
    seg = signal[: int(SR / f0 * 1.2)]
    t0 = np.argmax(seg) / SR * 1000
    y = 1.32
    ax1.annotate("", xy=(t0 + T_ms, y), xytext=(t0, y), annotation_clip=False,
                 arrowprops=dict(arrowstyle="<->", color=C_F0, lw=1.4))
    ax1.text(t0 + T_ms + 0.8, y, f"période T = {T_ms:.2f} ms  →  f₀ = 1/T",
             ha="left", va="center", color=C_F0, fontsize=8.5, clip_on=False)

    # --- Panneau 2 : spectre ------------------------------------------------
    m = freqs <= 1300
    ax2.plot(freqs[m], spec_db[m], color=C_SIG, lw=1.2)
    ax2.fill_between(freqs[m], -90, spec_db[m], color=C_SIG, alpha=0.10)
    ax2.set_title("2. Spectre après fenêtrage de Hann + FFT", loc="left",
                  fontweight="bold", pad=8)
    ax2.set_xlabel("Fréquence (Hz)")
    ax2.set_ylabel("Amplitude (dB, rel. au pic)")
    ax2.set_ylim(-80, 42)
    ax2.set_xlim(0, 1300)
    ax2.grid(alpha=0.25)

    # fondamentale : étiquette en haut à gauche, flèche vers le pic
    ax2.axvline(f0, color=C_F0, lw=1, ls="--", alpha=0.7)
    h_f0, = ax2.plot([f0], [spec_db[k]], "o", color=C_F0, ms=7, zorder=5,
                     label="fondamentale f₀")
    ax2.annotate(f"f₀ = {f0:.1f} Hz\n{note_name}  {cents:+.0f} cents",
                 xy=(f0, spec_db[k]), xytext=(15, 24), ha="left", va="center",
                 color=C_F0, fontweight="bold", fontsize=9.5,
                 arrowprops=dict(arrowstyle="->", color=C_F0, lw=1.3))
    # harmoniques : étiquettes juste au-dessus de chaque pic
    h_h = None
    for h in range(2, 6):
        fh = h * f0
        kh = np.argmin(np.abs(freqs - fh))
        h_h, = ax2.plot([fh], [spec_db[kh]], "o", color=C_HARM, ms=5.5, zorder=5,
                        label="harmoniques (multiples de f₀)")
        ax2.text(fh, spec_db[kh] + 5, f"{h}·f₀\n{fh:.0f} Hz", ha="center",
                 va="bottom", color=C_HARM, fontsize=8)
    ax2.legend(handles=[h_f0, h_h], loc="upper right", fontsize=8, frameon=False)

    # flèche entre les deux panneaux
    fig.text(0.535, 0.625, "▼   fenêtrage (Hann)  →  FFT   ▼", ha="center",
             va="center", fontsize=10, fontweight="bold", color=C_GREY)

    fig.savefig(path, dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 4) PDF (reportlab)
# ---------------------------------------------------------------------------
def build_pdf() -> None:
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=16, spaceAfter=2,
                           alignment=TA_LEFT, textColor=colors.HexColor("#1a202c"))
    cell = ParagraphStyle("c", parent=styles["Normal"], fontSize=8.6, leading=11)
    cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")
    head = ParagraphStyle("h", parent=cellb, textColor=colors.white)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=8.2, leading=10.5,
                           textColor=colors.HexColor("#4a5568"))

    with tempfile.TemporaryDirectory() as tmp:
        fig_path = os.path.join(tmp, "fig.png")
        make_figure(fig_path)

        doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                                topMargin=1.3 * cm, bottomMargin=1.2 * cm,
                                title="Extraction de la fréquence fondamentale",
                                author="Accordeur chromatique")
        story = [Paragraph("De l'audio à la note : extraction de la fréquence fondamentale", title)]

        w = A4[0] - 3.2 * cm
        story.append(Image(fig_path, width=w, height=w * FIG_H / FIG_W))
        story.append(Spacer(1, 6))

        rows = [
            [Paragraph("Étape", head), Paragraph("Ce qu'on fait", head), Paragraph("Pourquoi / valeurs utilisées", head)],
            [Paragraph("1. Échantillonnage", cellb),
             Paragraph("Le micro est lu à f<sub>s</sub> (44 100 ou 48 000 Hz). On garde les "
                       "<b>8 192 derniers échantillons</b> dans un tampon.", cell),
             Paragraph("Il faut f<sub>s</sub> &gt; 2 × f<sub>max</sub> (Shannon). 8 192 points = ~186 ms : "
                       "assez pour voir plusieurs périodes d'une note grave.", cell)],
            [Paragraph("2. Fenêtrage", cellb),
             Paragraph("On retire la moyenne puis on multiplie le bloc par une <b>fenêtre de Hann</b> "
                       "(qui tend vers 0 aux bords).", cell),
             Paragraph("Un bloc coupé brutalement « fuit » sur tout le spectre et masque le pic. "
                       "Hann réduit ces fuites.", cell)],
            [Paragraph("3. FFT", cellb),
             Paragraph("La FFT donne l'amplitude à chaque fréquence k × f<sub>s</sub>/N<sub>fft</sub>. "
                       "On ajoute du <b>zero-padding</b> (× 2) pour un spectre plus lisse.", cell),
             Paragraph("Résolution ≈ f<sub>s</sub>/N = 5,4 Hz : insuffisante seule pour accorder "
                       "(1 cent à 440 Hz = 0,25 Hz) → étape 4 indispensable.", cell)],
            [Paragraph("4. Détection du pic", cellb),
             Paragraph("On cherche le maximum dans 40–1 500 Hz, puis on <b>interpole une parabole</b> "
                       "sur les 3 points autour du pic. Un produit spectral harmonique (HPS) évite de "
                       "prendre une harmonique pour la fondamentale.", cell),
             Paragraph("L'interpolation donne une précision de l'ordre du centième de bin (&lt; 1 cent). "
                       "Un pic trop faible face au bruit de fond est rejeté.", cell)],
            [Paragraph("5. Fréquence → note", cellb),
             Paragraph("n = 69 + 12 · log<sub>2</sub>(f / 440) ; note = round(n) ; "
                       "écart en cents = 100 · (n − round(n)).", cell),
             Paragraph(f"Ici : f = {f0:.2f} Hz → n = {midi_f:.3f} → <b>{note_name}</b>, "
                       f"<b>{cents:+.1f} cents</b>. 69 = La4 (MIDI), 1 demi-ton = 100 cents.", cell)],
        ]
        tbl = Table(rows, colWidths=[3.0 * cm, 7.4 * cm, w - 10.4 * cm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6cb0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf2f7")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "Signal de démonstration synthétique (f<sub>s</sub> = 8 000 Hz, N = 4 096) : même chaîne que "
            "<i>pitch.py</i>, avec des paramètres adaptés à l'illustration.", small))
        doc.build(story)
    print(f"PDF généré : {OUT}")
    print(f"f0 mesurée = {f0:.2f} Hz (vraie valeur {F_TRUE:.2f}) -> {note_name} {cents:+.1f} cents")


if __name__ == "__main__":
    build_pdf()
