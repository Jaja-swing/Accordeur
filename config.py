"""
config.py — Tous les réglages de l'accordeur au même endroit.

Modifier une valeur ici suffit : aucun autre fichier n'a besoin d'être touché.
"""

# --------------------------------------------------------------------------
# Référence musicale
# --------------------------------------------------------------------------
A4_FREQ = 440.0  # Fréquence du La4 (diapason). 432.0 est parfois utilisé.

# Noms de notes en notation française (12 demi-tons à partir de Do).
NOTE_NAMES = ["Do", "Do#", "Ré", "Ré#", "Mi", "Fa",
              "Fa#", "Sol", "Sol#", "La", "La#", "Si"]

# --------------------------------------------------------------------------
# Capture audio
# --------------------------------------------------------------------------
BLOCK_SIZE = 1024     # Échantillons par callback audio (~23 ms à 44,1 kHz)
BUFFER_SIZE = 8192    # Échantillons analysés à chaque FFT (~186 ms à 44,1 kHz)
                      # Plus grand = plus précis dans les graves, mais plus lent.

# --------------------------------------------------------------------------
# Détection de hauteur
# --------------------------------------------------------------------------
ZERO_PAD = 2          # Facteur de zero-padding de la FFT (affine la lecture du pic)
MIN_FREQ = 40.0       # Hz — en dessous, on ignore (bruit, ronflement secteur)
MAX_FREQ = 1500.0     # Hz — au-dessus, on ignore
HPS_HARMONICS = 4     # Nb d'harmoniques utilisées pour retrouver le fondamental
MIN_RMS = 0.005       # Niveau minimal du signal (0..1). Augmenter si trop de bruit.
MIN_PEAK_RATIO = 8.0  # Le pic doit dépasser N fois le bruit de fond du spectre
SMOOTH_WINDOW = 5     # Nb de mesures pour le lissage (médiane)

# --------------------------------------------------------------------------
# Interface
# --------------------------------------------------------------------------
UPDATE_MS = 40            # Période de rafraîchissement de l'interface (ms)
HOLD_FRAMES = 8           # Nb de mesures "vides" avant d'afficher "--"
IN_TUNE_CENTS = 5         # |écart| <= 5 cents -> considéré comme accordé (vert)
GAUGE_RANGE_CENTS = 50    # Étendue de l'aiguille : -50 .. +50 cents
NEEDLE_SMOOTHING = 0.35   # 0..1 : plus grand = aiguille plus réactive

COLOR_BG = "#1e1f2b"
COLOR_PANEL = "#2a2c3d"
COLOR_TEXT = "#e8e8f0"
COLOR_MUTED = "#8b8fa8"
COLOR_OK = "#2ecc71"      # vert : accordé
COLOR_BAD = "#e74c3c"     # rouge : désaccordé
