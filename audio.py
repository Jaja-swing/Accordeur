"""
audio.py — Capture du microphone en continu (sounddevice).

Le flux audio tourne dans un thread géré par PortAudio. Chaque bloc reçu est
copié dans un tampon circulaire ; l'interface lit ce tampon quand elle veut
via `get_latest()`.
"""

import threading
from typing import Optional

import numpy as np

import config

try:
    import sounddevice as sd
    _SD_ERROR = None
except Exception as exc:  # PortAudio absent, paquet non installé, etc.
    sd = None
    _SD_ERROR = exc


class AudioError(RuntimeError):
    """Erreur lisible par l'utilisateur (micro absent, accès refusé, etc.)."""


class AudioInput:
    """Capture mono depuis le micro par défaut et conserve les derniers samples."""

    def __init__(self, buffer_size: int = config.BUFFER_SIZE,
                 block_size: int = config.BLOCK_SIZE, device=None):
        self.buffer_size = buffer_size
        self.block_size = block_size
        self.device = device           # None = micro par défaut du système
        self.sample_rate: float = 44100.0
        self._buffer = np.zeros(buffer_size, dtype=np.float32)
        self._filled = 0               # nb de samples valides reçus (plafonné)
        self._lock = threading.Lock()
        self._stream = None

    # -- Démarrage / arrêt ---------------------------------------------------
    @property
    def running(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        """Ouvre le micro. Lève AudioError avec un message clair en cas d'échec."""
        if self.running:
            return
        if sd is None:
            raise AudioError(
                "La bibliothèque audio (sounddevice/PortAudio) est indisponible.\n"
                f"Détail : {_SD_ERROR}\n\n"
                "Linux : sudo apt install libportaudio2\n"
                "Autres : pip install -r requirements.txt")
        try:
            info = sd.query_devices(self.device, "input")
            # On utilise la fréquence native du micro : évite les erreurs de format.
            self.sample_rate = float(info["default_samplerate"])
            self._reset_buffer()
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.block_size,
                device=self.device,
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise AudioError(
                "Impossible d'ouvrir le microphone.\n"
                "Vérifiez qu'un micro est branché et que l'application a "
                "l'autorisation de l'utiliser (macOS / Windows : paramètres de "
                f"confidentialité).\n\nDétail : {exc}") from exc

    def stop(self) -> None:
        """Ferme le micro (sans erreur si déjà fermé)."""
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    # -- Tampon --------------------------------------------------------------
    def _reset_buffer(self) -> None:
        with self._lock:
            self._buffer[:] = 0.0
            self._filled = 0

    def _push(self, data: np.ndarray) -> None:
        """Ajoute des samples à la fin du tampon circulaire."""
        data = np.asarray(data, dtype=np.float32).ravel()
        n = data.size
        if n == 0:
            return
        with self._lock:
            if n >= self.buffer_size:
                self._buffer[:] = data[-self.buffer_size:]
            else:
                self._buffer[:-n] = self._buffer[n:]
                self._buffer[-n:] = data
            self._filled = min(self.buffer_size, self._filled + n)

    def _callback(self, indata, frames, time_info, status) -> None:
        # Appelé par PortAudio : doit rester rapide et ne jamais lever d'exception.
        self._push(indata[:, 0])

    def get_latest(self) -> Optional[np.ndarray]:
        """Retourne une copie des derniers `buffer_size` samples,
        ou None tant que le tampon n'est pas entièrement rempli."""
        with self._lock:
            if self._filled < self.buffer_size:
                return None
            return self._buffer.copy()
