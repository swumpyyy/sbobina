"""Le scelte dello studente, salvate in <cartella dati>/impostazioni.json e lette a ogni lezione."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from sbobina.config import Config
from sbobina.llm import repo_mlx
from sbobina.sistema import contesto_massimo, info_mac

MOTORI_LLM = ("mlx", "claude")
LUNGHEZZE = ("essenziale", "normale", "dettagliata")
STILI = ("discorsivo", "schematico")
TEMI = ("sistema", "chiaro", "scuro")
LINGUE = ("it", "en")  # dell'app, delle lezioni (Whisper) e degli appunti
# Temi colore (stile Lectio): l'accento e il rosa del desktop mentre si registra. "personalizzato" usa `colore`.
ACCENTI = ("rosa", "menta", "arancio", "cobalto", "limone", "seppia", "personalizzato")
_ACCENTI_VECCHI = {"blu": "cobalto", "indaco": "cobalto", "azzurro": "cobalto", "verde": "menta"}
PDF = ("appunti", "approfondimento", "trascrizione")
SEZIONI = ("mappa", "schemi", "domande", "glossario", "indicazioni", "approfondimento", "verifica")

# Area di studio → come scrivere gli appunti. Il testo finisce nel prompt.
AREE = {
    "economia": "Corso di area economico-aziendale: cura i numeri, le formule di calcolo, i prospetti contabili e gli esempi d'impresa.",
    "giurisprudenza": "Corso di area giuridica: riporta con precisione articoli, commi, fonti normative, sentenze e definizioni legali.",
    "ingegneria": "Corso di area tecnico-scientifica: formule in LaTeX con tutti i passaggi, unità di misura, dimostrazioni ed esercizi completi.",
    "medicina": "Corso di area medico-sanitaria: terminologia clinica esatta, classificazioni, meccanismi fisiopatologici e valori di riferimento.",
    "umanistica": "Corso di area umanistica: autori, opere, date, correnti e citazioni testuali, con i collegamenti tra i concetti.",
    "scienze": "Corso di area scientifica: definizioni rigorose, leggi, esperimenti, dati e formule con i passaggi.",
    "altro": "",
}
ANNI = ("1", "2", "3", "4", "5", "6", "fuori corso", "magistrale")


@dataclass
class Impostazioni:
    # Profilo (dal primo avvio)
    configurato: bool = False
    lingua: str = "it"
    nome: str = ""
    universita: str = ""
    corso_di_laurea: str = ""
    area: str = "economia"
    anno: str = ""
    # AI
    motore_llm: str = "mlx"
    modello: str = ""  # vuoto: quello della configurazione
    chiave_claude: str = ""
    whisper: str = ""  # vuoto: quello della configurazione
    temperatura: float = 0.3
    contesto: int = 0  # 0: automatico in base alla RAM
    prompt_extra: str = ""
    # Appunti
    lunghezza: str = "normale"
    stile: str = "discorsivo"
    sezioni: dict[str, bool] = field(default_factory=lambda: {s: True for s in SEZIONI})
    # PDF
    pdf: str = "appunti"
    # Aspetto
    tema: str = "sistema"
    accento: str = "rosa"
    colore: str = "#d45bb6"  # accento del tema personalizzato
    griglia: bool = True  # sfondo a puntini
    vetro: bool = True  # trasparenze sugli elementi che galleggiano
    animazioni_ridotte: bool = False
    scala_testo: int = 100
    # Fine lezione
    notifiche: bool = True
    suono: bool = True
    # Sezione nerd: i numeri del modello (token, velocità, memoria) nelle risposte e mentre elabora
    nerd: bool = False

    def sezione(self, nome: str) -> bool:
        return self.sezioni.get(nome, True)

    def a_dict(self, *, nascondi_chiave: bool = True) -> dict:
        dati = asdict(self)
        if nascondi_chiave:
            dati["chiave_claude"] = "••••" + self.chiave_claude[-4:] if self.chiave_claude else ""
        return dati

    @classmethod
    def da_dict(cls, dati: dict, base: Impostazioni | None = None) -> Impostazioni:
        """Applica i campi noti a `base`, validandoli; ignora quelli sconosciuti."""
        base = base or cls()
        imp = replace(base, sezioni=dict(base.sezioni))
        noti = {f.name for f in fields(cls)}
        for chiave, valore in dati.items():
            if chiave not in noti:
                continue
            if chiave == "chiave_claude" and isinstance(valore, str) and valore.startswith("••••"):
                continue  # il client rimanda la chiave mascherata: non cambia
            if chiave == "accento" and valore in _ACCENTI_VECCHI:
                valore = _ACCENTI_VECCHI[valore]  # colori del tema a vetro blu, prima di Lectio
            if chiave == "motore_llm" and valore == "ollama":
                valore = "mlx"  # Ollama non c'è più: stessi modelli Gemma, ora dentro Sbobina
            if chiave == "sezioni":
                if isinstance(valore, dict):
                    imp.sezioni.update({k: bool(v) for k, v in valore.items() if k in SEZIONI})
                continue
            attuale = getattr(imp, chiave)
            try:
                if isinstance(attuale, bool):
                    valore = bool(valore)
                elif isinstance(attuale, int):
                    valore = int(valore)
                elif isinstance(attuale, float):
                    valore = float(valore)
                else:
                    valore = str(valore).strip()
            except (TypeError, ValueError) as e:
                raise ValueError(f"Valore non valido per {chiave}: {valore!r}") from e
            setattr(imp, chiave, valore)
        imp._valida()
        return imp

    def _valida(self) -> None:
        for nome, ammessi in (
            ("motore_llm", MOTORI_LLM), ("lunghezza", LUNGHEZZE), ("stile", STILI),
            ("tema", TEMI), ("accento", ACCENTI), ("pdf", PDF), ("area", tuple(AREE)), ("lingua", LINGUE),
        ):
            if getattr(self, nome) not in ammessi:
                raise ValueError(f"Valore non valido per {nome}: {getattr(self, nome)!r} (ammessi: {', '.join(ammessi)})")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.colore):
            raise ValueError("Il colore va scritto come #RRGGBB.")
        if not 0.0 <= self.temperatura <= 1.5:
            raise ValueError("La temperatura va da 0 a 1,5.")
        if self.contesto and not 8192 <= self.contesto <= 262144:
            raise ValueError("Il contesto va da 8.192 a 262.144 token (0 = automatico).")
        if not 80 <= self.scala_testo <= 140:
            raise ValueError("La dimensione del testo va dall'80% al 140%.")
        if len(self.prompt_extra) > 2000:
            raise ValueError("Le istruzioni aggiuntive possono essere lunghe al massimo 2000 caratteri.")

    # --- effetti sulla configurazione ------------------------------------

    def applica(self, config: Config) -> Config:
        """La configurazione effettiva: le scelte dello studente sopra quelle di .env."""
        modello = self.modello or config.modello
        if self.motore_llm == "claude" and not modello.startswith("claude"):
            modello = "claude-opus-5-5"
        elif self.motore_llm != "claude" and modello.startswith("claude"):
            modello = Config.modello
        if self.motore_llm == "mlx":
            modello = repo_mlx(modello)
        if self.chiave_claude:
            os.environ["ANTHROPIC_API_KEY"] = self.chiave_claude
        return replace(
            config,
            modello=modello,
            lingua=self.lingua,
            whisper_modello=self.whisper or config.whisper_modello,
            verifica=config.verifica and self.sezione("verifica"),
        )


    def contesto_effettivo(self) -> int:
        return self.contesto or contesto_massimo(info_mac()["memoria_ai_gb"])


def percorso(cartella_dati: Path) -> Path:
    return cartella_dati / "impostazioni.json"


def carica(cartella_dati: Path) -> Impostazioni:
    file = percorso(cartella_dati)
    if not file.is_file():
        return Impostazioni()
    try:
        return Impostazioni.da_dict(json.loads(file.read_text(encoding="utf-8")))
    except (ValueError, json.JSONDecodeError):
        return Impostazioni()  # file rovinato: meglio i valori predefiniti che non partire


def salva(cartella_dati: Path, imp: Impostazioni) -> None:
    file = percorso(cartella_dati)
    file.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = file.with_suffix(".tmp")
    temporaneo.write_text(json.dumps(imp.a_dict(nascondi_chiave=False), ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temporaneo, 0o600)  # contiene la chiave di Claude, se c'è
    temporaneo.replace(file)
