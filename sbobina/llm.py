"""Modelli linguistici: in locale con Ollama (gratuito) oppure Claude (Anthropic API, a pagamento)."""

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
        self, modello: str, *, url: str = OLLAMA_URL, client: httpx2.Client | None = None, contesto: int = 65536,
        temperatura: float | None = None,
    ):
        self.modello = modello
        self.temperatura = temperatura
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
        if self.temperatura is not None:
            corpo["options"]["temperature"] = self.temperatura
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


_OLLAMA_NOSTRO: Any = None  # il processo `ollama serve` avviato da Sbobina, da chiudere all'uscita


def ferma_ollama() -> None:
    """Chiude `ollama serve` se l'ha avviato Sbobina (l'app Ollama aperta dallo studente resta)."""
    global _OLLAMA_NOSTRO
    if _OLLAMA_NOSTRO is not None and _OLLAMA_NOSTRO.poll() is None:
        _OLLAMA_NOSTRO.terminate()
        try:
            _OLLAMA_NOSTRO.wait(timeout=5)
        except Exception:  # noqa: BLE001 - all'uscita: meglio forzare che restare appesi
            _OLLAMA_NOSTRO.kill()
    _OLLAMA_NOSTRO = None


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
        global _OLLAMA_NOSTRO
        _OLLAMA_NOSTRO = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    _prepara(lambda: _ollama(modello, url))


def _ollama(modello: str, url: str = OLLAMA_URL) -> None:
    PREPARAZIONE["messaggio"] = "Avvio Ollama…"
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


# --------------------------------------------------------------------------
# MLX: il modello gira dentro Sbobina sulla GPU del Mac, senza Ollama
# --------------------------------------------------------------------------

MODELLI_LOCALI = Path.home() / "Library/Application Support/Sbobina/modelli"
_MLX: dict[str, tuple[Any, Any]] = {}  # un solo modello in memoria alla volta


def cartella_mlx(repo: str) -> Path:
    return MODELLI_LOCALI / repo.split("/")[-1]


def mlx_pronto(repo: str) -> bool:
    return (cartella_mlx(repo) / ".completo").is_file()


def _carica_mlx(repo: str) -> tuple[Any, Any]:
    if repo not in _MLX:
        from mlx_lm import load

        _MLX.clear()  # libera il modello precedente prima di caricarne un altro
        _MLX[repo] = load(str(cartella_mlx(repo)) if mlx_pronto(repo) else repo)
    return _MLX[repo]


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

        if not isinstance(system, str):
            system = "\n\n".join(b["text"] for b in system if b.get("type") == "text")
        # shortcut: MLX legge solo testo, le immagini dei materiali vengono saltate; per le foto della lavagna usa Ollama o Claude.
        testi = [b["text"] if b["type"] == "text" else _testo_documento(b) for b in contenuto if b["type"] in ("text", "document")]
        utente = "\n\n".join(t for t in testi if t)
        if schema is not None:
            utente += ("\n\nRispondi solo con un oggetto JSON valido conforme a questo schema, senza testo prima "
                       f"o dopo e senza blocchi di codice:\n{json.dumps(schema, ensure_ascii=False)}")
        try:
            modello, tokenizer = _carica_mlx(self.modello)
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
        parti: list[str] = []
        ultima = None
        for risposta in stream_generate(
            modello, tokenizer, prompt, max_tokens=max_tokens, sampler=make_sampler(temp=self.temperatura)
        ):
            if FERMA.is_set():
                raise Fermata()
            parti.append(risposta.text)
            ultima = risposta
        if ultima is not None and ultima.finish_reason == "length":
            raise ErroreClaude("La risposta del modello integrato è stata troncata (limite di lunghezza raggiunto).")
        testo = "".join(parti).strip()
        if not testo:
            raise ErroreClaude("Il modello integrato ha restituito una risposta vuota.")
        uso = Utilizzo(input=getattr(ultima, "prompt_tokens", 0) or 0, output=getattr(ultima, "generation_tokens", 0) or 0)
        return testo, uso


def scarica_hf(repo: str, cartella: Path, etichetta: str) -> None:
    """Scarica un repo Hugging Face in `cartella` aggiornando PREPARAZIONE con i GB scaricati."""
    import threading as _t

    from huggingface_hub import HfApi, snapshot_download

    info = HfApi().model_info(repo, files_metadata=True)
    totale = sum((s.size or 0) for s in info.siblings or []) or 1
    cartella.mkdir(parents=True, exist_ok=True)
    errore: list[BaseException] = []

    def scarica() -> None:
        # Le connessioni lente cadono: snapshot_download riprende dai file a metà, quindi si ritenta.
        for tentativo in range(4):
            try:
                snapshot_download(repo, local_dir=cartella)
                return
            except Exception as e:  # noqa: BLE001 - riportato sotto dopo l'ultimo tentativo
                if tentativo == 3:
                    errore.append(e)
                time.sleep(3 * (tentativo + 1))

    lavoro = _t.Thread(target=scarica, daemon=True)
    lavoro.start()
    while lavoro.is_alive():
        fatto = sum(f.stat().st_size for f in cartella.rglob("*") if f.is_file())
        PREPARAZIONE["progresso"] = min(0.99, fatto / totale)
        PREPARAZIONE["messaggio"] = f"Scarico {etichetta}: {fatto / 1e9:.1f} di {totale / 1e9:.1f} GB"
        lavoro.join(1.0)
    if errore:
        raise ErroreClaude(f"Download di {etichetta} non riuscito: {errore[0]}")
    (cartella / ".completo").touch()


def prepara_mlx(repo: str) -> None:
    """Scarica il modello MLX che scrive gli appunti. Da eseguire in un thread."""
    _prepara(lambda: mlx_pronto(repo) or scarica_hf(repo, cartella_mlx(repo), "il modello degli appunti"))


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


def e_mlx(modello: str) -> bool:
    return "/" in modello


def pronto(modello: str) -> bool:
    """Il modello che scrive gli appunti è utilizzabile adesso."""
    import os

    if modello.startswith("claude"):
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    return mlx_pronto(modello) if e_mlx(modello) else locale_pronto(modello)


def prepara(modello: str, whisper: str = "") -> None:
    """Prepara tutto ciò che serve in locale: il modello degli appunti (MLX o Ollama) e Whisper."""
    from sbobina.trascrizione import whisper_locale

    def appunti() -> None:
        if e_mlx(modello):
            if not mlx_pronto(modello):
                scarica_hf(modello, cartella_mlx(modello), "il modello degli appunti")
        else:
            _ollama(modello)

    def riconoscimento() -> None:
        if not whisper or not whisper_locale.mlx_disponibile():
            return
        repo = whisper_locale.repo_hf(whisper)
        if whisper_locale.repo_mlx(whisper) == repo:  # non ancora scaricato
            scarica_hf(repo, whisper_locale.MODELLI_LOCALI / repo.split("/")[1], "il riconoscimento vocale")

    _prepara(*([appunti] if not modello.startswith("claude") else []), riconoscimento)


def crea_modello(modello: str, *, temperatura: float | None = None, contesto: int = 65536) -> ModelloLinguistico:
    if modello.startswith("claude"):
        return Claude(modello)
    if e_mlx(modello):
        return MLX(modello, temperatura=0.3 if temperatura is None else temperatura, contesto=contesto)
    return Locale(modello, temperatura=temperatura, contesto=contesto)
