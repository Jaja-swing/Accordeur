"""
gui.py — Interface tkinter : note, fréquence, écart en cents, aiguille, bouton.

Aucun calcul audio ici : on demande les samples à `AudioInput`, on les envoie à
`pitch.detect_pitch`, puis on affiche le résultat.
"""

import math
import tkinter as tk
from tkinter import messagebox

import config
from audio import AudioError, AudioInput
from pitch import PitchSmoother, detect_pitch, freq_to_note

# Géométrie du cadran (canvas)
W, H = 420, 250
CX, CY = W // 2, 225          # pivot de l'aiguille
RADIUS = 175                  # rayon de l'arc
NEEDLE_LEN = 160
MAX_ANGLE = 70                # degrés de part et d'autre de la verticale


def _polar(length: float, angle_deg: float):
    """Point à `length` du pivot, `angle_deg` par rapport à la verticale
    (positif = vers la droite)."""
    a = math.radians(angle_deg)
    return CX + length * math.sin(a), CY - length * math.cos(a)


def _cents_to_angle(cents: float) -> float:
    c = max(-config.GAUGE_RANGE_CENTS, min(config.GAUGE_RANGE_CENTS, cents))
    return c / config.GAUGE_RANGE_CENTS * MAX_ANGLE


class TunerApp:
    """Fenêtre principale de l'accordeur."""

    def __init__(self, audio: AudioInput):
        self.audio = audio
        self.smoother = PitchSmoother()
        self._misses = 0                 # nb de mesures vides consécutives
        self._needle_cents = 0.0         # position affichée (lissée)
        self._target_cents = 0.0         # position visée
        self._has_note = False
        self._after_id = None

        self.root = tk.Tk()
        self.root.title("Accordeur chromatique")
        self.root.configure(bg=config.COLOR_BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self._build_widgets()
        self._show_idle()

    # -- Construction de l'interface ----------------------------------------
    def _build_widgets(self) -> None:
        bg, fg, muted = config.COLOR_BG, config.COLOR_TEXT, config.COLOR_MUTED

        self.note_var = tk.StringVar()
        self.freq_var = tk.StringVar()
        self.cents_var = tk.StringVar()
        self.hint_var = tk.StringVar()

        self.note_label = tk.Label(self.root, textvariable=self.note_var,
                                   font=("Helvetica", 64, "bold"), bg=bg, fg=fg)
        self.note_label.pack(pady=(14, 0))

        self.freq_label = tk.Label(self.root, textvariable=self.freq_var,
                                   font=("Helvetica", 16), bg=bg, fg=muted)
        self.freq_label.pack()

        self.canvas = tk.Canvas(self.root, width=W, height=H, bg=bg,
                                highlightthickness=0)
        self.canvas.pack(pady=(6, 0))
        self._draw_dial()

        self.cents_label = tk.Label(self.root, textvariable=self.cents_var,
                                    font=("Helvetica", 22, "bold"), bg=bg, fg=fg)
        self.cents_label.pack()

        self.hint_label = tk.Label(self.root, textvariable=self.hint_var,
                                   font=("Helvetica", 12), bg=bg, fg=muted)
        self.hint_label.pack(pady=(0, 8))

        self.button = tk.Button(self.root, text="Démarrer", width=16,
                                font=("Helvetica", 14, "bold"),
                                command=self.toggle)
        self.button.pack(pady=(0, 18))

    def _draw_dial(self) -> None:
        """Dessine le cadran fixe (arc, zone verte, graduations) + l'aiguille."""
        c = self.canvas
        box = (CX - RADIUS, CY - RADIUS, CX + RADIUS, CY + RADIUS)

        # Arc complet (gris) sur toute la plage utile
        c.create_arc(*box, start=90 - MAX_ANGLE, extent=2 * MAX_ANGLE,
                     style=tk.ARC, outline=config.COLOR_PANEL, width=14)

        # Zone "accordé" (verte), centrée sur 0 cent
        tol = _cents_to_angle(config.IN_TUNE_CENTS)
        c.create_arc(*box, start=90 - tol, extent=2 * tol,
                     style=tk.ARC, outline=config.COLOR_OK, width=14)

        # Graduations tous les 10 cents, étiquettes tous les 25
        step = 10
        rng = config.GAUGE_RANGE_CENTS
        for cents in range(-rng, rng + 1, step):
            ang = _cents_to_angle(cents)
            major = cents % 50 == 0
            x1, y1 = _polar(RADIUS - (22 if major else 18), ang)
            x2, y2 = _polar(RADIUS - 9, ang)
            c.create_line(x1, y1, x2, y2, fill=config.COLOR_MUTED,
                          width=3 if major else 1)
        for cents, txt in ((-rng, f"-{rng}"), (0, "0"), (rng, f"+{rng}")):
            x, y = _polar(RADIUS - 38, _cents_to_angle(cents))
            c.create_text(x, y, text=txt, fill=config.COLOR_MUTED,
                          font=("Helvetica", 10))

        # Aiguille (coordonnées mises à jour à chaque image) + pivot
        x, y = _polar(NEEDLE_LEN, 0)
        self.needle = c.create_line(CX, CY, x, y, width=5, capstyle=tk.ROUND,
                                    fill=config.COLOR_MUTED)
        c.create_oval(CX - 9, CY - 9, CX + 9, CY + 9,
                      fill=config.COLOR_PANEL, outline=config.COLOR_MUTED, width=2)

    # -- Contrôles ------------------------------------------------------------
    def toggle(self) -> None:
        if self.audio.running:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        try:
            self.audio.start()
        except AudioError as exc:
            messagebox.showerror("Microphone", str(exc), parent=self.root)
            return
        self.smoother.reset()
        self._misses = 0
        self.button.config(text="Arrêter")
        self._schedule()

    def stop(self) -> None:
        self.audio.stop()
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.button.config(text="Démarrer")
        self._show_idle()

    def close(self) -> None:
        """Fermeture propre : coupe le micro puis détruit la fenêtre."""
        self.audio.stop()
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.root.destroy()

    # -- Boucle de mise à jour -------------------------------------------------
    def _schedule(self) -> None:
        self._after_id = self.root.after(config.UPDATE_MS, self._tick)

    def _tick(self) -> None:
        if not self.audio.running:
            return
        samples = self.audio.get_latest()
        result = detect_pitch(samples, self.audio.sample_rate) if samples is not None else None

        if result is not None:
            self._misses = 0
            freq = self.smoother.update(result.frequency)   # fréquence lissée
            self._show_note(freq_to_note(freq))
        else:
            self._misses += 1
            if self._misses >= config.HOLD_FRAMES:
                self.smoother.reset()
                self._has_note = False
                self._show_waiting()

        self._animate_needle()
        self._schedule()

    # -- Affichage ---------------------------------------------------------------
    def _show_note(self, res) -> None:
        ok = abs(res.cents) <= config.IN_TUNE_CENTS
        color = config.COLOR_OK if ok else config.COLOR_BAD
        self._has_note = True
        self._target_cents = res.cents
        self.note_var.set(f"{res.note}{res.octave}")
        self.freq_var.set(f"{res.frequency:.1f} Hz")
        self.cents_var.set(f"{res.cents:+.0f} cents")
        self.note_label.config(fg=color)
        self.cents_label.config(fg=color)
        if ok:
            self.hint_var.set("Accordé")
        elif res.cents < 0:
            self.hint_var.set("Trop grave : tendre la corde")
        else:
            self.hint_var.set("Trop aigu : détendre la corde")

    def _show_waiting(self) -> None:
        self.note_var.set("--")
        self.freq_var.set("--- Hz")
        self.cents_var.set("")
        self.hint_var.set("Jouez une note…")
        self.note_label.config(fg=config.COLOR_MUTED)
        self._target_cents = 0.0

    def _show_idle(self) -> None:
        self._has_note = False
        self._show_waiting()
        self.hint_var.set("Appuyez sur Démarrer")
        self._needle_cents = 0.0
        self._move_needle(config.COLOR_MUTED)

    def _animate_needle(self) -> None:
        """Rapproche l'aiguille de sa cible (mouvement fluide)."""
        self._needle_cents += (self._target_cents - self._needle_cents) * config.NEEDLE_SMOOTHING
        if not self._has_note:
            color = config.COLOR_MUTED
        elif abs(self._target_cents) <= config.IN_TUNE_CENTS:
            color = config.COLOR_OK
        else:
            color = config.COLOR_BAD
        self._move_needle(color)

    def _move_needle(self, color: str) -> None:
        x, y = _polar(NEEDLE_LEN, _cents_to_angle(self._needle_cents))
        self.canvas.coords(self.needle, CX, CY, x, y)
        self.canvas.itemconfig(self.needle, fill=color)

    # -- Lancement -------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()
