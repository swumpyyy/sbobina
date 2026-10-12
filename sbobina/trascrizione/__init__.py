"""Motori di trascrizione disponibili."""

from __future__ import annotations

from sbobina.config import Config
from sbobina.trascrizione.base import ErroreTrascrizione, MotoreTrascrizione, Parola, Trascrizione


def crea_motori(config: Config) -> list[MotoreTrascrizione]:
    motori: list[MotoreTrascrizione] = []
    for nome in config.motori:
        if nome == "assemblyai":
            if not config.assemblyai_chiave:
                raise ErroreTrascrizione("Motore 'assemblyai' richiesto ma ASSEMBLYAI_API_KEY non è impostata.")
            from sbobina.trascrizione.assemblyai import MotoreAssemblyAI

            motori.append(MotoreAssemblyAI(config.assemblyai_chiave))
        elif nome == "elevenlabs":
            if not config.elevenlabs_chiave:
                raise ErroreTrascrizione("Motore 'elevenlabs' richiesto ma ELEVENLABS_API_KEY non è impostata.")
            from sbobina.trascrizione.elevenlabs import MotoreElevenLabs

            motori.append(MotoreElevenLabs(config.elevenlabs_chiave))
        elif nome == "whisper":
            from sbobina.trascrizione.whisper_locale import MotoreWhisper

            motori.append(MotoreWhisper(config.whisper_modello, config.whisper_dispositivo))
    return motori


__all__ = ["ErroreTrascrizione", "MotoreTrascrizione", "Parola", "Trascrizione", "crea_motori"]
