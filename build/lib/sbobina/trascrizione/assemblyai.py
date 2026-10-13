"""Trascrizione cloud con AssemblyAI (modello Universal-3.5 Pro)."""

from __future__ import annotations

import time
from pathlib import Path

import httpx2

from sbobina.trascrizione.base import (
    Avanzamento,
    ErroreTrascrizione,
    Parola,
    Trascrizione,
    filtra_termini,
)

BASE = "https://api.assemblyai.com"
MODELLI = ["universal-3-5-pro", "universal-2"]


class MotoreAssemblyAI:
    nome = "assemblyai"

    def __init__(self, chiave: str, *, base: str = BASE, client: httpx2.Client | None = None, attesa: float = 5.0):
        self.chiave = chiave
        self.base = base.rstrip("/")
        self.client = client or httpx2.Client(timeout=httpx2.Timeout(60.0, read=900.0, write=900.0))
        self.attesa = attesa

    def _controlla(self, risposta: httpx2.Response, fase: str) -> dict:
        if risposta.status_code >= 400:
            raise ErroreTrascrizione(
                f"AssemblyAI ({fase}): errore {risposta.status_code} - {risposta.text[:300]}"
            )
        return risposta.json()

    def trascrivi(
        self, audio: Path, *, lingua: str, termini: list[str], contesto: str, avanzamento: Avanzamento
    ) -> Trascrizione:
        intestazioni = {"authorization": self.chiave}
        risposta = self.client.post(f"{self.base}/v2/upload", headers=intestazioni, content=audio.read_bytes())
        url_audio = self._controlla(risposta, "caricamento")["upload_url"]
        avanzamento(0.1)

        corpo = {
            "audio_url": url_audio,
            "speech_models": MODELLI,
            "language_code": lingua,
            "punctuate": True,
            "format_text": True,
        }
        parole_chiave = filtra_termini(termini, massimo=1000, max_parole=6, max_caratteri=100)
        if parole_chiave:
            corpo["keyterms_prompt"] = parole_chiave
        risposta = self.client.post(f"{self.base}/v2/transcript", headers=intestazioni, json=corpo)
        if risposta.status_code == 400 and "keyterms_prompt" in corpo:
            # Se il modello scelto non accetta i termini per questa lingua, meglio trascrivere senza.
            corpo.pop("keyterms_prompt")
            risposta = self.client.post(f"{self.base}/v2/transcript", headers=intestazioni, json=corpo)
        id_trascrizione = self._controlla(risposta, "invio")["id"]

        while True:
            dati = self._controlla(
                self.client.get(f"{self.base}/v2/transcript/{id_trascrizione}", headers=intestazioni), "stato"
            )
            stato = dati.get("status")
            if stato == "completed":
                break
            if stato == "error":
                raise ErroreTrascrizione(f"AssemblyAI: {dati.get('error') or 'trascrizione fallita'}")
            avanzamento(0.5 if stato == "processing" else 0.2)
            time.sleep(self.attesa)

        parole = [
            Parola(w["start"] / 1000, w["end"] / 1000, w["text"], w.get("confidence"))
            for w in dati.get("words") or []
            if (w.get("text") or "").strip()
        ]
        avanzamento(1.0)
        return Trascrizione(self.nome, parole, dati.get("audio_duration"))
