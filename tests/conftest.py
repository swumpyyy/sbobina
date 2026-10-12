from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from sbobina import prompt
from sbobina.archivio import Archivio
from sbobina.config import Config
from sbobina.llm import Utilizzo
from sbobina.trascrizione.base import ErroreTrascrizione, Parola, Trascrizione

APPUNTI_FINTI = """\
# Il teorema di Rolle

> **In sintesi:** enunciato e dimostrazione del teorema di Rolle.

## Mappa concettuale
```mappa
- Teorema di Rolle
  - Ipotesi
  - Tesi
```

## Appunti
### Enunciato ⏱ 00:02
> **Teorema (Rolle):** se $f$ è continua in $[a,b]$, derivabile in $(a,b)$ e $f(a)=f(b)$, allora esiste $c$ con $f'(c)=0$.

```mermaid
flowchart TD
  A["Ipotesi"] --> B["Tesi"]
```

## Indicazioni del docente
⭐ Il teorema sarà chiesto all'esame.

## Glossario
| Termine | Significato |
|---|---|
| Derivata | Tasso di variazione |

## Domande di ripasso
**1.** Cosa afferma il teorema di Rolle?
<details><summary>Risposta</summary>Esiste un punto a derivata nulla.</details>

## Punti da verificare
Nessuno."""


def parole_finte(n: int = 40, passo: float = 0.5, prefisso: str = "parola") -> list[Parola]:
    return [
        Parola(i * passo, i * passo + 0.4, f"{prefisso}{i}" + ("." if i % 10 == 9 else ""), 0.9)
        for i in range(n)
    ]


class FintoMotore:
    def __init__(self, nome: str = "finto", parole: list[Parola] | None = None, errore: str | None = None):
        self.nome = nome
        self.parole = parole if parole is not None else parole_finte()
        self.errore = errore
        self.chiamate: list[dict] = []

    def trascrivi(self, audio: Path, *, lingua, termini, contesto, avanzamento) -> Trascrizione:
        self.chiamate.append({"audio": audio, "lingua": lingua, "termini": list(termini), "contesto": contesto})
        assert audio.is_file(), "il motore deve ricevere il FLAC preparato"
        avanzamento(0.5)
        if self.errore:
            raise ErroreTrascrizione(self.errore)
        avanzamento(1.0)
        return Trascrizione(self.nome, list(self.parole), 20.0)


class FintoLLM:
    """Sostituto di Claude: risponde in modo deterministico in base alla fase."""

    def __init__(self, problemi: list[dict] | None = None, revisione_corta: bool = False):
        self.chiamate: list[dict] = []
        self.problemi = problemi if problemi is not None else [
            {
                "tipo": "errato",
                "gravita": "alta",
                "posizione": "Enunciato",
                "evidenza": "[00:02] il docente dice continua in [a,b]",
                "correzione": "Specificare l'intervallo chiuso",
            }
        ]
        self.revisione_corta = revisione_corta

    @staticmethod
    def _ultimo_testo(contenuto: list[dict]) -> str:
        return [b["text"] for b in contenuto if b.get("type") == "text"][-1]

    def testo(self, *, system, contenuto, sforzo, max_tokens=64000):
        testo = self._ultimo_testo(contenuto)
        if isinstance(system, list):
            fase = "revisione"
            blocco = re.search(r"<trascrizione_principale>\n(.*?)\n</trascrizione_principale>", testo, re.S).group(1)
            if self.revisione_corta and "Attenzione" not in testo:
                risposta = blocco.splitlines()[0].split()[0] + " Riassunto."
            else:
                risposta = "\n\n".join(riga.replace("parola", "Parola") for riga in blocco.splitlines())
        elif testo.startswith("Scrivi gli appunti"):
            fase, risposta = "appunti", APPUNTI_FINTI
        elif testo.startswith("Scrivi l'approfondimento"):
            fase, risposta = "approfondimento", "# Approfondimento: Rolle\n\n## Il quadro generale\n\nPerché conta."
        elif testo.startswith("Lo studente vuole andare più a fondo su:"):
            argomento = testo.split(":", 1)[1].split("\n", 1)[0].strip()
            fase, risposta = "espansione", f"## Approfondimento: {argomento}\n\n### Dettaglio\n\nSpiegazione."
        elif "problemi trovati dal revisore" in testo:
            fase, risposta = "correzione", APPUNTI_FINTI.replace("continua in", "continua nell'intervallo chiuso")
        else:
            raise AssertionError(f"chiamata testo inattesa: {testo[:80]}")
        self.chiamate.append({"fase": fase, "system": system, "contenuto": contenuto, "sforzo": sforzo})
        return risposta, Utilizzo(input=100, output=50, cache_lettura=10)

    def json(self, *, system, contenuto, schema, sforzo, max_tokens=32000):
        if schema is prompt.SCHEMA_TERMINI:
            fase, risposta = "termini", {"termini": ["Rolle", "Lagrange"]}
        elif schema is prompt.SCHEMA_VERIFICA:
            fase = "verifica"
            risposta = {"giudizio": "Appunti accurati.", "problemi": self.problemi, "termini_chiave": ["teorema di Rolle"]}
        else:
            raise AssertionError("schema inatteso")
        self.chiamate.append({"fase": fase, "system": system, "contenuto": contenuto, "sforzo": sforzo})
        return risposta, Utilizzo(input=100, output=20)

    def fasi(self) -> list[str]:
        return [c["fase"] for c in self.chiamate]


@pytest.fixture
def audio_prova(tmp_path: Path) -> Path:
    """20 secondi di audio in formato m4a (come le note vocali del telefono)."""
    percorso = tmp_path / "Lezione 3 - Rolle.m4a"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=20", "-c:a", "aac", str(percorso)],
        check=True,
        capture_output=True,
    )
    return percorso


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(cartella_dati=tmp_path / "dati", motori=("finto",), minuti_per_blocco=0.1, richieste_parallele=2)


@pytest.fixture
def archivio(config: Config) -> Archivio:
    return Archivio(config.cartella_dati)
