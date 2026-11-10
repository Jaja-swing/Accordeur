"""
main.py — Point d'entrée de l'accordeur chromatique.

Lancement :   python main.py
"""

import sys


def main() -> int:
    try:
        import tkinter  # noqa: F401  (vérifie sa présence avant d'aller plus loin)
    except ImportError:
        print("tkinter est introuvable.\n"
              "  Linux (Debian/Ubuntu) : sudo apt install python3-tk\n"
              "  Windows / macOS       : réinstallez Python depuis python.org "
              "(tkinter est inclus).")
        return 1

    from audio import AudioInput
    from gui import TunerApp

    app = TunerApp(AudioInput())
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
