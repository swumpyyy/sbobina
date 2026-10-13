"""Modelli linguistici: in locale (gratuito: MLX su Mac, llama.cpp su Windows) oppure Claude (Anthropic API, a pagamento)."""

from __future__ import annotations

import base64
import io
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import anthropic
import httpx2
from pypdf import PdfReader

log = logging.getLogger(__name__)

# Modelli che accettano il fallback lato server: se un classificatore di sicurezza
# rifiuta per errore una lezione (es. biologia, sicurezza informatica), la richiesta
# viene ripetuta automaticamente sul modello consigliato invece di fallire.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_MODELLI_CON_FALLBACK = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

# Prezzi in dollari per milione di token: (input, output, lettura cache, scrittura cache).
PREZZI = {
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20, 2.5),
}


class ErroreClaude(RuntimeError):
    pass


class ErroreRipetizione(ErroreClaude):
    """Il modello locale è entrato in un loop: meglio fermarlo subito che aspettare il limite di token."""


class Fermata(Exception):
    """L'utente ha fermato l'elaborazione."""


# La coda elabora una lezione alla volta: un solo segnale basta.
FERMA = threading.Event()


@dataclass
class Utilizzo:
    input: int = 0
    output: int = 0
    cache_lettura: int = 0
    cache_scrittura: int = 0

    def __add__(self, altro: Utilizzo) -> Utilizzo:
        return Utilizzo(
            self.input + altro.input,
            self.output + altro.output,
            self.cache_lettura + altro.cache_lettura,
            self.cache_scrittura + altro.cache_scrittura,
        )

    def a_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def da_dict(cls, dati: dict | None) -> Utilizzo:
        return cls(**{k: int(v) for k, v in (dati or {}).items() if k in cls.__dataclass_fields__})


def costo_stimato(modello: str, utilizzi: dict[str, dict[str, int]]) -> float | None:
    if modello not in PREZZI:
        return None
    p_in, p_out, p_lettura, p_scrittura = PREZZI[modello]
    totale = sum((Utilizzo.da_dict(u) for u in utilizzi.values()), Utilizzo())
    return (
        totale.input * p_in
        + totale.output * p_out
        + totale.cache_lettura * p_lettura
        + totale.cache_scrittura * p_scrittura
    ) / 1_000_000


class ModelloLinguistico(Protocol):
    def testo(
        self, *, system: str | list[dict], contenuto: list[dict], sforzo: str, max_tokens: int = 64000
    ) -> tuple[str, Utilizzo]: ...

    def json(
        self, *, system: str | list[dict], contenuto: list[dict], schema: dict, sforzo: str, max_tokens: int = 32000
    ) -> tuple[dict, Utilizzo]: ...


class Claude:
    def __init__(self, modello: str = "claude-opus-5-5", client: anthropic.Anthropic | None = None):
        self.modello = modello
        self.client = client or anthropic.Anthropic(max_retries=4)

    def testo(
        self, *, system: str | list[dict], contenuto: list[dict], sforzo: str, max_tokens: int = 64000
    ) -> tuple[str, Utilizzo]:
        return self._chiama(system, contenuto, {"effort": sforzo}, max_tokens)

    def json(
        self, *, system: str | list[dict], contenuto: list[dict], schema: dict, sforzo: str, max_tokens: int = 32000
    ) -> tuple[dict, Utilizzo]:
        testo, utilizzo = self._chiama(
            system, contenuto, {"effort": sforzo, "format": {"type": "json_schema", "schema": schema}}, max_tokens
        )
        try:
            return json.loads(testo), utilizzo
        except json.JSONDecodeError as e:
            raise ErroreClaude(f"Risposta JSON non valida: {e}") from e

    def _chiama(
        self, system: str | list[dict], contenuto: list[dict], output_config: dict[str, Any], max_tokens: int
    ) -> tuple[str, Utilizzo]:
        parametri: dict[str, Any] = {
            "model": self.modello,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": contenuto}],
            "thinking": {"type": "adaptive"},
            "output_config": output_config,
        }
        tentativi = 3
        for tentativo in range(1, tentativi + 1):
            try:
                if self.modello in _MODELLI_CON_FALLBACK:
                    flusso = self.client.beta.messages.stream(
                        **parametri, betas=[_FALLBACK_BETA], fallbacks="default"
                    )
                else:
                    flusso = self.client.messages.stream(**parametri)
                with flusso as stream:
                    messaggio = stream.get_final_message()
                break
            except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError) as e:
                # L'SDK ripete già gli errori all'avvio della richiesta; qui copriamo
                # le interruzioni a metà di una risposta lunga.
                if tentativo == tentativi:
                    raise ErroreClaude(f"Claude non raggiungibile dopo {tentativi} tentativi: {e}") from e
                attesa = 15 * tentativo
                log.warning("Errore temporaneo da Claude (%s), nuovo tentativo tra %ss", e, attesa)
                time.sleep(attesa)
            except anthropic.AuthenticationError as e:
                raise ErroreClaude("Chiave API di Anthropic non valida: controlla ANTHROPIC_API_KEY.") from e
            except TypeError as e:
                # L'SDK solleva TypeError quando non trova nessuna credenziale.
                if "authentication method" not in str(e):
                    raise
                raise ErroreClaude(
                    "Manca la chiave di Anthropic: aggiungi ANTHROPIC_API_KEY al file .env e riavvia Sbobina."
                ) from e
            except anthropic.BadRequestError as e:
                raise ErroreClaude(f"Richiesta rifiutata da Claude: {e.message}") from e

        if messaggio.stop_reason == "refusal":
            dettagli = getattr(messaggio, "stop_details", None)
            categoria = getattr(dettagli, "category", None) if dettagli else None
            raise ErroreClaude(
                "Claude ha rifiutato di elaborare questo contenuto"
                + (f" (categoria: {categoria})" if categoria else "")
                + "."
            )
        if messaggio.stop_reason == "max_tokens":
            raise ErroreClaude("La risposta di Claude è stata troncata (limite di lunghezza raggiunto).")

        testo = "".join(b.text for b in messaggio.content if b.type == "text").strip()
        if not testo:
            raise ErroreClaude("Claude ha restituito una risposta vuota.")
        u = messaggio.usage
        utilizzo = Utilizzo(
            input=u.input_tokens or 0,
            output=u.output_tokens or 0,
            cache_lettura=getattr(u, "cache_read_input_tokens", None) or 0,
            cache_scrittura=getattr(u, "cache_creation_input_tokens", None) or 0,
        )
        return testo, utilizzo


def _testo_documento(blocco: dict) -> str:
    """I modelli locali non leggono i PDF: ne passiamo il testo estratto."""
    pdf = PdfReader(io.BytesIO(base64.standard_b64decode(blocco["source"]["data"])))
    testo = "\n".join((p.extract_text() or "") for p in pdf.pages).strip()
    return f"<materiale nome=\"{blocco.get('title', 'documento')}\">\n{testo}\n</materiale>" if testo else ""


# Stato della preparazione dell'AI locale, letto da /api/stato: download dei modelli (byte, velocità in byte/s).
PREPARAZIONE: dict[str, Any] = {
    "attiva": False, "messaggio": "", "progresso": 0.0, "errore": "", "fatto": 0, "totale": 0, "velocita": 0.0,
}

# Cosa sta facendo l'AI in questo momento, letto da /api/diretta: le ultime parole riconosciute o scritte.
# "turno" cresce a ogni nuova richiesta, così la pagina sa quando ripulire.
DIRETTA: dict[str, Any] = {"turno": 0, "testo": ""}


def inizia_diretta() -> None:
    DIRETTA.update(turno=DIRETTA["turno"] + 1, testo="")


def in_diretta(pezzo: str) -> None:
    DIRETTA["testo"] = (DIRETTA["testo"] + pezzo)[-6000:]


def in_loop(testo: str, finestra: int = 60, volte: int = 4) -> bool:
    """Il modello ripete all'infinito la stessa frase: le ultime `finestra` lettere compaiono già molte volte."""
    if len(testo) < finestra * volte:
        return False
    return testo[-2000:].count(testo[-finestra:]) >= volte


# --------------------------------------------------------------------------
# MLX: il modello gira dentro Sbobina sulla GPU del Mac, senza Ollama
# --------------------------------------------------------------------------

def _cartella_app() -> Path:
    from sbobina.sistema import CARTELLA_APP

    return CARTELLA_APP


MODELLI_LOCALI = _cartella_app() / "modelli"
_MLX: dict[str, tuple[Any, Any]] = {}  # un solo modello in memoria alla volta


def cartella_mlx(repo: str) -> Path:
    return MODELLI_LOCALI / repo.split("/")[-1]


def mlx_pronto(repo: str) -> bool:
    return (cartella_mlx(repo) / ".completo").is_file()


def _carica_mlx(repo: str) -> tuple[Any, Any]:
    if repo not in _MLX:
        from mlx_lm import load

        _MLX.clear()  # libera il modello precedente prima di caricarne un altro
        _MLX[repo] = load(str(cartella_mlx(repo)))
    return _MLX[repo]


def _ocr_windows(grezzi: bytes) -> str:
    """Il riconoscimento del testo integrato in Windows 10/11 (lingue installate nel profilo)."""
    import asyncio

    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    async def leggi() -> str:
        flusso = InMemoryRandomAccessStream()
        scrittore = DataWriter(flusso)
        scrittore.write_bytes(grezzi)
        await scrittore.store_async()
        scrittore.detach_stream()
        flusso.seek(0)
        immagine = await (await BitmapDecoder.create_async(flusso)).get_software_bitmap_async()
        motore = OcrEngine.try_create_from_user_profile_languages()
        if motore is None:
            return ""
        return "\n".join(r.text for r in (await motore.recognize_async(immagine)).lines)

    return asyncio.run(leggi())


def testo_immagine(dati_base64: str) -> str:
    """Il testo di una foto (slide, lavagna) con l'OCR del sistema (macOS o Windows): niente modelli da scaricare."""
    grezzi = base64.standard_b64decode(dati_base64)
    import sys

    if sys.platform == "win32":
        try:
            return _ocr_windows(grezzi)
        except Exception as e:  # noqa: BLE001 - OCR assente o immagine illeggibile: l'immagine viene saltata
            log.warning("OCR di Windows non riuscito: %s", e)
            return ""
    try:
        import Vision
        from Foundation import NSData
    except ImportError:
        return ""  # né macOS né Windows: l'immagine viene saltata
    dati = NSData.dataWithBytes_length_(grezzi, len(grezzi))
    richiesta = Vision.VNRecognizeTextRequest.alloc().init()
    richiesta.setRecognitionLanguages_(["it-IT", "en-US"])
    richiesta.setUsesLanguageCorrection_(True)
    gestore = Vision.VNImageRequestHandler.alloc().initWithData_options_(dati, None)
    ok, _ = gestore.performRequests_error_([richiesta], None)
    if not ok:
        return ""
    righe = [r.topCandidates_(1)[0].string() for r in (richiesta.results() or []) if r.topCandidates_(1)]
    return "\n".join(righe)


def _estrai_json(testo: str) -> dict:
    """Il JSON dalla risposta, anche se il modello lo avvolge in ```json ... ``` o aggiunge una frase."""
    pulito = testo.strip()
    if pulito.startswith("```"):
        pulito = pulito.split("\n", 1)[1] if "\n" in pulito else pulito
        pulito = pulito.rsplit("```", 1)[0]
    inizio, fine = pulito.find("{"), pulito.rfind("}")
    if inizio == -1 or fine == -1:
        raise json.JSONDecodeError("nessun oggetto JSON", pulito, 0)
    return json.loads(pulito[inizio : fine + 1])


def _solo_testo(system: str | list[dict], contenuto: list[dict], schema: dict | None) -> tuple[str, str]:
    """System e messaggio utente in testo semplice, per i modelli locali (documenti e foto diventano testo)."""
    if not isinstance(system, str):
        system = "\n\n".join(b["text"] for b in system if b.get("type") == "text")
    testi: list[str] = []
    for b in contenuto:
        if b["type"] == "text":
            testi.append(b["text"])
        elif b["type"] == "document":
            testi.append(_testo_documento(b))
        elif b["type"] == "image" and (letto := testo_immagine(b["source"]["data"])):
            # shortcut: Gemma locale qui legge solo testo; dell'immagine passa il testo (OCR), non schemi o disegni.
            testi.append(f"<materiale tipo=\"immagine\">\n{letto}\n</materiale>")
    utente = "\n\n".join(t for t in testi if t)
    if schema is not None:
        utente += ("\n\nRispondi solo con un oggetto JSON valido conforme a questo schema, senza testo prima "
                   f"o dopo e senza blocchi di codice:\n{json.dumps(schema, ensure_ascii=False)}")
    return system, utente


class MLX:
    """Gemma in formato MLX eseguito in Sbobina stessa: gratuito, privato e senza programmi da installare."""

    def __init__(self, repo: str, *, temperatura: float = 0.3, contesto: int = 65536):
        self.modello = repo
        self.temperatura = temperatura
        self.contesto = contesto

    def testo(
        self, *, system: str | list[dict], contenuto: list[dict], sforzo: str, max_tokens: int = 64000
    ) -> tuple[str, Utilizzo]:
        return self._chiama(system, contenuto, None, max_tokens)

    def json(
        self, *, system: str | list[dict], contenuto: list[dict], schema: dict, sforzo: str, max_tokens: int = 32000
    ) -> tuple[dict, Utilizzo]:
        testo, utilizzo = self._chiama(system, contenuto, schema, max_tokens)
        try:
            return _estrai_json(testo), utilizzo
        except json.JSONDecodeError as e:
            raise ErroreClaude(f"Risposta JSON non valida dal modello integrato: {e}") from e

    def _chiama(
        self, system: str | list[dict], contenuto: list[dict], schema: dict | None, max_tokens: int
    ) -> tuple[str, Utilizzo]:
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler

        system, utente = _solo_testo(system, contenuto, schema)
        try:
            assicura_mlx(self.modello)
            modello, tokenizer = _carica_mlx(self.modello)
        except (Fermata, ErroreClaude):
            raise
        except Exception as e:  # noqa: BLE001 - rete, disco o memoria: il messaggio deve arrivare allo studente
            raise ErroreClaude(f"Non riesco a caricare il modello integrato {self.modello}: {e}") from e
        messaggi = [{"role": "system", "content": system}, {"role": "user", "content": utente}]
        try:
            prompt = tokenizer.apply_chat_template(messaggi, add_generation_prompt=True, tokenize=False, enable_thinking=False)
        except Exception:  # noqa: BLE001 - alcuni template non accettano il ruolo system
            unito = [{"role": "user", "content": f"{system}\n\n{utente}"}]
            prompt = tokenizer.apply_chat_template(unito, add_generation_prompt=True, tokenize=False)
        lunghezza = len(tokenizer.encode(prompt))
        if lunghezza + max_tokens // 4 > self.contesto:
            raise ErroreClaude(
                f"La lezione è troppo lunga per la memoria impostata ({lunghezza} token su {self.contesto}): "
                "aumenta il contesto nelle Impostazioni o usa un Mac con più memoria."
            )
        from mlx_lm.sample_utils import make_logits_processors

        parti: list[str] = []
        ultima = None
        inizia_diretta()
        for i, risposta in enumerate(stream_generate(
            modello, tokenizer, prompt, max_tokens=max_tokens, sampler=make_sampler(temp=self.temperatura),
            logits_processors=make_logits_processors(repetition_penalty=1.05, repetition_context_size=256),
        )):
            if FERMA.is_set():
                raise Fermata()
            parti.append(risposta.text)
            in_diretta(risposta.text)
            ultima = risposta
            if i % 64 == 63 and in_loop("".join(parti[-400:])):
                raise ErroreRipetizione("Il modello integrato si è bloccato ripetendo la stessa frase.")
        if ultima is not None and ultima.finish_reason == "length":
            raise ErroreClaude("La risposta del modello integrato è stata troncata (limite di lunghezza raggiunto).")
        testo = "".join(parti).strip()
        if not testo:
            raise ErroreClaude("Il modello integrato ha restituito una risposta vuota.")
        uso = Utilizzo(input=getattr(ultima, "prompt_tokens", 0) or 0, output=getattr(ultima, "generation_tokens", 0) or 0)
        return testo, uso


# --------------------------------------------------------------------------
# llama.cpp: su Windows lo stesso Gemma (GGUF) gira in llama-server sulla GPU NVIDIA
# --------------------------------------------------------------------------

# shortcut: versione fissata (asset Windows verificati il 13/10/2026); aggiornarla a mano se un modello nuovo non parte.
LLAMA_VERSIONE = "b11598"
_LLAMA: dict[str, Any] = {}  # il llama-server in esecuzione: processo, porta, modello, contesto


def file_gguf(modello: str) -> Path:
    from sbobina.sistema import MODELLI

    repo = repo_mlx(modello)
    gguf = next(m["gguf"] for m in MODELLI if m["mlx"] == repo)
    return MODELLI_LOCALI / gguf.split("/")[1] / gguf.rsplit("/", 1)[1]


def gguf_pronto(modello: str) -> bool:
    return (file_gguf(modello).parent / ".completo").is_file()


def assicura_gguf(modello: str, *, fermabile: bool = True) -> None:
    from sbobina.sistema import MODELLI

    repo = repo_mlx(modello)
    gguf = next(m["gguf"] for m in MODELLI if m["mlx"] == repo)
    with _SCARICO:
        if gguf_pronto(modello):
            return
        gia_attiva = PREPARAZIONE["attiva"]
        PREPARAZIONE.update(attiva=True, errore="")
        try:
            repo_hf, nome = gguf.rsplit("/", 1)
            scarica_hf(repo_hf, file_gguf(modello).parent, "il modello degli appunti", fermabile=fermabile, file=nome)
        finally:
            if not gia_attiva:
                PREPARAZIONE["attiva"] = False


def llama_server() -> Path:
    """llama-server.exe dalle release ufficiali di llama.cpp: CUDA con una scheda NVIDIA, altrimenti Vulkan."""
    import shutil
    import zipfile

    cartella = _cartella_app() / "llama.cpp" / LLAMA_VERSIONE
    if (cartella / ".completo").is_file():
        return next(cartella.rglob("llama-server.exe"))
    cuda = bool(shutil.which("nvidia-smi"))
    variante = "cuda-13.4" if cuda else "vulkan"
    base = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_VERSIONE}/"
    archivi = [f"llama-{LLAMA_VERSIONE}-bin-win-{variante}-x64.zip"] + ([f"cudart-llama-bin-win-{variante}-x64.zip"] if cuda else [])
    cartella.mkdir(parents=True, exist_ok=True)
    for nome in archivi:
        zip_locale = cartella / nome
        with httpx2.stream("GET", base + nome, follow_redirects=True, timeout=60) as risposta:
            risposta.raise_for_status()
            totale = int(risposta.headers.get("content-length") or 0) or 1
            fatto = 0
            with zip_locale.open("wb") as f:
                for pezzo in risposta.iter_bytes(1 << 20):
                    f.write(pezzo)
                    fatto += len(pezzo)
                    PREPARAZIONE.update(progresso=min(0.99, fatto / totale),
                                        messaggio=f"Scarico il motore AI: {fatto / 1e6:.0f} di {totale / 1e6:.0f} MB")
        with zipfile.ZipFile(zip_locale) as z:
            z.extractall(cartella)
        zip_locale.unlink()
    (cartella / ".completo").touch()
    return next(cartella.rglob("llama-server.exe"))


def ferma_llama() -> None:
    processo = _LLAMA.pop("processo", None)
    if processo is not None and processo.poll() is None:
        processo.kill()
        processo.wait()
    _LLAMA.clear()


def _avvia_llama(modello: Path, contesto: int) -> str:
    """L'indirizzo di un llama-server con `modello` caricato; lo (ri)avvia se serve."""
    import os
    import socket
    import subprocess

    processo = _LLAMA.get("processo")
    if processo is not None and processo.poll() is None and _LLAMA.get("chiave") == (modello, contesto):
        return _LLAMA["indirizzo"]
    ferma_llama()  # un solo modello in memoria video alla volta
    eseguibile = llama_server()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    registro = _cartella_app() / "llama-server.log"
    ambiente = {**os.environ, "PATH": f"{eseguibile.parent}{os.pathsep}{eseguibile.parent.parent}{os.pathsep}{os.environ.get('PATH', '')}"}
    processo = subprocess.Popen(
        # --fit sceglie da solo quanti strati tenere sulla GPU: il resto va in RAM invece di fallire.
        [str(eseguibile), "-m", str(modello), "-c", str(contesto), "-np", "1", "--fit", "on", "--reasoning", "off",
         "--host", "127.0.0.1", "--port", str(porta)],
        stdout=subprocess.DEVNULL, stderr=registro.open("w"), env=ambiente,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    indirizzo = f"http://127.0.0.1:{porta}"
    _LLAMA.update(processo=processo, indirizzo=indirizzo, chiave=(modello, contesto))
    PREPARAZIONE["messaggio"] = "Carico il modello sulla scheda video…"
    for _ in range(600):  # caricare 5-17 GB dal disco può richiedere qualche minuto
        if processo.poll() is not None:
            coda = registro.read_text(errors="replace").strip().splitlines()[-3:]
            raise ErroreClaude("Il motore AI (llama.cpp) si è chiuso: " + " | ".join(coda))
        if FERMA.is_set():
            raise Fermata()
        try:
            if httpx2.get(indirizzo + "/health", timeout=2).status_code == 200:
                return indirizzo
        except httpx2.HTTPError:
            pass
        time.sleep(1.0)
    ferma_llama()
    raise ErroreClaude("Il motore AI (llama.cpp) non ha caricato il modello in 10 minuti.")


class LlamaCpp:
    """Gemma in formato GGUF in llama-server (llama.cpp): gratuito e privato, per i PC Windows con GPU."""

    def __init__(self, modello: str, *, temperatura: float = 0.3, contesto: int = 65536):
        self.modello = repo_mlx(modello)
        self.temperatura = temperatura
        self.contesto = contesto

    testo, json = MLX.testo, MLX.json  # stessa interfaccia: cambia solo _chiama

    def _chiama(
        self, system: str | list[dict], contenuto: list[dict], schema: dict | None, max_tokens: int
    ) -> tuple[str, Utilizzo]:
        system, utente = _solo_testo(system, contenuto, schema)
        try:
            assicura_gguf(self.modello)
            indirizzo = _avvia_llama(file_gguf(self.modello), self.contesto)
        except (Fermata, ErroreClaude):
            raise
        except Exception as e:  # noqa: BLE001 - rete, disco o scheda video: il messaggio deve arrivare allo studente
            raise ErroreClaude(f"Non riesco ad avviare il modello integrato: {e}") from e
        corpo = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": utente}],
            "stream": True, "stream_options": {"include_usage": True},
            "max_tokens": max_tokens, "temperature": self.temperatura,
            "repeat_penalty": 1.05, "repeat_last_n": 256,
        }
        parti: list[str] = []
        fine, uso = None, Utilizzo()
        inizia_diretta()
        with httpx2.stream("POST", indirizzo + "/v1/chat/completions", json=corpo, timeout=httpx2.Timeout(30, read=None)) as r:
            if r.status_code != 200:
                dettaglio = r.read().decode(errors="replace")
                if "context" in dettaglio.lower():
                    raise ErroreClaude("La lezione è troppo lunga per la memoria impostata: aumenta il contesto "
                                       "nelle Impostazioni o scegli un modello più piccolo.")
                raise ErroreClaude(f"Il modello integrato ha risposto con un errore: {dettaglio[-300:]}")
            for i, riga in enumerate(r.iter_lines()):
                if FERMA.is_set():
                    raise Fermata()  # chiudere la connessione ferma anche la generazione in llama-server
                if not riga.startswith("data: ") or riga == "data: [DONE]":
                    continue
                pezzo = json.loads(riga[6:])
                if u := pezzo.get("usage"):
                    uso = Utilizzo(input=u.get("prompt_tokens", 0), output=u.get("completion_tokens", 0))
                for scelta in pezzo.get("choices") or []:
                    testo = (scelta.get("delta") or {}).get("content") or ""
                    parti.append(testo)
                    in_diretta(testo)
                    fine = scelta.get("finish_reason") or fine
                if i % 64 == 63 and in_loop("".join(parti[-400:])):
                    raise ErroreRipetizione("Il modello integrato si è bloccato ripetendo la stessa frase.")
        if fine == "length":
            raise ErroreClaude("La risposta del modello integrato è stata troncata (limite di lunghezza raggiunto).")
        testo = "".join(parti).strip()
        if not testo:
            raise ErroreClaude("Il modello integrato ha restituito una risposta vuota.")
        return testo, uso


_SCARICO = threading.Lock()  # un download alla volta: la preparazione e una lezione non scaricano due volte
_PROCESSI_SCARICO: set[Any] = set()  # da chiudere all'uscita: un download orfano litigherebbe con il prossimo


def ferma_download() -> None:
    for processo in list(_PROCESSI_SCARICO):
        processo.kill()


def scarica_hf(repo: str, cartella: Path, etichetta: str, *, fermabile: bool = False, file: str = "*") -> None:
    """Scarica un repo Hugging Face in `cartella` aggiornando PREPARAZIONE (GB, velocità).

    Il download gira in un processo a parte: se la connessione resta ferma lo si chiude e si riparte
    dai file a metà (in un thread di Python un download bloccato non si può interrompere).
    """
    import subprocess
    import sys

    from huggingface_hub import HfApi

    info = HfApi().model_info(repo, files_metadata=True)
    import fnmatch

    totale = sum((s.size or 0) for s in info.siblings or [] if fnmatch.fnmatch(s.rfilename, file)) or 1
    cartella.mkdir(parents=True, exist_ok=True)
    codice = (
        "import os,sys;os.environ['HF_HUB_DISABLE_XET']='1';from huggingface_hub import snapshot_download;"
        "snapshot_download(sys.argv[1],local_dir=sys.argv[2],allow_patterns=sys.argv[3])"
    )

    def scaricati() -> int:
        return sum(f.stat().st_size for f in cartella.rglob("*") if f.is_file())

    PREPARAZIONE.update(totale=totale, fatto=scaricati(), velocita=0.0)
    for tentativo in range(12):
        processo = subprocess.Popen(
            [sys.executable, "-c", codice, repo, str(cartella), file], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        _PROCESSI_SCARICO.add(processo)
        ultimo, fermo_da, istante = scaricati(), time.monotonic(), time.monotonic()
        try:
            while processo.poll() is None:
                time.sleep(1.0)
                if fermabile and FERMA.is_set():
                    raise Fermata()
                fatto, adesso = scaricati(), time.monotonic()
                if fatto > ultimo:
                    fermo_da = adesso
                # media mobile: la velocità non salta a ogni secondo
                istantanea = max(0, fatto - ultimo) / max(0.001, adesso - istante)
                PREPARAZIONE["velocita"] = 0.7 * PREPARAZIONE["velocita"] + 0.3 * istantanea
                ultimo, istante = fatto, adesso
                PREPARAZIONE.update(fatto=fatto, progresso=min(0.99, fatto / totale))
                PREPARAZIONE["messaggio"] = f"Scarico {etichetta}: {fatto / 1e9:.1f} di {totale / 1e9:.1f} GB"
                if adesso - fermo_da > 60:
                    PREPARAZIONE["messaggio"] = f"Connessione ferma, riprovo a scaricare {etichetta}…"
                    break
        finally:
            if processo.poll() is None:
                processo.kill()
                processo.wait()
            _PROCESSI_SCARICO.discard(processo)
        if processo.returncode == 0:
            (cartella / ".completo").touch()
            PREPARAZIONE["velocita"] = 0.0
            return
        time.sleep(min(30, 3 * (tentativo + 1)))
    dettaglio = (processo.stderr.read().decode(errors="replace").strip().splitlines() or ["connessione assente"])[-1]
    raise ErroreClaude(f"Download di {etichetta} non riuscito: {dettaglio}")


def assicura_mlx(repo: str, *, fermabile: bool = True) -> None:
    """Il modello degli appunti sul disco: lo scarica (con barra e tentativi) se manca."""
    with _SCARICO:
        if mlx_pronto(repo):
            return
        gia_attiva = PREPARAZIONE["attiva"]
        PREPARAZIONE.update(attiva=True, errore="")  # la barra di download appare anche se lo chiede una lezione
        try:
            scarica_hf(repo, cartella_mlx(repo), "il modello degli appunti", fermabile=fermabile)
        finally:
            if not gia_attiva:
                PREPARAZIONE["attiva"] = False


def _prepara(*passi: Callable[[], object]) -> None:
    """Esegue i passi di preparazione uno dopo l'altro, con stato e errori in PREPARAZIONE."""
    if PREPARAZIONE["attiva"]:
        return
    PREPARAZIONE.update(attiva=True, messaggio="Controllo i modelli…", progresso=0.0, errore="")
    try:
        for passo in passi:
            passo()
        PREPARAZIONE.update(messaggio="Pronta", progresso=1.0)
    except ErroreClaude as e:
        PREPARAZIONE["errore"] = str(e)
    except Exception as e:  # noqa: BLE001 - rete, disco, Hugging Face: il messaggio va allo studente
        PREPARAZIONE["errore"] = f"Preparazione non riuscita: {e}"
    finally:
        PREPARAZIONE["attiva"] = False


def usa_mlx() -> bool:
    """MLX sui Mac con chip Apple; altrove (Windows) llama.cpp."""
    import platform
    import sys

    return sys.platform == "darwin" and platform.machine() == "arm64"


def e_mlx(modello: str) -> bool:
    return "/" in modello


def pronto(modello: str) -> bool:
    """Il modello che scrive gli appunti è utilizzabile adesso."""
    import os

    if modello.startswith("claude"):
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    return mlx_pronto(repo_mlx(modello)) if usa_mlx() else gguf_pronto(modello)


def repo_mlx(modello: str) -> str:
    """Il repo MLX del modello: i nomi brevi (gemma4:12b, salvati dalle versioni con Ollama) diventano il repo."""
    from sbobina.sistema import MODELLI

    return modello if e_mlx(modello) else next((m["mlx"] for m in MODELLI if m["tag"] == modello), MODELLI[2]["mlx"])


def prepara(modello: str, whisper: str = "") -> None:
    """Prepara tutto ciò che serve in locale: il modello degli appunti (MLX) e Whisper."""
    from sbobina.trascrizione import whisper_locale

    def appunti() -> None:
        if usa_mlx():
            assicura_mlx(repo_mlx(modello), fermabile=False)
        else:
            assicura_gguf(modello, fermabile=False)
            with _SCARICO:
                llama_server()

    def riconoscimento() -> None:
        if not whisper:
            return
        if not whisper_locale.mlx_disponibile():
            whisper_locale.assicura_fw(whisper)
            return
        repo = whisper_locale.repo_hf(whisper)
        if whisper_locale.repo_mlx(whisper) == repo:  # non ancora scaricato
            with _SCARICO:
                scarica_hf(repo, whisper_locale.MODELLI_LOCALI / repo.split("/")[1], "il riconoscimento vocale")

    _prepara(*([appunti] if not modello.startswith("claude") else []), riconoscimento)


def crea_modello(modello: str, *, temperatura: float | None = None, contesto: int = 65536) -> ModelloLinguistico:
    if modello.startswith("claude"):
        return Claude(modello)
    classe = MLX if usa_mlx() else LlamaCpp
    return classe(repo_mlx(modello), temperatura=0.3 if temperatura is None else temperatura, contesto=contesto)
