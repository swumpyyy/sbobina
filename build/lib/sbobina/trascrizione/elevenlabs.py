"""Trascrizione cloud con ElevenLabs Scribe."""

from __future__ import annotations

import math
from pathlib import Path

import httpx2

from sbobina.trascrizione.base import (
    Avanzamento,
    ErroreTrascrizione,
    Parola,
    Trascrizione,
    filtra_termini,
)

URL = "https://api.elevenlabs.io/v1/speech-to-text"


class MotoreElevenLabs:
    nome = "elevenlabs"

    def __init__(
        self, chiave: str, *, url: str = URL, client: httpx2.Client | None = None, modello: str = "scribe_v2"
    ):
        self.chiave = chiave
        self.url = url
        self.modello = modello
        # La richiesta è sincrona: per una lezione di 2 ore la risposta può richiedere vari minuti.
        self.client = client or httpx2.Client(timeout=httpx2.Timeout(60.0, read=3600.0, write=900.0))

    def _invia(self, audio: Path, lingua: str, parole_chiave: list[str]) -> httpx2.Response:
        campi: dict[str, str | list[str]] = {
            "model_id": self.modello,
            "language_code": lingua,
            "timestamps_granularity": "word",
            "tag_audio_events": "false",
        }
        if parole_chiave:
            campi["keyterms"] = parole_chiave
        with audio.open("rb") as f:
            return self.client.post(
                self.url,
                headers={"xi-api-key": self.chiave},
                data=campi,
                files={"file": (audio.name, f, "audio/flac")},
            )

    def trascrivi(
        self, audio: Path, *, lingua: str, termini: list[str], contesto: str, avanzamento: Avanzamento
    ) -> Trascrizione:
        parole_chiave = filtra_termini(
            termini, massimo=1000, max_parole=5, max_caratteri=49, caratteri_vietati="<>{}[]\\"
        )
        avanzamento(0.05)
        risposta = self._invia(audio, lingua, parole_chiave)
        if risposta.status_code in (400, 422) and parole_chiave:
            risposta = self._invia(audio, lingua, [])
        if risposta.status_code >= 400:
            raise ErroreTrascrizione(f"ElevenLabs: errore {risposta.status_code} - {risposta.text[:300]}")
        dati = risposta.json()
        parole = [
            Parola(
                w["start"],
                w["end"],
                w["text"].strip(),
                math.exp(w["logprob"]) if w.get("logprob") is not None else None,
            )
            for w in dati.get("words") or []
            if w.get("type", "word") == "word" and (w.get("text") or "").strip()
        ]
        avanzamento(1.0)
        return Trascrizione(self.nome, parole, dati.get("audio_duration_secs"))
