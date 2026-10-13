"""Archivio su disco di lezioni e corsi (file JSON + cartelle, nessun database)."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

ESTENSIONI_AUDIO = {
    ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".oga", ".opus", ".flac", ".webm",
    ".mp4", ".mov", ".mkv", ".wma", ".amr", ".3gp", ".caf", ".aiff", ".aif",
}
ESTENSIONI_MATERIALI = {".pdf", ".txt", ".md", ".jpg", ".jpeg", ".png", ".webp"}

STATI = ("in_coda", "in_elaborazione", "completata", "errore")

_scrittura = threading.Lock()


def slug(testo: str, lunghezza: int = 40) -> str:
    testo = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode()
    testo = re.sub(r"[^a-zA-Z0-9]+", "-", testo).strip("-").lower()
    return testo[:lunghezza].strip("-") or "lezione"


def adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scrivi_atomico(percorso: Path, contenuto: str) -> None:
    """Scrive un file in modo atomico: chi legge non vede mai un file a metà."""
    percorso.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=percorso.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(contenuto)
        os.replace(tmp, percorso)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def scrivi_json(percorso: Path, dati) -> None:
    scrivi_atomico(percorso, json.dumps(dati, ensure_ascii=False, indent=2))


def leggi_json(percorso: Path):
    return json.loads(percorso.read_text(encoding="utf-8"))


@dataclass
class Lezione:
    id: str
    titolo: str
    corso: str
    data: str
    file_audio: str
    materiali: list[str] = field(default_factory=list)
    note: str = ""
    stato: str = "in_coda"
    fase: str = ""
    progresso: float = 0.0
    messaggio: str = ""
    errore: str = ""
    avvisi: list[str] = field(default_factory=list)
    durata_secondi: float | None = None
    motori: list[str] = field(default_factory=list)
    utilizzo: dict[str, dict[str, int]] = field(default_factory=dict)
    da_approfondire: list[str] = field(default_factory=list)
    creata: str = field(default_factory=adesso)
    aggiornata: str = field(default_factory=adesso)

    @classmethod
    def da_dict(cls, dati: dict) -> Lezione:
        noti = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in dati.items() if k in noti})


@dataclass
class Corso:
    nome: str
    glossario: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slug(self.nome, 60)


def unisci_termini(*elenchi: list[str], massimo: int = 600) -> list[str]:
    """Unisce elenchi di termini eliminando i duplicati (senza distinguere maiuscole)."""
    visti: dict[str, str] = {}
    for elenco in elenchi:
        for termine in elenco:
            termine = " ".join(str(termine).split()).strip(" ,;.")
            if termine and termine.casefold() not in visti:
                visti[termine.casefold()] = termine
    return list(visti.values())[:massimo]


def dividi_termini(testo: str) -> list[str]:
    """Trasforma un testo libero (una voce per riga, o separate da virgole/punti e virgola) in termini."""
    return [t.strip() for t in re.split(r"[\n,;]+", testo or "") if t.strip()]


class Archivio:
    def __init__(self, radice: Path):
        self.radice = Path(radice)
        self.cartella_lezioni = self.radice / "lezioni"
        self.cartella_corsi = self.radice / "corsi"
        self.cartella_lezioni.mkdir(parents=True, exist_ok=True)
        self.cartella_corsi.mkdir(parents=True, exist_ok=True)

    # --- lezioni ---------------------------------------------------------

    def cartella(self, id_lezione: str) -> Path:
        if not re.fullmatch(r"[a-z0-9-]+", id_lezione):
            raise KeyError(id_lezione)
        return self.cartella_lezioni / id_lezione

    def crea_lezione(
        self,
        *,
        audio: Path,
        nome_audio: str,
        corso: str,
        titolo: str = "",
        data_lezione: str = "",
        note: str = "",
        materiali: list[tuple[str, Path]] | None = None,
        sposta: bool = False,
    ) -> Lezione:
        """Crea una lezione copiando (o spostando) l'audio e i materiali nella sua cartella."""
        estensione = Path(nome_audio).suffix.lower()
        if estensione not in ESTENSIONI_AUDIO:
            raise ValueError(f"Formato audio non supportato: {nome_audio}")
        titolo = titolo.strip() or Path(nome_audio).stem.replace("_", " ").strip()
        corso = corso.strip() or "Senza corso"
        id_lezione = f"{slug(titolo)}-{secrets.token_hex(3)}"
        cartella = self.cartella(id_lezione)
        (cartella / "materiali").mkdir(parents=True)

        destinazione = cartella / f"originale{estensione}"
        (shutil.move if sposta else shutil.copyfile)(audio, destinazione)

        nomi_materiali = []
        for nome, percorso in materiali or []:
            nome_sicuro = self._nome_materiale(nome, nomi_materiali)
            (shutil.move if sposta else shutil.copyfile)(percorso, cartella / "materiali" / nome_sicuro)
            nomi_materiali.append(nome_sicuro)

        lezione = Lezione(
            id=id_lezione,
            titolo=titolo,
            corso=corso,
            data=data_lezione or date.today().isoformat(),
            file_audio=destinazione.name,
            materiali=nomi_materiali,
            note=note.strip(),
        )
        self.salva(lezione)
        if not self.carica_corso(corso):
            self.salva_corso(Corso(nome=corso))
        return lezione

    @staticmethod
    def _nome_materiale(nome: str, esistenti: list[str]) -> str:
        percorso = Path(nome)
        estensione = percorso.suffix.lower()
        if estensione not in ESTENSIONI_MATERIALI:
            raise ValueError(f"Formato materiale non supportato: {nome} (ammessi: PDF, TXT, MD, JPG, PNG, WEBP)")
        base = slug(percorso.stem, 60) or "materiale"
        candidato, n = f"{base}{estensione}", 2
        while candidato in esistenti:
            candidato, n = f"{base}-{n}{estensione}", n + 1
        return candidato

    def salva(self, lezione: Lezione) -> None:
        with _scrittura:
            lezione.aggiornata = adesso()
            scrivi_json(self.cartella(lezione.id) / "lezione.json", asdict(lezione))

    def carica(self, id_lezione: str) -> Lezione:
        percorso = self.cartella(id_lezione) / "lezione.json"
        if not percorso.is_file():
            raise KeyError(id_lezione)
        return Lezione.da_dict(leggi_json(percorso))

    def aggiorna(self, id_lezione: str, **campi) -> Lezione:
        def imposta(lezione: Lezione) -> None:
            for chiave, valore in campi.items():
                setattr(lezione, chiave, valore)

        return self.modifica(id_lezione, imposta)

    def modifica(self, id_lezione: str, funzione: Callable[[Lezione], None]) -> Lezione:
        """Legge, modifica e riscrive la lezione in un'unica operazione (sicura tra thread)."""
        with _scrittura:
            lezione = self.carica(id_lezione)
            funzione(lezione)
            lezione.aggiornata = adesso()
            scrivi_json(self.cartella(id_lezione) / "lezione.json", asdict(lezione))
            return lezione

    def elenco(self) -> list[Lezione]:
        lezioni = []
        for percorso in self.cartella_lezioni.glob("*/lezione.json"):
            try:
                lezioni.append(Lezione.da_dict(leggi_json(percorso)))
            except (OSError, ValueError):
                continue
        return sorted(lezioni, key=lambda lez: (lez.data, lez.creata), reverse=True)

    def elimina(self, id_lezione: str) -> None:
        cartella = self.cartella(id_lezione)
        if not cartella.is_dir():
            raise KeyError(id_lezione)
        shutil.rmtree(cartella)

    # --- corsi -----------------------------------------------------------

    def carica_corso(self, nome: str) -> Corso | None:
        percorso = self.cartella_corsi / f"{slug(nome, 60)}.json"
        if not percorso.is_file():
            return None
        dati = leggi_json(percorso)
        return Corso(nome=dati.get("nome", nome), glossario=list(dati.get("glossario", [])))

    def salva_corso(self, corso: Corso) -> None:
        with _scrittura:
            scrivi_json(self.cartella_corsi / f"{corso.slug}.json", asdict(corso))

    def aggiungi_al_glossario(self, nome_corso: str, termini: list[str]) -> Corso:
        corso = self.carica_corso(nome_corso) or Corso(nome=nome_corso)
        corso.glossario = unisci_termini(corso.glossario, termini)
        self.salva_corso(corso)
        return corso

    def corsi(self) -> list[Corso]:
        risultato = []
        for percorso in sorted(self.cartella_corsi.glob("*.json")):
            dati = leggi_json(percorso)
            risultato.append(Corso(nome=dati["nome"], glossario=list(dati.get("glossario", []))))
        return risultato
