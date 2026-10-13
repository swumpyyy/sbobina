"""Configurazione letta da variabili d'ambiente (ed eventuale file .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MOTORI_NOTI = ("assemblyai", "elevenlabs", "whisper")
SFORZI = ("low", "medium", "high", "xhigh", "max")


def carica_dotenv(percorso: Path) -> None:
    """Carica righe KEY=VALUE da un file .env senza sovrascrivere variabili già impostate."""
    if not percorso.is_file():
        return
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, valore = riga.split("=", 1)
        chiave = chiave.strip().removeprefix("export ").strip()
        valore = valore.strip().strip('"').strip("'")
        if chiave:
            os.environ.setdefault(chiave, valore)


def scegli_motori(richiesta: str, env: dict[str, str] | os._Environ) -> tuple[str, ...]:
    """Decide quali motori di trascrizione usare.

    "auto" usa tutti i servizi cloud con una chiave configurata (con due motori
    le trascrizioni vengono confrontate e riconciliate); senza chiavi ripiega su
    Whisper in locale.
    """
    richiesta = (richiesta or "auto").strip().lower()
    if richiesta == "auto":
        motori = [
            nome
            for nome, chiave in (("assemblyai", "ASSEMBLYAI_API_KEY"), ("elevenlabs", "ELEVENLABS_API_KEY"))
            if env.get(chiave)
        ]
        return tuple(motori) or ("whisper",)
    motori = tuple(dict.fromkeys(m.strip() for m in richiesta.split(",") if m.strip()))
    sconosciuti = [m for m in motori if m not in MOTORI_NOTI]
    if sconosciuti or not motori:
        raise ValueError(
            f"SBOBINA_MOTORI non valido: {richiesta!r}. Valori ammessi: auto oppure {', '.join(MOTORI_NOTI)}"
        )
    return motori


def _sforzo(valore: str | None, predefinito: str) -> str:
    valore = (valore or predefinito).strip().lower()
    if valore not in SFORZI:
        raise ValueError(f"Livello di sforzo non valido: {valore!r}. Valori ammessi: {', '.join(SFORZI)}")
    return valore


@dataclass(frozen=True)
class Config:
    cartella_dati: Path = Path("dati")
    # Modello locale gratuito via Ollama; un nome "claude-..." usa invece l'API Anthropic (a pagamento).
    modello: str = "gemma4:12b"
    # Sforzo per appunti, verifica e correzione finale (le tre fasi condividono la cache del prompt).
    sforzo_appunti: str = "high"
    # Sforzo per la revisione della trascrizione, blocco per blocco.
    sforzo_revisione: str = "medium"
    motori: tuple[str, ...] = ("whisper",)
    lingua: str = "it"
    whisper_modello: str = "large-v3-turbo"
    whisper_dispositivo: str = "auto"
    minuti_per_blocco: float = 8.0
    richieste_parallele: int = 4
    verifica: bool = True
    assemblyai_chiave: str = ""
    elevenlabs_chiave: str = ""

    @classmethod
    def da_ambiente(cls, file_env: Path = Path(".env")) -> Config:
        carica_dotenv(file_env)
        env = os.environ
        modello = env.get("SBOBINA_MODELLO", cls.modello)
        # In locale le richieste parallele si contendono la memoria del Mac: una alla volta.
        parallele_predefinite = "4" if modello.startswith("claude") else "1"
        return cls(
            cartella_dati=Path(env.get("SBOBINA_DATI", "dati")),
            modello=modello,
            sforzo_appunti=_sforzo(env.get("SBOBINA_SFORZO"), "high"),
            sforzo_revisione=_sforzo(env.get("SBOBINA_SFORZO_REVISIONE"), "medium"),
            motori=scegli_motori(env.get("SBOBINA_MOTORI", "auto"), env),
            lingua=env.get("SBOBINA_LINGUA", "it"),
            whisper_modello=env.get("SBOBINA_WHISPER_MODELLO", "large-v3-turbo"),
            whisper_dispositivo=env.get("SBOBINA_WHISPER_DISPOSITIVO", "auto"),
            minuti_per_blocco=float(env.get("SBOBINA_MINUTI_PER_BLOCCO", "8")),
            richieste_parallele=max(1, int(env.get("SBOBINA_RICHIESTE_PARALLELE", parallele_predefinite))),
            verifica=env.get("SBOBINA_VERIFICA", "1").strip().lower() not in ("0", "no", "false"),
            assemblyai_chiave=env.get("ASSEMBLYAI_API_KEY", ""),
            elevenlabs_chiave=env.get("ELEVENLABS_API_KEY", ""),
        )

    @property
    def locale(self) -> bool:
        return not self.modello.startswith("claude")

    @property
    def llm_pronto(self) -> bool:
        """Il modello che scrive gli appunti è utilizzabile: Ollama o MLX con il modello scaricato, o chiave Claude."""
        from sbobina.llm import pronto

        return pronto(self.modello)
