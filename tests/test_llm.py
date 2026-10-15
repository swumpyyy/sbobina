"""Verifica la richiesta che l'SDK Anthropic invia davvero, con un trasporto HTTP finto."""

import json
from pathlib import Path

import anthropic
import httpx2
import pytest

from sbobina.llm import MLX, Claude, ErroreClaude, Utilizzo, costo_stimato, crea_modello, in_loop


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
    from sbobina.llm import DIRETTA
    assert DIRETTA["nerd"].get("motore") != "Claude API"  # Claude non tocca la vista in diretta dei lavori locali
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


def test_crea_modello_sceglie_il_motore(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    # i nomi brevi delle versioni con Ollama diventano il repo MLX equivalente
    assert crea_modello("gemma4:12b").modello == "mlx-community/gemma-4-12B-it-4bit"
    assert isinstance(crea_modello("mlx-community/gemma-4-26b-a4b-it-4bit"), MLX)
    assert isinstance(crea_modello("claude-opus-5-5"), Claude)


def test_in_loop_riconosce_le_ripetizioni():
    frase = "Il teorema di Rolle vale se la funzione è continua. "
    assert in_loop("Introduzione alla lezione. " + frase * 8)
    assert not in_loop("Appunti normali che non si ripetono mai, " * 1 + "con frasi sempre diverse e nuove. " * 1)


def test_scarica_hf_completa_e_poi_si_arrende(tmp_path, monkeypatch):
    import io
    import subprocess
    from types import SimpleNamespace

    import huggingface_hub

    from sbobina import llm

    info = SimpleNamespace(siblings=[SimpleNamespace(size=10, rfilename="model.safetensors")])
    monkeypatch.setattr(huggingface_hub.HfApi, "model_info", lambda self, repo, files_metadata: info)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    class FintoProcesso:
        esito = 0

        def __init__(self, argomenti, **_):
            (Path(argomenti[-2]) / "pesi.safetensors").write_bytes(b"x" * 10)
            self.returncode, self.stderr = FintoProcesso.esito, io.BytesIO(b"rete assente")

        def poll(self):
            return self.returncode

    monkeypatch.setattr(subprocess, "Popen", FintoProcesso)
    llm.scarica_hf("org/modello", tmp_path / "ok", "il modello")
    assert (tmp_path / "ok" / ".completo").is_file() and not llm._PROCESSI_SCARICO

    FintoProcesso.esito = 1
    with pytest.raises(ErroreClaude, match="rete assente"):
        llm.scarica_hf("org/modello", tmp_path / "ko", "il modello")
    assert not (tmp_path / "ko" / ".completo").exists()


def test_fuori_dal_mac_usa_llama_cpp_con_il_gguf_giusto(monkeypatch, tmp_path):
    from sbobina import llm

    monkeypatch.setattr(llm, "usa_mlx", lambda: False)
    monkeypatch.setattr(llm, "MODELLI_LOCALI", tmp_path)
    modello = crea_modello("gemma4:e4b")
    assert isinstance(modello, llm.LlamaCpp) and modello.modello == "mlx-community/gemma-4-e4b-it-4bit"
    gguf = llm.file_gguf("gemma4:e4b")
    assert gguf == tmp_path / "gemma-4-E4B-it-GGUF" / "gemma-4-E4B-it-Q4_K_M.gguf"
    assert not llm.pronto("gemma4:e4b")
    gguf.parent.mkdir(parents=True)
    (gguf.parent / ".completo").touch()
    assert llm.pronto("gemma4:e4b")


def test_llama_cpp_legge_lo_stream_di_llama_server(monkeypatch):
    """Un finto llama-server con lo stesso formato SSE (OpenAI) di quello vero."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from sbobina import llm

    pezzi = [{"choices": [{"delta": {"content": t}, "finish_reason": None}]} for t in ('{"titolo": ', '"Rolle"}')]
    pezzi += [{"choices": [{"delta": {}, "finish_reason": "stop"}]},
              {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 5},
               "timings": {"prompt_n": 12, "prompt_per_second": 240.0, "predicted_n": 5, "predicted_per_second": 31.25}}]
    ricevuto = {}

    class Finto(BaseHTTPRequestHandler):
        def do_POST(self):
            ricevuto.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for p in pezzi:
                self.wfile.write(f"data: {json.dumps(p)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")

        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", 0), Finto)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(llm, "assicura_gguf", lambda modello: None)
    monkeypatch.setattr(llm, "_avvia_llama", lambda modello, contesto: f"http://127.0.0.1:{server.server_port}")
    try:
        dati, uso = llm.LlamaCpp("gemma4:e4b").json(
            system="Sei un tutor.", contenuto=[{"type": "text", "text": "Lezione"}], schema={"type": "object"}, sforzo="low"
        )
    finally:
        server.shutdown()
    assert dati == {"titolo": "Rolle"} and uso.input == 12 and uso.output == 5
    numeri = llm.DIRETTA["nerd"]  # la sezione nerd vede i numeri veri di llama-server
    assert numeri["motore"] == "llama.cpp" and numeri["token_al_secondo"] == 31.2 and numeri["prompt_tps"] == 240.0
    assert numeri["fine"] == "stop" and "primo_token_s" in numeri and numeri["durata_s"] >= 0
    assert ricevuto["messages"][0] == {"role": "system", "content": "Sei un tutor."} and ricevuto["stream"] is True


def test_versione_inglese_aggiunge_la_lingua_al_system():
    from sbobina.llm import InInglese

    class Eco:
        modello = "finto"

        def testo(self, *, system, contenuto, sforzo, max_tokens=64000):
            return system, None

    inglese = InInglese(Eco())
    assert inglese.modello == "finto"
    testo, _ = inglese.testo(system="Scrivi appunti.", contenuto=[], sforzo="alto")
    assert testo.startswith("Scrivi appunti.") and "in English" in testo
    blocchi, _ = inglese.testo(system=[{"type": "text", "text": "a", "cache_control": {}}], contenuto=[], sforzo="alto")
    assert blocchi[0]["cache_control"] == {} and "in English" in blocchi[-1]["text"]
