"""Strutture comuni ai motori di trascrizione e funzioni per suddividere il testo."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

Avanzamento = Callable[[float], None]


class ErroreTrascrizione(RuntimeError):
    pass


@dataclass
class Parola:
    inizio: float
    fine: float
    testo: str
    confidenza: float | None = None


@dataclass
class Trascrizione:
    motore: str
    parole: list[Parola]
    durata: float | None = None

    @property
    def testo(self) -> str:
        return " ".join(p.testo for p in self.parole)

    def a_dict(self) -> dict:
        return {
            "motore": self.motore,
            "durata": self.durata,
            "parole": [
                [round(p.inizio, 2), round(p.fine, 2), p.testo,
                 None if p.confidenza is None else round(p.confidenza, 3)]
                for p in self.parole
            ],
        }

    @classmethod
    def da_dict(cls, dati: dict) -> Trascrizione:
        return cls(
            motore=dati["motore"],
            durata=dati.get("durata"),
            parole=[Parola(inizio, fine, testo, conf) for inizio, fine, testo, conf in dati["parole"]],
        )


class MotoreTrascrizione(Protocol):
    nome: str

    def trascrivi(
        self, audio: Path, *, lingua: str, termini: list[str], contesto: str, avanzamento: Avanzamento
    ) -> Trascrizione: ...


def tempo(secondi: float) -> str:
    """12:34 oppure 1:02:03."""
    s = max(0, int(secondi))
    ore, minuti, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{ore}:{minuti:02d}:{sec:02d}" if ore else f"{minuti:02d}:{sec:02d}"


_FINE_FRASE = re.compile(r"[.!?…][\"'»”)\]]*$")


@dataclass
class Riga:
    inizio: float
    testo: str


def in_righe(parole: list[Parola], *, max_parole: int = 45, min_parole: int = 8, pausa: float = 1.5) -> list[Riga]:
    """Raggruppa le parole in righe brevi (circa una frase) con il loro tempo d'inizio."""
    righe: list[Riga] = []
    correnti: list[str] = []
    inizio = 0.0
    precedente: Parola | None = None
    for parola in parole:
        if correnti and precedente is not None:
            chiudi = (
                len(correnti) >= max_parole
                or parola.inizio - precedente.fine >= pausa
                or (len(correnti) >= min_parole and _FINE_FRASE.search(precedente.testo))
            )
            if chiudi:
                righe.append(Riga(inizio, " ".join(correnti)))
                correnti = []
        if not correnti:
            inizio = parola.inizio
        correnti.append(parola.testo)
        precedente = parola
    if correnti:
        righe.append(Riga(inizio, " ".join(correnti)))
    return righe


@dataclass
class Blocco:
    indice: int
    inizio: float
    fine: float | None  # None = fino alla fine dell'audio
    righe: list[Riga]

    @property
    def testo(self) -> str:
        return "\n".join(f"[{tempo(r.inizio)}] {r.testo}" for r in self.righe)

    @property
    def numero_parole(self) -> int:
        return sum(len(r.testo.split()) for r in self.righe)


def in_blocchi(righe: list[Riga], secondi: float = 480.0) -> list[Blocco]:
    """Divide le righe in blocchi di circa `secondi` secondi, tagliando solo tra una riga e l'altra."""
    gruppi: list[list[Riga]] = []
    for riga in righe:
        if gruppi and riga.inizio - gruppi[-1][0].inizio < secondi:
            gruppi[-1].append(riga)
        else:
            gruppi.append([riga])
    # Un ultimo blocco troppo corto viene unito al precedente.
    if len(gruppi) > 1:
        ultimo = gruppi[-1]
        if ultimo[-1].inizio - ultimo[0].inizio < secondi / 4:
            gruppi[-2].extend(gruppi.pop())
    blocchi = []
    for i, gruppo in enumerate(gruppi):
        fine = gruppi[i + 1][0].inizio if i + 1 < len(gruppi) else None
        blocchi.append(Blocco(indice=i, inizio=gruppo[0].inizio, fine=fine, righe=gruppo))
    return blocchi


def estrai_testo(parole: list[Parola], inizio: float, fine: float | None) -> str:
    """Testo delle parole che iniziano nell'intervallo [inizio, fine)."""
    return " ".join(p.testo for p in parole if p.inizio >= inizio and (fine is None or p.inizio < fine))


def filtra_termini(
    termini: list[str],
    *,
    massimo: int,
    max_parole: int,
    max_caratteri: int,
    caratteri_vietati: str = "",
) -> list[str]:
    """Adatta l'elenco di termini ai limiti del servizio di trascrizione."""
    risultato: list[str] = []
    visti: set[str] = set()
    for termine in termini:
        termine = " ".join(termine.split())
        for c in caratteri_vietati:
            termine = termine.replace(c, " ")
        termine = " ".join(termine.split())
        if (
            not termine
            or len(termine) > max_caratteri
            or len(termine.split()) > max_parole
            or termine.casefold() in visti
        ):
            continue
        visti.add(termine.casefold())
        risultato.append(termine)
        if len(risultato) >= massimo:
            break
    return risultato
