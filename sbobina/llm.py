"""Modelli linguistici: in locale con Ollama (gratuito) oppure Claude (Anthropic API, a pagamento)."""

from __future__ import annotations

import base64
import io
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol

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


OLLAMA_URL = "http://localhost:11434"


def _testo_documento(blocco: dict) -> str:
    """I modelli locali non leggono i PDF: ne passiamo il testo estratto."""
    pdf = PdfReader(io.BytesIO(base64.standard_b64decode(blocco["source"]["data"])))
    testo = "\n".join((p.extract_text() or "") for p in pdf.pages).strip()
    return f"<materiale nome=\"{blocco.get('title', 'documento')}\">\n{testo}\n</materiale>" if testo else ""


class Locale:
    """Modello open source eseguito sul computer da Ollama: gratuito e senza inviare dati all'esterno."""

    def __init__(
        self, modello: str, *, url: str = OLLAMA_URL, client: httpx2.Client | None = None, contesto: int = 65536
    ):
        self.modello = modello
        self.url = url.rstrip("/")
        # Trascrizione di una lezione lunga + slide supera i 40.000 token: il contesto predefinito di Ollama non basta.
        self.contesto = contesto
        # Su un portatile la scrittura degli appunti può richiedere molti minuti.
        self.client = client or httpx2.Client(timeout=httpx2.Timeout(30.0, read=3600.0))

    def testo(
        self, *, system: str | list[dict], contenuto: list[dict], sforzo: str, max_tokens: int = 64000
    ) -> tuple[str, Utilizzo]:
        return self._chiama(system, contenuto, None, max_tokens)  # sforzo: solo per Claude

    def json(
        self, *, system: str | list[dict], contenuto: list[dict], schema: dict, sforzo: str, max_tokens: int = 32000
    ) -> tuple[dict, Utilizzo]:
        testo, utilizzo = self._chiama(system, contenuto, schema, max_tokens)
        try:
            return json.loads(testo), utilizzo
        except json.JSONDecodeError as e:
            raise ErroreClaude(f"Risposta JSON non valida dal modello locale: {e}") from e

    def _chiama(
        self, system: str | list[dict], contenuto: list[dict], schema: dict | None, max_tokens: int
    ) -> tuple[str, Utilizzo]:
        if not isinstance(system, str):
            system = "\n\n".join(b["text"] for b in system if b.get("type") == "text")
        testi: list[str] = []
        immagini: list[str] = []
        for blocco in contenuto:
            if blocco["type"] == "text":
                testi.append(blocco["text"])
            elif blocco["type"] == "image":
                immagini.append(blocco["source"]["data"])
            elif blocco["type"] == "document":
                testi.append(_testo_documento(blocco))
        utente: dict[str, Any] = {"role": "user", "content": "\n\n".join(t for t in testi if t)}
        if immagini:
            utente["images"] = immagini
        corpo: dict[str, Any] = {
            "model": self.modello,
            "stream": True,
            "messages": [{"role": "system", "content": system}, utente],
            # gemma4 ragiona ad alta voce per default: su un blocco lungo esaurisce num_predict e la risposta viene troncata.
            "think": False,
            "options": {"num_ctx": self.contesto, "num_predict": max_tokens},
        }
        if schema is not None:
            corpo["format"] = schema
        # In streaming per poter fermare: chiudere la connessione interrompe anche la generazione in Ollama.
        parti: list[str] = []
        dati: dict[str, Any] = {}
        try:
            with self.client.stream("POST", f"{self.url}/api/chat", json=corpo) as risposta:
                if risposta.status_code == 404:
                    raise ErroreClaude(f"Modello {self.modello} non scaricato: esegui `ollama pull {self.modello}`.")
                if risposta.status_code >= 400:
                    risposta.read()
                    raise ErroreClaude(f"Errore da Ollama ({risposta.status_code}): {risposta.text[:300]}")
                for riga in risposta.iter_lines():
                    if FERMA.is_set():
                        raise Fermata()
                    if riga.strip():
                        dati = json.loads(riga)
                        parti.append((dati.get("message") or {}).get("content", ""))
        except httpx2.ConnectError as e:
            raise ErroreClaude("Ollama non è in esecuzione: apri l'app Ollama e riprova.") from e
        except httpx2.HTTPError as e:
            raise ErroreClaude(f"Errore di comunicazione con Ollama: {e}") from e
        if dati.get("done_reason") == "length":
            raise ErroreClaude("La risposta del modello locale è stata troncata (limite di lunghezza raggiunto).")
        testo = "".join(parti).strip()
        if not testo:
            raise ErroreClaude("Il modello locale ha restituito una risposta vuota.")
        return testo, Utilizzo(input=dati.get("prompt_eval_count") or 0, output=dati.get("eval_count") or 0)


def locale_pronto(modello: str, url: str = OLLAMA_URL) -> bool:
    """True se Ollama è in esecuzione e il modello è già scaricato."""
    try:
        nomi = {m["name"] for m in httpx2.get(f"{url}/api/tags", timeout=2.0).json().get("models", [])}
    except (httpx2.HTTPError, ValueError):
        return False
    return modello in nomi or f"{modello}:latest" in nomi


# Stato della preparazione dell'AI locale, letto da /api/stato: avvio di Ollama e download del modello.
PREPARAZIONE: dict[str, Any] = {"attiva": False, "messaggio": "", "progresso": 0.0, "errore": ""}


def avvia_ollama(url: str = OLLAMA_URL, attesa: float = 20.0) -> bool:
    """Avvia Ollama se non risponde (app per macOS, altrimenti `ollama serve`). True se ora risponde."""
    import shutil
    import subprocess
    import sys

    def risponde() -> bool:
        try:
            return httpx2.get(f"{url}/api/version", timeout=1.0).status_code == 200
        except httpx2.HTTPError:
            return False

    if risponde():
        return True
    if sys.platform == "darwin" and subprocess.run(["open", "-ga", "Ollama"], capture_output=True).returncode == 0:
        pass
    elif shutil.which("ollama"):
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        return False
    fine = time.monotonic() + attesa
    while time.monotonic() < fine:
        if risponde():
            return True
        time.sleep(0.5)
    return False


def prepara_locale(modello: str, url: str = OLLAMA_URL) -> None:
    """Avvia Ollama e scarica il modello mostrando l'avanzamento in PREPARAZIONE. Da eseguire in un thread."""
    if PREPARAZIONE["attiva"]:
        return
    PREPARAZIONE.update(attiva=True, messaggio="Avvio Ollama…", progresso=0.0, errore="")
    try:
        if not avvia_ollama(url):
            raise ErroreClaude("Ollama non è installato: scaricalo da ollama.com e riapri Sbobina.")
        if not locale_pronto(modello, url):
            with httpx2.stream("POST", f"{url}/api/pull", json={"model": modello}, timeout=None) as risposta:
                for riga in risposta.iter_lines():
                    dati = json.loads(riga) if riga.strip() else {}
                    if dati.get("error"):
                        raise ErroreClaude(dati["error"])
                    if dati.get("total"):
                        PREPARAZIONE["progresso"] = dati.get("completed", 0) / dati["total"]
                        PREPARAZIONE["messaggio"] = f"Scarico {modello}: {dati.get('completed', 0) / 1e9:.1f} di {dati['total'] / 1e9:.1f} GB"
        PREPARAZIONE.update(messaggio="Pronta", progresso=1.0)
    except (ErroreClaude, httpx2.HTTPError, ValueError) as e:
        PREPARAZIONE["errore"] = str(e)
    finally:
        PREPARAZIONE["attiva"] = False


def crea_modello(modello: str) -> ModelloLinguistico:
    return Claude(modello) if modello.startswith("claude") else Locale(modello)
