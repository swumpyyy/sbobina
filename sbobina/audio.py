"""Preparazione dell'audio con ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class ErroreAudio(RuntimeError):
    pass


def ffmpeg_disponibile() -> bool:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        try:  # il pacchetto pip static-ffmpeg (usato su Windows) scarica ffmpeg e lo mette nel PATH
            import static_ffmpeg

            static_ffmpeg.add_paths()
        except Exception:  # noqa: BLE001 - non installato o senza rete: resta il messaggio sotto
            pass
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _esegui(comando: list[str]) -> str:
    if not ffmpeg_disponibile():
        raise ErroreAudio(
            "ffmpeg non è installato: installalo (es. 'pip install static-ffmpeg', 'brew install ffmpeg' o 'sudo apt install ffmpeg')."
        )
    risultato = subprocess.run(comando, capture_output=True, text=True)
    if risultato.returncode != 0:
        dettaglio = (risultato.stderr or "").strip().splitlines()[-3:]
        raise ErroreAudio("ffmpeg non è riuscito a leggere l'audio: " + " | ".join(dettaglio))
    return risultato.stdout


def durata(percorso: Path) -> float:
    uscita = _esegui([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(percorso),
    ])
    try:
        return float(uscita.strip())
    except ValueError as e:
        raise ErroreAudio(f"Durata dell'audio non leggibile per {percorso.name}") from e


def prepara_per_trascrizione(sorgente: Path, destinazione: Path) -> Path:
    """Converte in FLAC mono 16 kHz (lossless) e uniforma il volume.

    - highpass toglie rimbombi e ronzii sotto la voce;
    - dynaudnorm alza le parti in cui il docente si allontana dal microfono
      senza saturare quelle vicine.
    Tutti i motori ricevono lo stesso file, così i tempi delle trascrizioni coincidono.
    """
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    _esegui([
        "ffmpeg", "-nostdin", "-y", "-i", str(sorgente), "-vn",
        "-af", "highpass=f=70,dynaudnorm=f=250:g=15:p=0.9",
        "-ac", "1", "-ar", "16000", "-c:a", "flac", str(destinazione),
    ])
    return destinazione


def prepara_per_ascolto(sorgente: Path, destinazione: Path) -> Path:
    """Copia compressa per il player del browser: MP3 a bitrate costante, riproducibile ovunque."""
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    _esegui([
        "ffmpeg", "-nostdin", "-y", "-i", str(sorgente), "-vn", "-ac", "1",
        "-c:a", "libmp3lame", "-b:a", "64k", str(destinazione),
    ])
    return destinazione
