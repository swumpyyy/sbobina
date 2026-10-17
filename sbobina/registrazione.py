"""Registrazione dal microfono con ffmpeg (avfoundation su macOS, dshow su Windows), con il livello reale per il VU meter."""

from __future__ import annotations

import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

WINDOWS = sys.platform == "win32"
PERMESSO = ("Impostazioni → Privacy e sicurezza → Microfono (attiva \"Consenti alle app desktop\")" if WINDOWS
            else "Impostazioni di Sistema → Privacy e sicurezza → Microfono")


def microfono_windows() -> str:
    """Il primo microfono che vede DirectShow: su Windows ffmpeg vuole il nome, non un numero."""
    uscita = subprocess.run(
        ["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stderr
    trovato = re.search(r'"([^"]+)" \(audio\)', uscita)
    if not trovato:
        raise RuntimeError(f"Non trovo nessun microfono: controlla che sia collegato e il permesso in {PERMESSO}.")
    return trovato.group(1)


RE_LIVELLO = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+|-inf)")


class Registratore:
    """Una registrazione alla volta. Lo stato (secondi, livello in dB, pausa) si legge da `stato()`.

    La pausa chiude il pezzo in corso e la ripresa ne apre uno nuovo: alla fine ffmpeg li unisce
    senza ricodificare. Fermare ffmpeg con SIGSTOP non va: il microfono continua e l'audio si accumula.
    """

    def __init__(self, cartella: Path):
        self.cartella = cartella
        self._processo: subprocess.Popen | None = None
        self._pezzi: list[Path] = []
        self._nome = ""
        self._inizio = 0.0
        self._accumulati = 0.0  # secondi dei pezzi già chiusi
        self._in_pausa = False
        self._livello = -90.0
        self._errore = ""
        self._segnale = False  # è arrivata almeno una misura dal microfono
        self._lock = threading.Lock()

    @property
    def attiva(self) -> bool:
        return self._processo is not None and self._processo.poll() is None

    @property
    def in_corso(self) -> bool:
        """Registra oppure è in pausa: la sessione non è ancora chiusa."""
        return self.attiva or self._in_pausa

    def avvia(self, dispositivo: str = ":0") -> None:
        with self._lock:
            if self.in_corso:
                raise RuntimeError("Sto già registrando.")
            self.cartella.mkdir(parents=True, exist_ok=True)
            self._nome = time.strftime("registrazione-%Y%m%d-%H%M%S")
            self._pezzi, self._accumulati, self._errore = [], 0.0, ""
            self._avvia_pezzo(dispositivo)

    def pausa(self) -> None:
        with self._lock:
            if not self.attiva:
                raise RuntimeError("Non c'è nessuna registrazione in corso.")
            self._chiudi_processo()
            self._accumulati += time.monotonic() - self._inizio
            self._in_pausa = True
            self._livello = -90.0

    def riprendi(self, dispositivo: str = ":0") -> None:
        with self._lock:
            if not self._in_pausa:
                raise RuntimeError("La registrazione non è in pausa.")
            self._avvia_pezzo(dispositivo)
            self._in_pausa = False

    def _avvia_pezzo(self, dispositivo: str) -> None:
        file = self.cartella / f"{self._nome}-{len(self._pezzi) + 1}.m4a"
        self._segnale = False
        self._livello = -90.0
        # astats misura ogni ~0,1 s; ametadata stampa il livello su stdout, che leggiamo in un thread.
        comando = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            *(["-f", "dshow", "-i", f"audio={microfono_windows()}"] if WINDOWS else ["-f", "avfoundation", "-i", dispositivo]),
            "-af", "asetnsamples=4410,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
            "-ac", "1", "-c:a", "aac", "-b:a", "96k", str(file),
        ]
        try:
            self._processo = subprocess.Popen(
                comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
        except OSError as e:
            raise RuntimeError(f"Non riesco ad avviare ffmpeg: {e}") from e
        self._pezzi.append(file)
        self._inizio = time.monotonic()
        threading.Thread(target=self._leggi, args=(self._processo,), daemon=True).start()

    def _leggi(self, processo: subprocess.Popen) -> None:
        for riga in processo.stdout:  # type: ignore[union-attr]
            trovato = RE_LIVELLO.search(riga)
            if trovato:
                self._segnale = True
                valore = trovato.group(1)
                self._livello = -90.0 if valore == "-inf" else max(-90.0, float(valore))
        errore = (processo.stderr.read() if processo.stderr else "").strip()  # type: ignore[union-attr]
        if processo.returncode not in (0, None, 255) and errore:
            self._errore = _messaggio(errore)

    def stato(self) -> dict:
        if self._processo is not None and self._processo.poll() is not None and not self._errore and self._processo.returncode not in (0, 255):
            self._errore = "La registrazione si è interrotta."
        pezzo = time.monotonic() - self._inizio if self.attiva else 0.0
        if self.attiva and not self._segnale and pezzo > 5 and not self._errore:
            # Senza permesso il sistema non consegna l'audio: ffmpeg resta fermo senza errori.
            self._errore = f"Il microfono non manda audio: dai a Sbobina il permesso in {PERMESSO}, poi riprova."
        return {
            "attiva": self.in_corso,
            "pausa": self._in_pausa,
            "secondi": round(self._accumulati + pezzo, 1) if self.in_corso else 0,
            "livello": round(self._livello, 1),
            "errore": self._errore,
        }

    def _chiudi_processo(self) -> None:
        processo = self._processo
        if processo is None or processo.poll() is not None:
            return
        try:
            processo.stdin.write("q")  # type: ignore[union-attr]
            processo.stdin.flush()  # type: ignore[union-attr]
        except (BrokenPipeError, OSError):
            pass
        # "q" chiude il file per bene; poi SIGINT (fa lo stesso, non su Windows); kill solo se ffmpeg è bloccato.
        for passo in ("aspetta", "interrompi", "uccidi"):
            if passo == "interrompi" and not WINDOWS:
                processo.send_signal(signal.SIGINT)
            elif passo == "uccidi":
                processo.kill()
            try:
                processo.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                continue

    def ferma(self) -> Path:
        """Chiude la registrazione, unisce i pezzi e restituisce il file audio."""
        with self._lock:
            if not self.in_corso and not self._pezzi:
                raise RuntimeError("Non c'è nessuna registrazione in corso.")
            self._chiudi_processo()
            self._processo, self._in_pausa = None, False
            pezzi = [p for p in self._pezzi if p.is_file() and p.stat().st_size >= 1000]
            if not pezzi:
                self._butta()
                raise RuntimeError(self._errore or "La registrazione è vuota: controlla il permesso del microfono.")
            file = self.cartella / f"{self._nome}.m4a"
            if len(pezzi) == 1:
                pezzi[0].replace(file)
            else:
                elenco = self.cartella / f"{self._nome}.txt"
                elenco.write_text("".join(f"file '{p.name}'\n" for p in pezzi), encoding="utf-8")
                unione = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                     "-i", str(elenco), "-c", "copy", str(file)],
                    capture_output=True, text=True,
                )
                elenco.unlink(missing_ok=True)
                if unione.returncode != 0 or not file.is_file():
                    # I pezzi restano nella cartella delle registrazioni: niente audio perso.
                    self._pezzi = []
                    raise RuntimeError(f"Non riesco a unire i pezzi della registrazione: {unione.stderr[-200:]}")
            self._butta()
            return file

    def _butta(self) -> None:
        for p in self._pezzi:
            p.unlink(missing_ok=True)
        self._pezzi = []

    def annulla(self) -> None:
        try:
            self.ferma().unlink(missing_ok=True)
        except RuntimeError:
            pass


def _messaggio(errore: str) -> str:
    if "not authorized" in errore.lower() or "permission" in errore.lower():
        return f"Sbobina non ha il permesso di usare il microfono: aprilo in {PERMESSO}."
    return f"Errore del microfono: {errore[-200:]}"
