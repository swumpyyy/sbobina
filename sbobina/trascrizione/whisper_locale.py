"""Trascrizione locale con Whisper (faster-whisper): gratuita e offline."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from sbobina.trascrizione.base import Avanzamento, ErroreTrascrizione, Parola, Trascrizione

_modelli: dict[tuple[str, str], object] = {}
_blocco = threading.Lock()


def prompt_iniziale(contesto: str, termini: list[str], limite: int = 600) -> str:
    """Testo di innesco nello stile della lezione: aiuta Whisper con grafia e punteggiatura."""
    prompt = contesto.strip()
    if termini:
        prompt += (" " if prompt else "") + "Termini: " + ", ".join(termini) + "."
    return prompt[:limite].rsplit(" ", 1)[0] if len(prompt) > limite else prompt


def parole_suggerite(termini: list[str], limite: int = 300) -> str:
    """Termini ripetuti in ogni finestra di 30 s (a differenza del prompt iniziale)."""
    testo = ""
    for termine in termini:
        candidato = f"{testo}, {termine}" if testo else termine
        if len(candidato) > limite:
            break
        testo = candidato
    return testo


def campioni_16k(audio: Path):
    """Decodifica con ffmpeg in campioni float32 mono a 16 kHz, il formato che Whisper si aspetta.

    Evita il decoder interno di faster-whisper (PyAV), che si rompe con alcune versioni di `av`.
    """
    import numpy as np

    risultato = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(audio), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True,
    )
    if risultato.returncode != 0:
        dettaglio = risultato.stderr.decode(errors="replace").strip()[-300:]
        raise ErroreTrascrizione(f"Audio non leggibile per Whisper: {dettaglio}")
    return np.frombuffer(risultato.stdout, dtype=np.float32)


class MotoreWhisper:
    nome = "whisper"

    def __init__(self, modello: str = "large-v3", dispositivo: str = "auto"):
        self.modello = modello
        self.dispositivo = dispositivo

    def _carica(self):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise ErroreTrascrizione(
                "Per la trascrizione locale installa faster-whisper: pip install -e '.[locale]'"
            ) from e
        chiave = (self.modello, self.dispositivo)
        with _blocco:
            if chiave not in _modelli:
                _modelli[chiave] = WhisperModel(self.modello, device=self.dispositivo, compute_type="auto")
            return _modelli[chiave]

    def trascrivi(
        self, audio: Path, *, lingua: str, termini: list[str], contesto: str, avanzamento: Avanzamento
    ) -> Trascrizione:
        modello = self._carica()
        segmenti, info = modello.transcribe(
            campioni_16k(audio),
            language=lingua,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 700},
            word_timestamps=True,
            # Evita i "loop" di frasi ripetute tipici di Whisper su audio lunghi.
            condition_on_previous_text=False,
            initial_prompt=prompt_iniziale(contesto, termini) or None,
            hotwords=parole_suggerite(termini) or None,
        )
        parole: list[Parola] = []
        for segmento in segmenti:
            for w in segmento.words or []:
                testo = w.word.strip()
                if testo:
                    parole.append(Parola(float(w.start), float(w.end), testo, float(w.probability)))
            if info.duration:
                avanzamento(min(1.0, segmento.end / info.duration))
        avanzamento(1.0)
        return Trascrizione(self.nome, parole, float(info.duration))
