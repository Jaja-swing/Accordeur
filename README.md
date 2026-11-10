# Accordeur chromatique

Détecteur de note et accordeur chromatique en temps réel.
Python · tkinter · sounddevice · numpy.

Affiche la **note**, la **fréquence (Hz)**, l'**écart en cents** et une **aiguille**
(verte = accordé, rouge = désaccordé).

## Installation et lancement

```bash
pip install -r requirements.txt
python main.py
```

Cliquez sur **Démarrer**, autorisez le micro si le système le demande, puis jouez une note.

### Prérequis par système

| Système | À faire |
|---|---|
| **Windows** | Rien de plus (Python de python.org inclut tkinter). |
| **macOS** | Python de python.org. Autoriser le micro pour le Terminal (Réglages > Confidentialité > Micro). |
| **Linux (Debian/Ubuntu)** | `sudo apt install python3-tk libportaudio2` |

Python 3.8 ou plus récent.

## Structure

```
accordeur/
├── main.py            Point d'entrée
├── audio.py           Capture micro (sounddevice) + tampon circulaire
├── pitch.py           FFT, détection du fondamental, conversion note/cents
├── gui.py             Interface tkinter (note, Hz, cents, aiguille, bouton)
├── config.py          Tous les réglages
├── requirements.txt   numpy, sounddevice
├── README.md
└── docs/
    ├── rapport.pdf            Schéma + explication de la méthode (1 page)
    └── generer_rapport.py     Script qui régénère le PDF
```

## Fonctionnement en bref

`micro → tampon de 8192 échantillons → fenêtre de Hann → FFT → pic (HPS + interpolation parabolique) → fréquence → note + cents`

Détails illustrés dans `docs/rapport.pdf`.

## Réglages (`config.py`)

| Paramètre | Effet |
|---|---|
| `A4_FREQ` | Diapason (440 Hz par défaut) |
| `MIN_RMS` | Seuil de niveau : monter si l'appli réagit au bruit ambiant, baisser si elle ne détecte pas un son faible |
| `IN_TUNE_CENTS` | Tolérance « accordé » (5 cents par défaut) |
| `BUFFER_SIZE` | Taille d'analyse : plus grand = plus précis dans les graves, mais plus de latence |
| `MIN_FREQ` / `MAX_FREQ` | Plage de détection (40 à 1500 Hz) |
| `SMOOTH_WINDOW` | Lissage des mesures |

## Vérifier sans micro

```bash
python pitch.py
```

Lance un auto-test sur des signaux synthétiques (notes graves et aiguës, harmoniques
faibles, bruit, silence). Doit afficher `TOUS LES TESTS PASSENT`.

## Régénérer le PDF (optionnel)

```bash
pip install matplotlib reportlab
python docs/generer_rapport.py
```

## Dépannage

- **« Impossible d'ouvrir le microphone »** : vérifier le micro par défaut du système et les autorisations.
- **`OSError: PortAudio library not found`** (Linux) : `sudo apt install libportaudio2`.
- **`No module named tkinter`** (Linux) : `sudo apt install python3-tk`.
- **Affiche « -- » en permanence** : jouer plus fort / plus près du micro, ou baisser `MIN_RMS`.
- **Aiguille instable** : jouer une note seule (un accord n'a pas de fondamental unique) et augmenter `SMOOTH_WINDOW`.
