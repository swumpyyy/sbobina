"""App web locale (FastAPI): carica le lezioni, segui l'elaborazione, studia gli appunti."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from fastapi import Depends, FastAPI, File as CampoFile, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

from sbobina.archivio import (
    ESTENSIONI_AUDIO,
    ESTENSIONI_MATERIALI,
    Archivio,
    Corso,
    Lezione,
    dividi_termini,
    leggi_json,
    scrivi_atomico,
    slug,
    unisci_termini,
)
from sbobina.audio import ffmpeg_disponibile
from sbobina.coda import ATTIVI, Coda
from sbobina.config import Config
from sbobina.esporta import LIBRERIE, crea_pdf, esporta_html, esporta_pdf_html
from sbobina import impostazioni, sistema, studio
from sbobina.registrazione import Registratore
from sbobina.llm import DIRETTA, FERMA, PREPARAZIONE, costo_stimato, prepara
from sbobina.pipeline import RIPARTENZE, Elaborazione, File, prepara_rielaborazione

STATIC = Path(__file__).parent / "static"


def richiede_intestazione(x_sbobina: str | None = Header(default=None)) -> None:
    """Le richieste che modificano dati devono avere l'intestazione X-Sbobina.

    Un sito esterno aperto nel browser non può aggiungerla senza il permesso CORS,
    quindi non può caricare lezioni o cancellarle a tua insaputa.
    """
    if x_sbobina != "1":
        raise HTTPException(403, "Richiesta non consentita")


class Rielaborazione(BaseModel):
    da: str = "appunti"


class Approfondimento(BaseModel):
    argomento: str = ""


class Domanda(BaseModel):
    domanda: str
    corso: str = ""


class Testo(BaseModel):
    testo: str


class Esito(BaseModel):
    id: str
    giusta: bool


class NuovaRegistrazione(BaseModel):
    corso: str
    titolo: str = ""
    data: str = ""


class Glossario(BaseModel):
    corso: str
    termini: list[str]


MESI = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")


def data_leggibile(iso: str) -> str:
    """2026-10-12 → 12 ott 2026 (testo libero lasciato com'è)."""
    try:
        anno, mese, giorno = (int(x) for x in iso.split("-"))
        return f"{giorno} {MESI[mese - 1]} {anno}"
    except (ValueError, IndexError):
        return iso


def durata_leggibile(secondi: float | None) -> str:
    if not secondi:
        return ""
    minuti = round(secondi / 60)
    return f"{minuti} min" if minuti < 60 else f"{minuti // 60} h {minuti % 60:02d} min"


def stime(lezioni: list[Lezione]) -> dict[str, float]:
    """Secondi che mancano a ogni lezione in coda o in corso, dal ritmo delle lezioni già fatte."""
    fatte = [l.secondi_elaborazione / l.durata_secondi for l in lezioni
             if l.stato == "completata" and l.secondi_elaborazione and l.durata_secondi]
    ritmo = sorted(fatte)[len(fatte) // 2] if fatte else 1.5  # senza storia: 1,5 volte la durata dell'audio
    attese: dict[str, float] = {}
    accumulato = 0.0
    attive = sorted((l for l in lezioni if l.stato in ATTIVI), key=lambda l: (l.stato != "in_elaborazione", l.creata))
    for l in attive:
        totale = (l.durata_secondi or 3600) * ritmo
        resto = totale * (1 - l.progresso) if l.stato == "in_elaborazione" else totale
        accumulato += resto
        attese[l.id] = round(accumulato)
    return attese


def riassunto(lezione: Lezione) -> dict:
    return {
        "id": lezione.id,
        "titolo": lezione.titolo,
        "corso": lezione.corso,
        "data": lezione.data,
        "stato": lezione.stato,
        "fase": lezione.fase,
        "progresso": lezione.progresso,
        "messaggio": lezione.messaggio,
        "errore": lezione.errore,
        "durata_secondi": lezione.durata_secondi,
    }


def _salva_upload(upload: UploadFile, cartella: Path) -> Path:
    destinazione = cartella / f"{len(list(cartella.iterdir()))}{Path(upload.filename or '').suffix.lower()}"
    with destinazione.open("wb") as uscita:
        shutil.copyfileobj(upload.file, uscita, length=1024 * 1024)
    return destinazione


def crea_app(
    config: Config,
    crea_elaborazione: Callable[[], Elaborazione] | None = None,
    avvia_coda: bool = True,
    host_ammessi: tuple[str, ...] = ("127.0.0.1", "localhost"),
) -> FastAPI:
    archivio = Archivio(config.cartella_dati)

    if crea_elaborazione is None:

        def crea_elaborazione() -> Elaborazione:
            from sbobina.llm import crea_modello
            from sbobina.trascrizione import crea_motori

            imp = impostazioni.carica(config.cartella_dati)
            effettiva = imp.applica(config)
            modello = crea_modello(effettiva.modello, temperatura=imp.temperatura, contesto=imp.contesto_effettivo())
            return Elaborazione(effettiva, archivio, modello, crea_motori(effettiva))

    def effettiva() -> Config:
        return impostazioni.carica(config.cartella_dati).applica(config)

    coda = Coda(archivio, crea_elaborazione)

    @asynccontextmanager
    async def ciclo_di_vita(_app: FastAPI):
        if avvia_coda:
            coda.avvia()
        yield

    app = FastAPI(title="Sbobina", lifespan=ciclo_di_vita, docs_url=None, redoc_url=None, openapi_url=None)
    # Contro il DNS rebinding: un sito esterno che punta a 127.0.0.1 arriva con un Host diverso.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(host_ammessi))
    app.state.archivio = archivio
    app.state.coda = coda
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    protetto = [Depends(richiede_intestazione)]

    def trova(id_lezione: str) -> Lezione:
        try:
            return archivio.carica(id_lezione)
        except KeyError:
            raise HTTPException(404, "Lezione non trovata") from None

    @app.get("/", response_class=HTMLResponse)
    def pagina() -> str:
        return (STATIC / "index.html").read_text(encoding="utf-8").replace("<!-- LIBRERIE -->", LIBRERIE)

    @app.get("/api/stato")
    def stato() -> dict:
        cfg = effettiva()
        imp = impostazioni.carica(config.cartella_dati)
        return {
            "modello": cfg.modello,
            "motore": imp.motore_llm,
            "motori": list(cfg.motori),
            "locale": cfg.locale,
            "llm": cfg.llm_pronto,
            "impostazioni": imp.a_dict(),
            "preparazione": PREPARAZIONE,
            "ffmpeg": ffmpeg_disponibile(),
            "verifica": cfg.verifica,
            "corsi": [{"nome": c.nome, "termini": len(c.glossario)} for c in archivio.corsi()],
        }

    @app.post("/api/ai/prepara")
    def prepara_ai() -> dict:
        cfg = effettiva()
        if cfg.locale:
            threading.Thread(target=prepara, args=(cfg.modello, cfg.whisper_modello), daemon=True).start()
        return PREPARAZIONE

    @app.get("/api/diretta")
    def diretta() -> dict:
        """Le ultime parole riconosciute da Whisper o scritte dal modello, per vederlo lavorare."""
        return DIRETTA

    @app.get("/api/sistema")
    def info_sistema() -> dict:
        from sbobina.llm import pronto

        dati = sistema.proposte()
        for m in dati["modelli"]:
            m["installato"] = pronto(m["mlx"])
        dati["cartella_dati"] = str(config.cartella_dati.resolve())
        dati["aree"] = list(impostazioni.AREE)
        dati["anni"] = list(impostazioni.ANNI)
        return dati

    @app.get("/api/impostazioni")
    def leggi_impostazioni() -> dict:
        return impostazioni.carica(config.cartella_dati).a_dict()

    @app.put("/api/impostazioni", dependencies=protetto)
    def salva_impostazioni(corpo: dict) -> dict:
        try:
            imp = impostazioni.Impostazioni.da_dict(corpo, impostazioni.carica(config.cartella_dati))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        impostazioni.salva(config.cartella_dati, imp)
        return imp.a_dict()

    @app.post("/api/cartella-dati", dependencies=protetto)
    def apri_cartella_dati() -> Response:
        if os.name == "nt":
            os.startfile(config.cartella_dati.resolve())  # Esplora file
        else:
            subprocess.run(["open", str(config.cartella_dati.resolve())], check=False)
        return Response(status_code=204)

    @app.get("/api/lezioni")
    def elenco() -> list[dict]:
        lezioni = archivio.elenco()
        attese = stime(lezioni)
        return [{**riassunto(l), "stima_secondi": attese.get(l.id)} for l in lezioni]

    @app.post("/api/lezioni", dependencies=protetto)
    def nuova(
        audio: list[UploadFile] = CampoFile(...),
        corso: str = Form(...),
        titolo: str = Form(""),
        data: str = Form(""),
        note: str = Form(""),
        termini: str = Form(""),
        materiali: list[UploadFile] = CampoFile(default=[]),
    ) -> list[dict]:
        audio = [a for a in audio if a.filename]
        materiali = [m for m in materiali if m.filename]
        if not audio:
            raise HTTPException(400, "Seleziona almeno una registrazione audio.")
        if not corso.strip():
            raise HTTPException(400, "Indica il corso.")
        for upload in audio:
            if Path(upload.filename).suffix.lower() not in ESTENSIONI_AUDIO:
                raise HTTPException(400, f"Formato audio non supportato: {upload.filename}")
        for upload in materiali:
            if Path(upload.filename).suffix.lower() not in ESTENSIONI_MATERIALI:
                raise HTTPException(
                    400, f"Formato non supportato per i materiali: {upload.filename} (usa PDF, immagini o testo)"
                )

        temporanea = config.cartella_dati / "tmp"
        temporanea.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporanea) as cartella:
            cartella = Path(cartella)
            file_materiali = [(m.filename, _salva_upload(m, cartella)) for m in materiali]
            create = []
            for upload in audio:
                percorso = _salva_upload(upload, cartella)
                lezione = archivio.crea_lezione(
                    audio=percorso,
                    nome_audio=upload.filename,
                    corso=corso,
                    titolo=titolo if len(audio) == 1 else "",
                    data_lezione=data,
                    note=note,
                    materiali=file_materiali,
                    sposta=False,
                )
                create.append(lezione)
        if termini.strip():
            archivio.aggiungi_al_glossario(corso.strip(), dividi_termini(termini))
        for lezione in create:
            coda.accoda(lezione.id)
        return [riassunto(lezione) for lezione in create]

    @app.get("/api/lezioni/{id_lezione}")
    def dettaglio(id_lezione: str) -> dict:
        lezione = trova(id_lezione)
        f = File(archivio.cartella(id_lezione))

        def leggi(percorso: Path) -> str | None:
            return percorso.read_text(encoding="utf-8") if percorso.is_file() else None

        appunti = leggi(f.appunti)
        return {
            "lezione": asdict(lezione),
            "appunti": appunti or leggi(f.bozza),
            "bozza": appunti is None and f.bozza.is_file(),
            "trascrizione": leggi(f.trascrizione),
            "approfondimento": leggi(f.approfondimento),
            "verifica": leggi_json(f.verifica) if f.verifica.is_file() else None,
            "audio": f.ascolto.is_file(),
            "costo": costo_stimato(config.modello, lezione.utilizzo),
        }

    @app.get("/api/lezioni/{id_lezione}/audio")
    def audio_lezione(id_lezione: str) -> FileResponse:
        trova(id_lezione)
        percorso = File(archivio.cartella(id_lezione)).ascolto
        if not percorso.is_file():
            raise HTTPException(404, "Audio non ancora pronto")
        return FileResponse(percorso, media_type="audio/mpeg")

    @app.get("/api/lezioni/{id_lezione}/scarica/{formato}")
    def scarica(id_lezione: str, formato: str, allegato: bool = False, contenuto: str = "") -> FileResponse:
        lezione = trova(id_lezione)
        f = File(archivio.cartella(id_lezione))
        nome = slug(f"{lezione.corso} {lezione.titolo}", 80)
        opzioni = {
            "md": (f.appunti, "text/markdown; charset=utf-8", f"{nome}.md"),
            "html": (f.html, "text/html; charset=utf-8", f"{nome}.html"),
            "trascrizione": (f.trascrizione, "text/markdown; charset=utf-8", f"{nome}-trascrizione.md"),
        }
        if formato == "pdf":
            return _pdf(lezione, f, nome, contenuto or impostazioni.carica(config.cartella_dati).pdf)
        if formato not in opzioni:
            raise HTTPException(404, "Formato non disponibile")
        percorso, tipo, nome_file = opzioni[formato]
        if not percorso.is_file():
            raise HTTPException(404, "File non ancora pronto")
        if formato == "html" and not allegato:
            return FileResponse(percorso, media_type=tipo)  # si apre nel browser, pronta da stampare
        return FileResponse(percorso, media_type=tipo, filename=nome_file)

    def _pdf(lezione: Lezione, f: File, nome: str, contenuto: str) -> FileResponse:
        if contenuto not in impostazioni.PDF:
            raise HTTPException(400, f"Contenuto del PDF non valido: {contenuto}")
        if not f.appunti.is_file():
            raise HTTPException(404, "Gli appunti non sono ancora pronti.")
        leggi = lambda p: p.read_text(encoding="utf-8") if p.is_file() else ""  # noqa: E731
        parti = [("Appunti della lezione", leggi(f.appunti))]
        if contenuto == "approfondimento" and f.approfondimento.is_file():
            parti.append(("Approfondimento", leggi(f.approfondimento)))
        if contenuto == "trascrizione" and f.trascrizione.is_file():
            parti.append(("Trascrizione revisionata", leggi(f.trascrizione)))
        destinazione = f.pdf if contenuto == "appunti" else f.pdf.with_name(f"appunti-{contenuto}.pdf")
        fonti = [f.appunti, f.approfondimento, f.trascrizione]
        if not destinazione.is_file() or any(
            p.is_file() and p.stat().st_mtime > destinazione.stat().st_mtime for p in fonti
        ):
            pagina = esporta_pdf_html(
                titolo=lezione.titolo, corso=lezione.corso, data=data_leggibile(lezione.data), parti=parti,
                durata=durata_leggibile(lezione.durata_secondi),
            )
            try:
                crea_pdf(pagina, destinazione)
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
                raise HTTPException(503, str(e)) from e
        suffisso = "" if contenuto == "appunti" else f"-{contenuto}"
        return FileResponse(destinazione, media_type="application/pdf", filename=f"{nome}{suffisso}.pdf")

    @app.get("/api/corsi/pdf")
    def pdf_corso(corso: str) -> FileResponse:
        """Tutte le lezioni pronte di un corso in un unico PDF, in ordine di data, con indice."""
        lezioni = sorted(
            (l for l in archivio.elenco() if l.corso == corso and l.stato == "completata"),
            key=lambda l: (l.data or "", l.creata),
        )
        parti = []
        for l in lezioni:
            appunti = File(archivio.cartella(l.id)).appunti
            if appunti.is_file():
                parti.append((f"{l.titolo} · {data_leggibile(l.data)}" if l.data else l.titolo, appunti.read_text(encoding="utf-8")))
        if not parti:
            raise HTTPException(404, "Questo corso non ha ancora lezioni pronte.")
        ore = sum(l.durata_secondi or 0 for l in lezioni)
        pagina = esporta_pdf_html(
            titolo="Tutte le lezioni", corso=corso, data=f"{len(parti)} lezioni", parti=parti,
            durata=durata_leggibile(ore),
        )
        destinazione = config.cartella_dati / "esportazioni" / f"{slug(corso, 80)}.pdf"
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        try:
            crea_pdf(pagina, destinazione)
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            raise HTTPException(503, str(e)) from e
        return FileResponse(destinazione, media_type="application/pdf", filename=f"{slug(corso, 80)}.pdf")

    @app.post("/api/lezioni/{id_lezione}/approfondisci", dependencies=protetto)
    def approfondisci(id_lezione: str, corpo: Approfondimento) -> dict:
        """Aggiunge un argomento da approfondire (o crea l'approfondimento mancante) e rimette in coda."""
        lezione = trova(id_lezione)
        if lezione.stato in ATTIVI:
            raise HTTPException(409, "La lezione è già in elaborazione.")
        if lezione.stato != "completata":
            raise HTTPException(409, "Prima devono essere pronti gli appunti.")
        argomento = " ".join(corpo.argomento.split())[:200]

        def aggiungi(lez: Lezione) -> None:
            if argomento and argomento not in lez.da_approfondire:
                lez.da_approfondire.append(argomento)
            lez.approfondimento_richiesto = True
            lez.stato, lez.fase, lez.progresso, lez.errore, lez.messaggio = "in_coda", "In coda", 0.0, "", ""

        lezione = archivio.modifica(id_lezione, aggiungi)
        coda.accoda(id_lezione)
        return riassunto(lezione)

    @app.post("/api/lezioni/{id_lezione}/rielabora", dependencies=protetto)
    def rielabora(id_lezione: str, corpo: Rielaborazione) -> dict:
        lezione = trova(id_lezione)
        if lezione.stato in ATTIVI:
            raise HTTPException(409, "La lezione è già in elaborazione.")
        if corpo.da not in RIPARTENZE:
            raise HTTPException(400, f"Valore non valido: {corpo.da}")
        lezione = prepara_rielaborazione(archivio, id_lezione, corpo.da)
        coda.accoda(id_lezione)
        return riassunto(lezione)

    @app.post("/api/lezioni/{id_lezione}/ferma", dependencies=protetto)
    def ferma(id_lezione: str) -> dict:
        lezione = trova(id_lezione)
        if lezione.stato == "in_coda":
            lezione = archivio.aggiorna(id_lezione, stato="fermata", messaggio="")
        elif lezione.stato == "in_elaborazione":
            FERMA.set()  # la pipeline si ferma al prossimo controllo e salva lo stato "fermata"
        else:
            raise HTTPException(409, "La lezione non è in elaborazione.")
        return riassunto(lezione)

    @app.delete("/api/lezioni/{id_lezione}", dependencies=protetto)
    def elimina(id_lezione: str) -> Response:
        lezione = trova(id_lezione)
        if lezione.stato == "in_elaborazione":
            raise HTTPException(409, "Attendi la fine dell'elaborazione prima di eliminare la lezione.")
        archivio.elimina(id_lezione)
        return Response(status_code=204)

    # --- studio: ricerca, modifica, quiz, flashcard, domande, esportazioni -------

    ripasso = studio.Ripasso(archivio)
    registratore = Registratore(config.cartella_dati / "registrazioni")

    def modello_interattivo():
        """Il modello per le richieste dallo studente; con un modello locale aspetta la fine delle lezioni."""
        from sbobina.llm import crea_modello

        imp = impostazioni.carica(config.cartella_dati)
        cfg = imp.applica(config)
        if not cfg.llm_pronto:
            raise HTTPException(409, "L'AI non è pronta: preparala dalle Impostazioni.")
        if cfg.locale and any(l.stato == "in_elaborazione" for l in archivio.elenco()):
            raise HTTPException(409, "L'AI sta scrivendo gli appunti di una lezione: riprova quando ha finito.")
        return crea_modello(cfg.modello, temperatura=imp.temperatura, contesto=imp.contesto_effettivo())

    def genera(funzione, *argomenti):
        if not studio.OCCUPATO.acquire(blocking=False):
            raise HTTPException(409, "Sto già rispondendo a un'altra richiesta: un attimo.")
        try:
            return funzione(*argomenti)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        except Exception as e:  # noqa: BLE001 - ErroreClaude, rete, memoria: il messaggio va allo studente
            raise HTTPException(503, str(e)) from e
        finally:
            studio.OCCUPATO.release()

    @app.get("/api/cerca")
    def cerca(q: str = "") -> list[dict]:
        return studio.cerca(archivio, q[:200])

    @app.put("/api/lezioni/{id_lezione}/appunti", dependencies=protetto)
    def modifica_appunti(id_lezione: str, corpo: Testo) -> dict:
        lezione = trova(id_lezione)
        if lezione.stato in ATTIVI:
            raise HTTPException(409, "Aspetta la fine dell'elaborazione prima di modificare gli appunti.")
        if not corpo.testo.strip() or len(corpo.testo) > 2_000_000:
            raise HTTPException(400, "Il testo degli appunti è vuoto o troppo lungo.")
        f = File(archivio.cartella(id_lezione))
        originali = f.cartella / "appunti_originali.md"
        if f.appunti.is_file() and not originali.is_file():
            shutil.copy2(f.appunti, originali)  # la versione dell'AI resta, per tornare indietro
        testo = corpo.testo.rstrip() + "\n"
        scrivi_atomico(f.appunti, testo)
        scrivi_atomico(f.html, esporta_html(titolo=lezione.titolo, corso=lezione.corso, data=lezione.data, appunti=testo))
        for vecchio in f.cartella.glob("appunti*.pdf"):
            vecchio.unlink(missing_ok=True)
        return {"appunti": testo, "originali": originali.is_file()}

    @app.post("/api/lezioni/{id_lezione}/appunti/ripristina", dependencies=protetto)
    def ripristina_appunti(id_lezione: str) -> dict:
        lezione = trova(id_lezione)
        f = File(archivio.cartella(id_lezione))
        originali = f.cartella / "appunti_originali.md"
        if not originali.is_file():
            raise HTTPException(404, "Gli appunti non sono mai stati modificati.")
        return modifica_appunti(lezione.id, Testo(testo=originali.read_text(encoding="utf-8")))

    @app.get("/api/lezioni/{id_lezione}/studio")
    def stato_studio(id_lezione: str) -> dict:
        lezione = trova(id_lezione)
        cartella = archivio.cartella(id_lezione)
        leggi = lambda nome, vuoto: leggi_json(cartella / nome) if (cartella / nome).is_file() else vuoto  # noqa: E731
        return {
            "quiz": leggi("quiz.json", None),
            "carte": leggi("flashcard.json", {"carte": []})["carte"],
            "da_ripassare": ripasso.da_ripassare(lezione=lezione.id),
            "chat": leggi("chat.json", []),
        }

    @app.post("/api/lezioni/{id_lezione}/quiz", dependencies=protetto)
    def crea_quiz(id_lezione: str) -> dict:
        return genera(studio.genera_quiz, archivio, trova(id_lezione), modello_interattivo())

    @app.post("/api/lezioni/{id_lezione}/flashcard", dependencies=protetto)
    def crea_carte(id_lezione: str) -> dict:
        return genera(studio.genera_carte, archivio, trova(id_lezione), modello_interattivo())

    @app.post("/api/lezioni/{id_lezione}/chiedi", dependencies=protetto)
    def chiedi_alla_lezione(id_lezione: str, corpo: Domanda) -> list[dict]:
        domanda = " ".join(corpo.domanda.split())[:1000]
        if not domanda:
            raise HTTPException(400, "Scrivi una domanda.")
        return genera(studio.chiedi, archivio, trova(id_lezione), modello_interattivo(), domanda)

    @app.delete("/api/lezioni/{id_lezione}/chat", dependencies=protetto)
    def cancella_chat(id_lezione: str) -> Response:
        (archivio.cartella(trova(id_lezione).id) / "chat.json").unlink(missing_ok=True)
        return Response(status_code=204)

    @app.get("/api/chat")
    def chat_generale() -> list[dict]:
        file = archivio.radice / "chat.json"
        return leggi_json(file) if file.is_file() else []

    @app.post("/api/chiedi", dependencies=protetto)
    def chiedi_alle_lezioni(corpo: Domanda) -> list[dict]:
        domanda = " ".join(corpo.domanda.split())[:1000]
        if not domanda:
            raise HTTPException(400, "Scrivi una domanda.")
        return genera(studio.chiedi_tutte, archivio, modello_interattivo(), domanda, corpo.corso.strip())

    @app.delete("/api/chat", dependencies=protetto)
    def cancella_chat_generale() -> Response:
        (archivio.radice / "chat.json").unlink(missing_ok=True)
        return Response(status_code=204)

    @app.get("/api/ripasso")
    def da_ripassare(lezione: str = "") -> list[dict]:
        return ripasso.da_ripassare(lezione=lezione or None)

    @app.post("/api/ripasso/esito", dependencies=protetto)
    def esito_ripasso(corpo: Esito) -> dict:
        return ripasso.esito(corpo.id, corpo.giusta)

    @app.get("/api/lezioni/{id_lezione}/anki")
    def anki(id_lezione: str) -> Response:
        lezione = trova(id_lezione)
        try:
            testo = studio.esporta_anki(archivio, lezione)
        except ValueError as e:
            raise HTTPException(404, str(e)) from e
        nome = slug(f"{lezione.corso} {lezione.titolo}", 80)
        return Response(testo, media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{nome}-anki.txt"'})

    @app.get("/api/corsi/obsidian")
    def obsidian(corso: str) -> Response:
        try:
            dati = studio.esporta_obsidian(archivio, corso)
        except ValueError as e:
            raise HTTPException(404, str(e)) from e
        return Response(dati, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{slug(corso, 60)}-obsidian.zip"'})

    @app.post("/api/registrazione/avvia", dependencies=protetto)
    def avvia_registrazione() -> dict:
        if not ffmpeg_disponibile():
            raise HTTPException(503, "Manca ffmpeg, che serve per registrare.")
        try:
            registratore.avvia()
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from e
        return registratore.stato()

    @app.get("/api/registrazione")
    def stato_registrazione() -> dict:
        return registratore.stato()

    @app.post("/api/registrazione/ferma", dependencies=protetto)
    def ferma_registrazione(corpo: NuovaRegistrazione) -> dict:
        if not corpo.corso.strip():
            raise HTTPException(400, "Indica il corso.")
        try:
            file = registratore.ferma()
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from e
        lezione = archivio.crea_lezione(
            audio=file, nome_audio=file.name, corso=corpo.corso, titolo=corpo.titolo,
            data_lezione=corpo.data, sposta=True,
        )
        coda.accoda(lezione.id)
        return riassunto(lezione)

    @app.post("/api/registrazione/annulla", dependencies=protetto)
    def annulla_registrazione() -> Response:
        registratore.annulla()
        return Response(status_code=204)

    @app.get("/api/glossario")
    def leggi_glossario(corso: str) -> dict:
        trovato = archivio.carica_corso(corso)
        return {"corso": corso, "termini": trovato.glossario if trovato else []}

    @app.put("/api/glossario", dependencies=protetto)
    def salva_glossario(corpo: Glossario) -> dict:
        if not corpo.corso.strip():
            raise HTTPException(400, "Indica il corso.")
        corso = Corso(nome=corpo.corso.strip(), glossario=unisci_termini(corpo.termini))
        archivio.salva_corso(corso)
        return {"corso": corso.nome, "termini": corso.glossario}

    return app
