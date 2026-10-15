"""Strumenti per studiare: ricerca, quiz, flashcard con ripasso Leitner, domande alla lezione, esportazioni."""

from __future__ import annotations

import io
import re
import threading
import unicodedata
import zipfile
from datetime import date, timedelta
from pathlib import Path

from sbobina.archivio import Archivio, Lezione, leggi_json, scrivi_json, slug
from sbobina.llm import ModelloLinguistico

# Una sola generazione interattiva alla volta: con un modello locale due insieme esauriscono la memoria.
OCCUPATO = threading.Lock()

RE_TEMPO = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]|⏱️?\s?(\d{1,2}:\d{2}(?::\d{2})?)")


def _piano(testo: str) -> str:
    """Minuscolo e senza accenti: "perché" e "perche" si trovano a vicenda."""
    return "".join(c for c in unicodedata.normalize("NFD", testo.lower()) if unicodedata.category(c) != "Mn")


def _file(archivio: Archivio, lezione: Lezione, nome: str) -> Path:
    return archivio.cartella(lezione.id) / nome


# --------------------------------------------------------------------------
# Ricerca in tutte le lezioni
# --------------------------------------------------------------------------

def cerca(archivio: Archivio, domanda: str, massimo: int = 60) -> list[dict]:
    """Cerca in appunti e trascrizioni. Ogni risultato ha un estratto e il tempo più vicino nell'audio."""
    parole = [p for p in _piano(domanda).split() if len(p) > 1]
    if not parole:
        return []
    risultati: list[dict] = []
    for lezione in archivio.elenco():
        for fonte, nome in (("appunti", "appunti.md"), ("trascrizione", "trascrizione.md")):
            percorso = _file(archivio, lezione, nome)
            if not percorso.is_file():
                continue
            tempo = ""
            for riga in percorso.read_text(encoding="utf-8").splitlines():
                trovato = RE_TEMPO.search(riga)
                if trovato:
                    tempo = trovato.group(1) or trovato.group(2)
                if not all(p in _piano(riga) for p in parole):
                    continue
                pulita = re.sub(r"[#>*_`]|\[\d{1,2}:\d{2}(?::\d{2})?\]|⏱️?\s?\d{1,2}:\d{2}", "", riga).strip()
                pos = max(0, _piano(pulita).find(parole[0]))
                inizio = max(0, pos - 70)
                estratto = ("…" if inizio else "") + pulita[inizio : inizio + 200] + ("…" if len(pulita) > inizio + 200 else "")
                risultati.append({
                    "lezione": lezione.id, "titolo": lezione.titolo, "corso": lezione.corso,
                    "fonte": fonte, "estratto": estratto, "tempo": tempo,
                })
                if len(risultati) >= massimo:
                    return risultati
    return risultati


# --------------------------------------------------------------------------
# Generazione con l'AI (quiz, flashcard, domande alla lezione)
# --------------------------------------------------------------------------

SYSTEM_STUDIO = (
    "Aiuti uno studente universitario italiano a studiare una lezione. Usi solo i contenuti degli "
    "appunti e della trascrizione forniti: non inventare nulla. Scrivi in italiano chiaro."
)

SCHEMA_QUIZ = {
    "type": "object",
    "properties": {
        "domande": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "domanda": {"type": "string"},
                    "opzioni": {"type": "array", "items": {"type": "string"}},
                    "corretta": {"type": "integer"},
                    "spiegazione": {"type": "string"},
                    "tempo": {"type": "string"},
                },
                "required": ["domanda", "opzioni", "corretta", "spiegazione", "tempo"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["domande"],
    "additionalProperties": False,
}

SCHEMA_CARTE = {
    "type": "object",
    "properties": {
        "carte": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"fronte": {"type": "string"}, "retro": {"type": "string"}, "tempo": {"type": "string"}},
                "required": ["fronte", "retro", "tempo"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["carte"],
    "additionalProperties": False,
}


def _testo(archivio: Archivio, lezione: Lezione, *, trascrizione: bool) -> str:
    parti = []
    appunti = _file(archivio, lezione, "appunti.md")
    if appunti.is_file():
        parti.append(f"<appunti>\n{appunti.read_text(encoding='utf-8')}\n</appunti>")
    t = _file(archivio, lezione, "trascrizione.md")
    if trascrizione and t.is_file():
        parti.append(f"<trascrizione>\n{t.read_text(encoding='utf-8')}\n</trascrizione>")
    if not parti:
        raise ValueError("Gli appunti di questa lezione non sono ancora pronti.")
    return f"Corso: {lezione.corso}\nLezione: {lezione.titolo}\n\n" + "\n\n".join(parti)


def _valida_domanda(d: dict) -> bool:
    try:
        return isinstance(d.get("opzioni"), list) and len(d["opzioni"]) >= 2 and 0 <= int(d["corretta"]) < len(d["opzioni"])
    except (KeyError, TypeError, ValueError):
        return False


def genera_quiz(archivio: Archivio, lezione: Lezione, llm: ModelloLinguistico, numero: int = 10) -> dict:
    istruzioni = (
        f"Prepara un quiz di verifica di {numero} domande a scelta multipla su questa lezione, dalle più "
        "semplici alle più impegnative, come all'esame. Ogni domanda ha esattamente 4 opzioni plausibili e "
        "una sola corretta (indice da 0 a 3 in `corretta`), con una spiegazione di 1-2 frasi e il tempo "
        "`mm:ss` della lezione in cui se ne parla (preso dai marcatori ⏱ o [mm:ss], altrimenti stringa vuota). "
        "Varia la posizione della risposta corretta."
    )
    dati, _ = llm.json(
        system=SYSTEM_STUDIO,
        contenuto=[{"type": "text", "text": _testo(archivio, lezione, trascrizione=False)}, {"type": "text", "text": istruzioni}],
        schema=SCHEMA_QUIZ, sforzo="medium", max_tokens=12000,
    )
    domande = [d for d in dati.get("domande", []) if _valida_domanda(d)]
    if not domande:
        raise ValueError("Il modello non ha prodotto domande valide: riprova.")
    quiz = {"domande": domande}
    scrivi_json(_file(archivio, lezione, "quiz.json"), quiz)
    return quiz


def genera_carte(archivio: Archivio, lezione: Lezione, llm: ModelloLinguistico) -> dict:
    istruzioni = (
        "Crea 15-30 flashcard per ripassare questa lezione: sul fronte una domanda breve o un termine, sul "
        "retro la risposta essenziale (massimo 3 righe). Copri definizioni, formule, distinzioni, articoli, "
        "date e ciò che il docente ha indicato come importante (⭐). Indica il tempo `mm:ss` della lezione in "
        "cui se ne parla, o stringa vuota."
    )
    dati, _ = llm.json(
        system=SYSTEM_STUDIO,
        contenuto=[{"type": "text", "text": _testo(archivio, lezione, trascrizione=False)}, {"type": "text", "text": istruzioni}],
        schema=SCHEMA_CARTE, sforzo="medium", max_tokens=12000,
    )
    carte = [c for c in dati.get("carte", []) if str(c.get("fronte", "")).strip() and str(c.get("retro", "")).strip()]
    if not carte:
        raise ValueError("Il modello non ha prodotto flashcard valide: riprova.")
    mazzo = {"carte": carte}
    scrivi_json(_file(archivio, lezione, "flashcard.json"), mazzo)
    return mazzo


def chiedi(archivio: Archivio, lezione: Lezione, llm: ModelloLinguistico, domanda: str) -> list[dict]:
    """Risponde a una domanda sulla lezione citando i minuti; salva la conversazione in chat.json."""
    file = _file(archivio, lezione, "chat.json")
    storia: list[dict] = leggi_json(file) if file.is_file() else []
    precedenti = "\n".join(f"{m['ruolo'].upper()}: {m['testo']}" for m in storia[-6:])
    istruzioni = (
        "Rispondi alla domanda dello studente usando solo questa lezione. Cita sempre il punto dell'audio "
        "tra parentesi quadre nel formato [mm:ss] preso dai marcatori della trascrizione, così lo studente "
        "può riascoltarlo. Se la lezione non ne parla, dillo chiaramente invece di inventare. Sii conciso "
        "(massimo 8 frasi) e usa elenchi se aiutano. Formule in LaTeX.\n\n"
        + (f"Conversazione finora:\n{precedenti}\n\n" if precedenti else "")
        + f"Domanda: {domanda}"
    )
    risposta, _ = llm.testo(
        system=SYSTEM_STUDIO,
        contenuto=[{"type": "text", "text": _testo(archivio, lezione, trascrizione=True)}, {"type": "text", "text": istruzioni}],
        sforzo="medium", max_tokens=4000,
    )
    storia += [{"ruolo": "studente", "testo": domanda}, {"ruolo": "sbobina", "testo": risposta.strip()}]
    scrivi_json(file, storia)
    return storia


# Parole che compaiono in ogni domanda e non aiutano a scegliere la lezione giusta.
VUOTE = set("della delle degli dello nella nelle negli sulla sulle quali quale quando quanto come cosa sono "
            "questo questa quello quella perche spiega spiegami dimmi lezione lezioni professore docente corso "
            "differenza esempio fammi parla parlato detto".split())


def chiedi_tutte(archivio: Archivio, llm: ModelloLinguistico, domanda: str, corso: str = "") -> list[dict]:
    """Risponde usando gli appunti di tutte le lezioni pronte (o di un corso); salva la conversazione in chat.json."""
    file = archivio.radice / "chat.json"
    storia: list[dict] = leggi_json(file) if file.is_file() else []
    # shortcut: le prime 6 lettere come radice ("associazioni" trova "associazione"), niente stemmer vero
    parole = {p[:6] for p in re.findall(r"\w{4,}", _piano(domanda)) if p not in VUOTE}
    candidate = []
    for lezione in archivio.elenco():
        appunti = _file(archivio, lezione, "appunti.md")
        if lezione.stato != "completata" or (corso and lezione.corso != corso) or not appunti.is_file():
            continue
        testo = appunti.read_text(encoding="utf-8")
        piano = _piano(testo)
        candidate.append((sum(piano.count(p) for p in parole), lezione, testo))
    if not candidate:
        raise ValueError(f"Non ci sono ancora appunti pronti{' per ' + corso if corso else ''}.")
    # prima le lezioni che parlano delle parole della domanda; se nessuna ne parla, tutte (es. "riassumi il corso")
    candidate = sorted([c for c in candidate if c[0]], key=lambda c: -c[0]) or candidate
    # shortcut: un budget fisso di caratteri invece dei token veri; oltre, un modello locale diventa lento
    resto = min(60_000, max(8192, getattr(llm, "contesto", 65536) - 8000) * 3)
    blocchi, fonti = [], []
    for _, lezione, testo in candidate:
        if resto < 2000:
            break
        pezzo = testo[:resto]
        blocchi.append(f'<lezione titolo="{lezione.titolo}" corso="{lezione.corso}" data="{lezione.data}">\n{pezzo}\n</lezione>')
        fonti.append({"id": lezione.id, "titolo": lezione.titolo, "corso": lezione.corso})
        resto -= len(pezzo)
    precedenti = "\n".join(f"{m['ruolo'].upper()}: {m['testo']}" for m in storia[-6:])
    istruzioni = (
        "Rispondi alla domanda dello studente usando solo gli appunti di queste lezioni. Per ogni "
        "informazione indica da quale lezione viene, col titolo in grassetto, e il minuto tra parentesi "
        "quadre nel formato [mm:ss] preso dai marcatori ⏱ degli appunti. Se le lezioni non ne parlano, dillo "
        "chiaramente invece di inventare. Sii conciso (massimo 10 frasi) e usa elenchi se aiutano. Formule in LaTeX.\n\n"
        + (f"Conversazione finora:\n{precedenti}\n\n" if precedenti else "")
        + f"Domanda: {domanda}"
    )
    risposta, _ = llm.testo(
        system=SYSTEM_STUDIO,
        contenuto=[{"type": "text", "text": "\n\n".join(blocchi)}, {"type": "text", "text": istruzioni}],
        sforzo="medium", max_tokens=4000,
    )
    storia += [{"ruolo": "studente", "testo": domanda, "corso": corso},
               {"ruolo": "sbobina", "testo": risposta.strip(), "fonti": fonti}]
    scrivi_json(file, storia)
    return storia


# --------------------------------------------------------------------------
# Ripasso con il sistema Leitner: 5 scatole, ogni risposta giusta allunga l'attesa
# --------------------------------------------------------------------------

INTERVALLI = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}  # giorni prima di rivedere una carta in quella scatola


class Ripasso:
    def __init__(self, archivio: Archivio):
        self.archivio = archivio
        self.file = archivio.radice / "ripasso.json"
        self._lock = threading.Lock()

    def _stato(self) -> dict:
        return leggi_json(self.file) if self.file.is_file() else {}

    def da_ripassare(self, *, lezione: str | None = None, oggi: date | None = None) -> list[dict]:
        """Le carte da rivedere oggi (le nuove compaiono subito), dalla scatola più bassa."""
        oggi = oggi or date.today()
        stato = self._stato()
        carte = []
        for lez in self.archivio.elenco():
            if lezione and lez.id != lezione:
                continue
            mazzo = _file(self.archivio, lez, "flashcard.json")
            if not mazzo.is_file():
                continue
            for i, carta in enumerate(leggi_json(mazzo).get("carte", [])):
                chiave = f"{lez.id}:{i}"
                info = stato.get(chiave, {"scatola": 1, "prossima": ""})
                if not info["prossima"] or info["prossima"] <= oggi.isoformat():
                    carte.append({**carta, "id": chiave, "scatola": info["scatola"], "lezione": lez.id,
                                  "titolo": lez.titolo, "corso": lez.corso})
        return sorted(carte, key=lambda c: c["scatola"])

    def esito(self, chiave: str, giusta: bool, oggi: date | None = None) -> dict:
        oggi = oggi or date.today()
        with self._lock:
            stato = self._stato()
            scatola = stato.get(chiave, {}).get("scatola", 1)
            scatola = min(5, scatola + 1) if giusta else 1
            stato[chiave] = {"scatola": scatola, "prossima": (oggi + timedelta(days=INTERVALLI[scatola])).isoformat()}
            scrivi_json(self.file, stato)
            return stato[chiave]


# --------------------------------------------------------------------------
# Esportazioni: Anki (testo importabile) e Obsidian (cartella Markdown con collegamenti)
# --------------------------------------------------------------------------

def esporta_anki(archivio: Archivio, lezione: Lezione) -> str:
    """Flashcard nel formato testo di Anki (File → Importa): mazzo e tag già impostati."""
    mazzo = _file(archivio, lezione, "flashcard.json")
    if not mazzo.is_file():
        raise ValueError("Crea prima le flashcard di questa lezione (scheda Ripasso).")
    pulisci = lambda s: " ".join(str(s).replace("\t", " ").split())  # noqa: E731
    tag = slug(lezione.corso, 40)
    righe = ["#separator:tab", "#html:false", f"#deck:Sbobina::{lezione.corso}", "#tags column:3"]
    for carta in leggi_json(mazzo).get("carte", []):
        righe.append(f"{pulisci(carta['fronte'])}\t{pulisci(carta['retro'])}\t{tag}")
    return "\n".join(righe) + "\n"


def esporta_obsidian(archivio: Archivio, corso: str) -> bytes:
    """Una nota per lezione con proprietà YAML e una nota indice del corso con i collegamenti [[...]]."""
    lezioni = sorted(
        (l for l in archivio.elenco() if l.corso == corso and _file(archivio, l, "appunti.md").is_file()),
        key=lambda l: (l.data or "", l.creata),
    )
    if not lezioni:
        raise ValueError("Questo corso non ha ancora lezioni pronte.")
    buffer = io.BytesIO()
    cartella = slug(corso, 60) or "corso"
    tag = slug(corso, 40)
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        nomi = []
        for l in lezioni:
            nome = re.sub(r'[\\/:*?"<>|#^\[\]]', "-", f"{l.data} {l.titolo}".strip())[:100]
            nomi.append(nome)
            testa = (
                "---\n"
                f'corso: "{corso}"\n'
                f"data: {l.data}\n"
                f"durata: {round((l.durata_secondi or 0) / 60)} min\n"
                f"tags: [sbobina, {tag}]\n"
                "---\n\n"
            )
            z.writestr(f"{cartella}/{nome}.md", testa + _file(archivio, l, "appunti.md").read_text(encoding="utf-8"))
            appr = _file(archivio, l, "approfondimento.md")
            if appr.is_file():
                z.writestr(f"{cartella}/{nome} - approfondimento.md", testa + appr.read_text(encoding="utf-8"))
        z.writestr(f"{cartella}/{corso}.md", f"# {corso}\n\n" + "\n".join(f"- [[{n}]]" for n in nomi) + "\n")
    return buffer.getvalue()
