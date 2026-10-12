"""App web locale (FastAPI): carica le lezioni, segui l'elaborazione, studia gli appunti."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from fastapi import Depends, FastAPI, File as CampoFile, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sbobina.archivio import (
    ESTENSIONI_AUDIO,
    ESTENSIONI_MATERIALI,
    Archivio,
    Corso,
    Lezione,
    dividi_termini,
    leggi_json,
    slug,
    unisci_termini,
)
from sbobina.audio import ffmpeg_disponibile
from sbobina.coda import ATTIVI, Coda
from sbobina.config import Config
from sbobina.esporta import LIBRERIE, crea_pdf, esporta_pdf_html
from sbobina.llm import costo_stimato
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


class Glossario(BaseModel):
    corso: str
    termini: list[str]


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
) -> FastAPI:
    archivio = Archivio(config.cartella_dati)

    if crea_elaborazione is None:

        def crea_elaborazione() -> Elaborazione:
            from sbobina.llm import crea_modello
            from sbobina.trascrizione import crea_motori

            return Elaborazione(config, archivio, crea_modello(config.modello), crea_motori(config))

    coda = Coda(archivio, crea_elaborazione)

    @asynccontextmanager
    async def ciclo_di_vita(_app: FastAPI):
        if avvia_coda:
            coda.avvia()
        yield

    app = FastAPI(title="Sbobina", lifespan=ciclo_di_vita, docs_url=None, redoc_url=None, openapi_url=None)
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
        return {
            "modello": config.modello,
            "motori": list(config.motori),
            "locale": config.locale,
            "llm": config.llm_pronto,
            "ffmpeg": ffmpeg_disponibile(),
            "verifica": config.verifica,
            "corsi": [{"nome": c.nome, "termini": len(c.glossario)} for c in archivio.corsi()],
        }

    @app.get("/api/lezioni")
    def elenco() -> list[dict]:
        return [riassunto(lezione) for lezione in archivio.elenco()]

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
    def scarica(id_lezione: str, formato: str, allegato: bool = False) -> FileResponse:
        lezione = trova(id_lezione)
        f = File(archivio.cartella(id_lezione))
        nome = slug(f"{lezione.corso} {lezione.titolo}", 80)
        opzioni = {
            "md": (f.appunti, "text/markdown; charset=utf-8", f"{nome}.md"),
            "html": (f.html, "text/html; charset=utf-8", f"{nome}.html"),
            "trascrizione": (f.trascrizione, "text/markdown; charset=utf-8", f"{nome}-trascrizione.md"),
        }
        if formato == "pdf":
            return _pdf(lezione, f, nome)
        if formato not in opzioni:
            raise HTTPException(404, "Formato non disponibile")
        percorso, tipo, nome_file = opzioni[formato]
        if not percorso.is_file():
            raise HTTPException(404, "File non ancora pronto")
        if formato == "html" and not allegato:
            return FileResponse(percorso, media_type=tipo)  # si apre nel browser, pronta da stampare
        return FileResponse(percorso, media_type=tipo, filename=nome_file)

    def _pdf(lezione: Lezione, f: File, nome: str) -> FileResponse:
        if not f.appunti.is_file():
            raise HTTPException(404, "Gli appunti non sono ancora pronti.")
        fonti = [f.appunti, f.approfondimento]
        if not f.pdf.is_file() or any(p.is_file() and p.stat().st_mtime > f.pdf.stat().st_mtime for p in fonti):
            pagina = esporta_pdf_html(
                titolo=lezione.titolo,
                corso=lezione.corso,
                data=lezione.data,
                appunti=f.appunti.read_text(encoding="utf-8"),
                approfondimento=f.approfondimento.read_text(encoding="utf-8") if f.approfondimento.is_file() else None,
            )
            try:
                crea_pdf(pagina, f.pdf)
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
                raise HTTPException(503, str(e)) from e
        return FileResponse(f.pdf, media_type="application/pdf", filename=f"{nome}.pdf")

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

    @app.delete("/api/lezioni/{id_lezione}", dependencies=protetto)
    def elimina(id_lezione: str) -> Response:
        lezione = trova(id_lezione)
        if lezione.stato == "in_elaborazione":
            raise HTTPException(409, "Attendi la fine dell'elaborazione prima di eliminare la lezione.")
        archivio.elimina(id_lezione)
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
