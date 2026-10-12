import time

import pytest
from fastapi.testclient import TestClient

from sbobina.pipeline import Elaborazione
from sbobina.server import crea_app

from conftest import FintoLLM, FintoMotore

PROTETTO = {"X-Sbobina": "1"}


@pytest.fixture
def client(config):
    def crea_elaborazione():
        return Elaborazione(config, app.state.archivio, FintoLLM(), [FintoMotore()])

    app = crea_app(config, crea_elaborazione=crea_elaborazione)
    with TestClient(app) as c:
        yield c


def _attendi(client, id_lezione, timeout=30):
    fine = time.monotonic() + timeout
    while time.monotonic() < fine:
        lezione = client.get(f"/api/lezioni/{id_lezione}").json()["lezione"]
        if lezione["stato"] in ("completata", "errore"):
            return lezione
        time.sleep(0.2)
    raise AssertionError("elaborazione troppo lenta")


def _carica(client, audio_prova, **campi):
    with audio_prova.open("rb") as f:
        return client.post(
            "/api/lezioni",
            headers=PROTETTO,
            data={"corso": "Fisica 1", "titolo": "Cinematica", "termini": "Galileo, moto uniformemente accelerato",
                  **campi},
            files=[("audio", (audio_prova.name, f, "audio/mp4")),
                   ("materiali", ("slide.txt", b"Moto rettilineo uniforme", "text/plain"))],
        )


def test_pagina_principale_con_librerie(client):
    risposta = client.get("/")
    assert risposta.status_code == 200
    assert "mermaid@11.17.2" in risposta.text and "<!-- LIBRERIE -->" not in risposta.text
    assert client.get("/static/render.js").status_code == 200


def test_stato(client):
    dati = client.get("/api/stato").json()
    assert dati["motori"] == ["finto"] and dati["ffmpeg"] is True


def test_richieste_senza_intestazione_rifiutate(client, audio_prova):
    with audio_prova.open("rb") as f:
        risposta = client.post("/api/lezioni", data={"corso": "X"}, files=[("audio", (audio_prova.name, f, "audio/mp4"))])
    assert risposta.status_code == 403
    assert client.get("/api/lezioni").json() == []


def test_formato_non_supportato(client):
    risposta = client.post(
        "/api/lezioni", headers=PROTETTO, data={"corso": "X"},
        files=[("audio", ("documento.docx", b"x", "application/octet-stream"))],
    )
    assert risposta.status_code == 400 and "non supportato" in risposta.json()["detail"]


def test_ciclo_completo(client, audio_prova):
    risposta = _carica(client, audio_prova)
    assert risposta.status_code == 200, risposta.text
    [creata] = risposta.json()
    assert creata["titolo"] == "Cinematica"

    lezione = _attendi(client, creata["id"])
    assert lezione["stato"] == "completata", lezione["errore"]

    dettaglio = client.get(f"/api/lezioni/{creata['id']}").json()
    assert dettaglio["appunti"].startswith("# Il teorema di Rolle")
    assert dettaglio["bozza"] is False
    assert dettaglio["trascrizione"].startswith("[00:00]")
    assert dettaglio["verifica"]["problemi"]
    assert dettaglio["audio"] is True
    assert dettaglio["costo"] is not None

    audio = client.get(f"/api/lezioni/{creata['id']}/audio", headers={"Range": "bytes=0-99"})
    assert audio.status_code == 206 and len(audio.content) == 100

    md = client.get(f"/api/lezioni/{creata['id']}/scarica/md")
    assert md.status_code == 200 and "attachment" in md.headers["content-disposition"]
    html = client.get(f"/api/lezioni/{creata['id']}/scarica/html")
    assert html.status_code == 200 and "content-disposition" not in html.headers

    # Il glossario del corso contiene i termini indicati al caricamento e quelli imparati
    glossario = client.get("/api/glossario", params={"corso": "Fisica 1"}).json()["termini"]
    assert "Galileo" in glossario and "teorema di Rolle" in glossario

    # Rielabora gli appunti
    risposta = client.post(f"/api/lezioni/{creata['id']}/rielabora", headers=PROTETTO, json={"da": "appunti"})
    assert risposta.status_code == 200
    assert _attendi(client, creata["id"])["stato"] == "completata"

    # Elimina
    assert client.delete(f"/api/lezioni/{creata['id']}", headers=PROTETTO).status_code == 204
    assert client.get(f"/api/lezioni/{creata['id']}").status_code == 404


def test_piu_file_diventano_piu_lezioni(client, audio_prova):
    with audio_prova.open("rb") as a, audio_prova.open("rb") as b:
        risposta = client.post(
            "/api/lezioni", headers=PROTETTO, data={"corso": "Chimica", "titolo": "ignorato"},
            files=[("audio", ("lezione_01.m4a", a, "audio/mp4")), ("audio", ("lezione_02.m4a", b, "audio/mp4"))],
        )
    titoli = [l["titolo"] for l in risposta.json()]
    assert titoli == ["lezione 01", "lezione 02"]
    for l in risposta.json():
        assert _attendi(client, l["id"])["stato"] == "completata"


def test_glossario_modificabile(client):
    risposta = client.put("/api/glossario", headers=PROTETTO, json={"corso": "Storia", "termini": ["Federico II", "federico ii", " "]})
    assert risposta.json()["termini"] == ["Federico II"]
    assert client.get("/api/glossario", params={"corso": "Storia"}).json()["termini"] == ["Federico II"]


def test_id_non_valido(client):
    assert client.get("/api/lezioni/..%2F..%2Fetc").status_code == 404
    assert client.get("/api/lezioni/NON-ESISTE").status_code == 404
