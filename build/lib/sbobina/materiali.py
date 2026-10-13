"""Materiali del corso (slide, dispense, foto della lavagna) da affiancare all'audio."""

from __future__ import annotations

import base64
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# Limiti dell'API: richieste fino a 32 MB (il base64 pesa 4/3) e 600 pagine PDF.
MAX_BYTE_PDF = 20 * 1024 * 1024
MAX_PAGINE_PDF = 500
LATO_MAX_IMMAGINE = 1600

_TIPI_IMMAGINE = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@dataclass
class Materiali:
    blocchi: list[dict] = field(default_factory=list)  # blocchi di contenuto per Claude
    testo: str = ""  # testo estratto, usato nella revisione della trascrizione
    avvisi: list[str] = field(default_factory=list)

    @property
    def presenti(self) -> bool:
        return bool(self.blocchi)


def _testo_pdf(percorso: Path) -> tuple[str, int]:
    from pypdf import PdfReader

    lettore = PdfReader(str(percorso))
    pagine = []
    for i, pagina in enumerate(lettore.pages, 1):
        try:
            testo = (pagina.extract_text() or "").strip()
        except Exception:  # noqa: BLE001 - un PDF malformato non deve bloccare la lezione
            testo = ""
        if testo:
            pagine.append(f"[pagina {i}]\n{testo}")
    return "\n\n".join(pagine), len(lettore.pages)


def _immagine_ridotta(percorso: Path, cartella_lavoro: Path) -> Path:
    """Riduce le foto (spesso >5 MB dal telefono) a una dimensione adatta all'API."""
    destinazione = cartella_lavoro / f"{percorso.stem}-ridotta.jpg"
    if destinazione.is_file():
        return destinazione
    cartella_lavoro.mkdir(parents=True, exist_ok=True)
    filtro = f"scale='if(gt(iw,ih),min({LATO_MAX_IMMAGINE},iw),-2)':'if(gt(iw,ih),-2,min({LATO_MAX_IMMAGINE},ih))'"
    risultato = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-i", str(percorso), "-vf", filtro, "-q:v", "3", str(destinazione)],
        capture_output=True,
    )
    if risultato.returncode != 0:
        raise ValueError(f"immagine non leggibile: {percorso.name}")
    return destinazione


def carica_materiali(cartella: Path, nomi: list[str], cartella_lavoro: Path, limite_testo: int = 80_000) -> Materiali:
    materiali = Materiali()
    testi: list[str] = []
    byte_pdf = pagine_pdf = 0
    for nome in nomi:
        percorso = cartella / nome
        estensione = percorso.suffix.lower()
        try:
            if estensione == ".pdf":
                testo, pagine = _testo_pdf(percorso)
                if testo:
                    testi.append(f"<materiale nome=\"{nome}\">\n{testo}\n</materiale>")
                dimensione = percorso.stat().st_size
                if byte_pdf + dimensione <= MAX_BYTE_PDF and pagine_pdf + pagine <= MAX_PAGINE_PDF:
                    byte_pdf += dimensione
                    pagine_pdf += pagine
                    materiali.blocchi.append({
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.standard_b64encode(percorso.read_bytes()).decode(),
                        },
                        "title": nome,
                    })
                elif testo:
                    materiali.blocchi.append({"type": "text", "text": testi[-1]})
                    materiali.avvisi.append(f"{nome}: PDF troppo grande, usato solo il testo (senza immagini).")
                else:
                    materiali.avvisi.append(f"{nome}: PDF troppo grande e senza testo estraibile, ignorato.")
            elif estensione in _TIPI_IMMAGINE:
                ridotta = _immagine_ridotta(percorso, cartella_lavoro)
                materiali.blocchi.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.standard_b64encode(ridotta.read_bytes()).decode(),
                    },
                })
                materiali.blocchi.append({"type": "text", "text": f"(Immagine qui sopra: {nome})"})
            elif estensione in (".txt", ".md"):
                testo = percorso.read_text(encoding="utf-8", errors="replace").strip()
                if testo:
                    blocco = f"<materiale nome=\"{nome}\">\n{testo}\n</materiale>"
                    testi.append(blocco)
                    materiali.blocchi.append({"type": "text", "text": blocco})
        except Exception as e:  # noqa: BLE001
            log.warning("Materiale %s non utilizzabile: %s", nome, e)
            materiali.avvisi.append(f"{nome}: non utilizzabile ({e}).")

    testo = "\n\n".join(testi)
    if len(testo) > limite_testo:
        testo = testo[:limite_testo] + "\n[... materiali troncati ...]"
    materiali.testo = testo
    return materiali
