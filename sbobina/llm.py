"""Chiamate a Claude (Anthropic API)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import anthropic

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
