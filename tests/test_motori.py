import json
from pathlib import Path

import httpx2
import pytest

from sbobina.trascrizione.assemblyai import MotoreAssemblyAI
from sbobina.trascrizione.base import ErroreTrascrizione
from sbobina.trascrizione.elevenlabs import MotoreElevenLabs


@pytest.fixture
def flac(tmp_path: Path) -> Path:
    percorso = tmp_path / "audio.flac"
    percorso.write_bytes(b"fLaC finto")
    return percorso


def _nulla(_):
    pass


def test_assemblyai_flusso_completo(flac):
    richieste = []
    stati = iter(["queued", "processing", "completed"])

    def gestore(req: httpx2.Request) -> httpx2.Response:
        richieste.append(req)
        assert req.headers["authorization"] == "chiave"
        if req.url.path == "/v2/upload":
            assert req.content == b"fLaC finto"
            return httpx2.Response(200, json={"upload_url": "https://cdn/audio"})
        if req.url.path == "/v2/transcript" and req.method == "POST":
            return httpx2.Response(200, json={"id": "t1", "status": "queued"})
        if req.url.path == "/v2/transcript/t1":
            stato = next(stati)
            corpo = {"id": "t1", "status": stato}
            if stato == "completed":
                corpo.update({
                    "audio_duration": 12,
                    "words": [
                        {"text": "Il", "start": 0, "end": 300, "confidence": 0.99},
                        {"text": "teorema", "start": 320, "end": 900, "confidence": 0.95},
                    ],
                })
            return httpx2.Response(200, json=corpo)
        raise AssertionError(req.url)

    motore = MotoreAssemblyAI("chiave", client=httpx2.Client(transport=httpx2.MockTransport(gestore)), attesa=0)
    avanzamenti = []
    t = motore.trascrivi(flac, lingua="it", termini=["Rolle", "una frase davvero troppo lunga per AssemblyAI"],
                         contesto="", avanzamento=avanzamenti.append)
    invio = json.loads(richieste[1].content)
    assert invio["language_code"] == "it"
    assert invio["speech_models"][0] == "universal-3-5-pro"
    assert invio["keyterms_prompt"] == ["Rolle"]
    assert [(p.testo, p.inizio, p.fine) for p in t.parole] == [("Il", 0.0, 0.3), ("teorema", 0.32, 0.9)]
    assert t.durata == 12 and avanzamenti[-1] == 1.0


def test_assemblyai_riprova_senza_termini_se_rifiutati(flac):
    invii = []

    def gestore(req):
        if req.url.path == "/v2/upload":
            return httpx2.Response(200, json={"upload_url": "u"})
        if req.method == "POST":
            corpo = json.loads(req.content)
            invii.append(corpo)
            if "keyterms_prompt" in corpo:
                return httpx2.Response(400, json={"error": "keyterms not supported"})
            return httpx2.Response(200, json={"id": "t2"})
        return httpx2.Response(200, json={"status": "completed", "words": []})

    motore = MotoreAssemblyAI("k", client=httpx2.Client(transport=httpx2.MockTransport(gestore)), attesa=0)
    motore.trascrivi(flac, lingua="it", termini=["Rolle"], contesto="", avanzamento=_nulla)
    assert "keyterms_prompt" in invii[0] and "keyterms_prompt" not in invii[1]


def test_assemblyai_errore(flac):
    def gestore(req):
        if req.url.path == "/v2/upload":
            return httpx2.Response(401, text="Invalid API key")
        raise AssertionError

    motore = MotoreAssemblyAI("k", client=httpx2.Client(transport=httpx2.MockTransport(gestore)))
    with pytest.raises(ErroreTrascrizione, match="401"):
        motore.trascrivi(flac, lingua="it", termini=[], contesto="", avanzamento=_nulla)


def test_elevenlabs_richiesta_e_parole(flac):
    def gestore(req: httpx2.Request) -> httpx2.Response:
        assert req.headers["xi-api-key"] == "chiave"
        corpo = req.content.decode("latin-1")
        assert 'name="model_id"' in corpo and "scribe_v2" in corpo
        # "[vietato]" perde le parentesi (caratteri non ammessi) ma resta come termine
        assert corpo.count('name="keyterms"') == 3
        assert "\r\n\r\nvietato\r\n" in corpo and "[vietato]" not in corpo
        assert 'name="file"' in corpo
        return httpx2.Response(200, json={
            "language_code": "it",
            "audio_duration_secs": 5.0,
            "words": [
                {"text": "Buongiorno", "type": "word", "start": 0.1, "end": 0.7, "logprob": -0.01},
                {"text": " ", "type": "spacing", "start": 0.7, "end": 0.8},
                {"text": "(risate)", "type": "audio_event", "start": 0.8, "end": 1.0},
                {"text": "ragazzi.", "type": "word", "start": 1.0, "end": 1.5, "logprob": -0.2},
            ],
        })

    motore = MotoreElevenLabs("chiave", client=httpx2.Client(transport=httpx2.MockTransport(gestore)))
    t = motore.trascrivi(flac, lingua="it", termini=["Rolle", "Lagrange", "[vietato]"], contesto="", avanzamento=_nulla)
    assert [p.testo for p in t.parole] == ["Buongiorno", "ragazzi."]
    assert t.parole[0].confidenza == pytest.approx(0.99, abs=0.01)
    assert t.durata == 5.0


def test_elevenlabs_riprova_senza_termini(flac):
    chiamate = []

    def gestore(req):
        chiamate.append('name="keyterms"' in req.content.decode("latin-1"))
        if chiamate[-1]:
            return httpx2.Response(422, json={"detail": "invalid keyterms"})
        return httpx2.Response(200, json={"words": [{"text": "ok", "type": "word", "start": 0, "end": 1}]})

    motore = MotoreElevenLabs("k", client=httpx2.Client(transport=httpx2.MockTransport(gestore)))
    t = motore.trascrivi(flac, lingua="it", termini=["Rolle"], contesto="", avanzamento=_nulla)
    assert chiamate == [True, False] and t.parole[0].testo == "ok"
