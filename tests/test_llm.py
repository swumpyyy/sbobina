"""Verifica la richiesta che l'SDK Anthropic invia davvero, con un trasporto HTTP finto."""

import json

import anthropic
import httpx2
import pytest

from sbobina.llm import Claude, ErroreClaude, Utilizzo, costo_stimato


def _sse(eventi: list[dict]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in eventi).encode()


def _risposta(testo: str, stop_reason: str = "end_turn", stop_details: dict | None = None) -> list[dict]:
    delta = {"stop_reason": stop_reason, "stop_sequence": None}
    if stop_details:
        delta["stop_details"] = stop_details
    return [
        {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": [],
            "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 1200, "output_tokens": 1, "cache_read_input_tokens": 800,
                      "cache_creation_input_tokens": 0},
        }},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": testo}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": delta, "usage": {"output_tokens": 345}},
        {"type": "message_stop"},
    ]


def _claude(eventi: list[dict], richieste: list):
    def gestore(req: httpx2.Request) -> httpx2.Response:
        richieste.append(req)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(eventi))

    client = anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(gestore))
    )
    return Claude("claude-opus-5-5", client=client)


def test_richiesta_testo():
    richieste = []
    claude = _claude(_risposta("# Appunti"), richieste)
    system = [{"type": "text", "text": "istruzioni", "cache_control": {"type": "ephemeral"}}]
    testo, uso = claude.testo(system=system, contenuto=[{"type": "text", "text": "ciao"}], sforzo="high")

    assert testo == "# Appunti"
    assert uso == Utilizzo(input=1200, output=345, cache_lettura=800, cache_scrittura=0)
    corpo = json.loads(richieste[0].content)
    assert corpo["model"] == "claude-opus-5-5"
    assert corpo["stream"] is True
    assert corpo["thinking"] == {"type": "adaptive"}
    assert corpo["output_config"] == {"effort": "high"}
    assert corpo["fallbacks"] == "default"
    assert corpo["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert corpo["messages"] == [{"role": "user", "content": [{"type": "text", "text": "ciao"}]}]
    assert "server-side-fallback-2026-07-01" in richieste[0].headers["anthropic-beta"]


def test_richiesta_json_con_schema():
    richieste = []
    claude = _claude(_risposta('{"termini": ["Rolle"]}'), richieste)
    schema = {"type": "object", "properties": {"termini": {"type": "array", "items": {"type": "string"}}},
              "required": ["termini"], "additionalProperties": False}
    dati, _ = claude.json(system="s", contenuto=[{"type": "text", "text": "x"}], schema=schema, sforzo="medium")
    assert dati == {"termini": ["Rolle"]}
    corpo = json.loads(richieste[0].content)
    assert corpo["output_config"] == {"effort": "medium", "format": {"type": "json_schema", "schema": schema}}


def test_rifiuto_diventa_errore_leggibile():
    claude = _claude(_risposta("", "refusal", {"type": "refusal", "category": "bio", "explanation": "x"}), [])
    with pytest.raises(ErroreClaude, match="rifiutato"):
        claude.testo(system="s", contenuto=[{"type": "text", "text": "x"}], sforzo="high")


def test_risposta_troncata():
    claude = _claude(_risposta("metà", "max_tokens"), [])
    with pytest.raises(ErroreClaude, match="troncata"):
        claude.testo(system="s", contenuto=[{"type": "text", "text": "x"}], sforzo="high")


def test_modello_senza_fallback():
    richieste = []
    claude = _claude(_risposta("ok"), richieste)
    claude.modello = "claude-haiku-5-5"
    claude.testo(system="s", contenuto=[{"type": "text", "text": "x"}], sforzo="low")
    corpo = json.loads(richieste[0].content)
    assert "fallbacks" not in corpo


def test_chiave_mancante_messaggio_chiaro(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))  # nessun profilo `ant auth login`
    client = anthropic.Anthropic(
        max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(lambda r: None))
    )
    with pytest.raises(ErroreClaude, match="ANTHROPIC_API_KEY"):
        Claude(client=client).testo(system="s", contenuto=[{"type": "text", "text": "x"}], sforzo="low")


def test_costo_stimato():
    utilizzo = {"appunti": {"input": 1_000_000, "output": 100_000, "cache_lettura": 0, "cache_scrittura": 0}}
    assert costo_stimato("claude-opus-5-5", utilizzo) == pytest.approx(4.0 + 2.0)
    assert costo_stimato("modello-sconosciuto", utilizzo) is None
