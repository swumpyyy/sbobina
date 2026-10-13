"""Registrazione dal microfono con ffmpeg (avfoundation su macOS), con il livello reale per il VU meter."""

from __future__ import annotations

import re
import subprocess
import threading
import time
from pathlib import Path

RE_LIVELLO = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+|-inf)")


class Registratore:
    """Una registrazione alla volta. Lo stato (secondi, livello in dB) si legge da `stato()`."""

    def __init__(self, cartella: Path):
        self.cartella = cartella
        self._processo: subprocess.Popen | None = None
        self._file: Path | None = None
        self._inizio = 0.0
        self._livello = -90.0
        self._errore = ""
        self._lock = threading.Lock()

    @property
    def attiva(self) -> bool:
        return self._processo is not None and self._processo.poll() is None

    def avvia(self, dispositivo: str = ":0") -> None:
        with self._lock:
            if self.attiva:
                raise RuntimeError("Sto già registrando.")
            self.cartella.mkdir(parents=True, exist_ok=True)
            self._file = self.cartella / time.strftime("registrazione-%Y%m%d-%H%M%S.m4a")
            self._errore = ""
            self._livello = -90.0
            # astats misura ogni ~0,1 s; ametadata stampa il livello su stdout, che leggiamo in un thread.
            comando = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-f", "avfoundation", "-i", dispositivo,
                "-af", "asetnsamples=4410,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
                "-ac", "1", "-c:a", "aac", "-b:a", "96k", str(self._file),
            ]
            try:
                self._processo = subprocess.Popen(
                    comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
            except OSError as e:
                raise RuntimeError(f"Non riesco ad avviare ffmpeg: {e}") from e
            self._inizio = time.monotonic()
            threading.Thread(target=self._leggi, args=(self._processo,), daemon=True).start()

    def _leggi(self, processo: subprocess.Popen) -> None:
        for riga in processo.stdout:  # type: ignore[union-attr]
            trovato = RE_LIVELLO.search(riga)
            if trovato:
                valore = trovato.group(1)
                self._livello = -90.0 if valore == "-inf" else max(-90.0, float(valore))
        errore = (processo.stderr.read() if processo.stderr else "").strip()  # type: ignore[union-attr]
        if processo.returncode not in (0, None, 255) and errore:
            self._errore = _messaggio(errore)

    def stato(self) -> dict:
        if self._processo is not None and self._processo.poll() is not None and not self._errore and self._processo.returncode not in (0, 255):
            self._errore = "La registrazione si è interrotta."
        return {
            "attiva": self.attiva,
            "secondi": round(time.monotonic() - self._inizio, 1) if self.attiva else 0,
            "livello": round(self._livello, 1),
            "errore": self._errore,
        }

    def ferma(self) -> Path:
        """Chiude la registrazione e restituisce il file audio."""
        with self._lock:
            processo, file = self._processo, self._file
            if processo is None or file is None:
                raise RuntimeError("Non c'è nessuna registrazione in corso.")
            if processo.poll() is None:
                try:
                    processo.stdin.write("q")  # type: ignore[union-attr]
                    processo.stdin.flush()  # type: ignore[union-attr]
                except (BrokenPipeError, OSError):
                    pass
                try:
                    processo.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    processo.terminate()
                    processo.wait(timeout=5)
            self._processo = None
            if not file.is_file() or file.stat().st_size < 1000:
                raise RuntimeError(self._errore or "La registrazione è vuota: controlla il permesso del microfono.")
            return file

    def annulla(self) -> None:
        try:
            self.ferma().unlink(missing_ok=True)
        except RuntimeError:
            pass


def _messaggio(errore: str) -> str:
    if "not authorized" in errore.lower() or "permission" in errore.lower():
        return "Sbobina non ha il permesso di usare il microfono: aprilo in Impostazioni di Sistema → Privacy → Microfono."
    return f"Errore del microfono: {errore[-200:]}"
