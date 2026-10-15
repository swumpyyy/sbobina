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
    with TestClient(app, base_url="http://localhost") as c:
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
    assert "/static/vendor/mermaid.min.js" in risposta.text and "<!-- LIBRERIE -->" not in risposta.text
    assert "cdn.jsdelivr" not in risposta.text  # niente rete: gli appunti si vedono anche offline
    for percorso in ("/static/render.js", "/static/vendor/mermaid.min.js", "/static/vendor/katex/katex.min.css"):
        assert client.get(percorso).status_code == 200


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
    assert dettaglio["costo"] is None  # modello locale predefinito: gratuito

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


def test_approfondisci_e_pdf(client, audio_prova):
    [creata] = _carica(client, audio_prova).json()
    assert _attendi(client, creata["id"])["stato"] == "completata"
    dettaglio = client.get(f"/api/lezioni/{creata['id']}").json()
    assert dettaglio["approfondimento"].startswith("# Approfondimento")

    risposta = client.post(f"/api/lezioni/{creata['id']}/approfondisci", headers=PROTETTO,
                           json={"argomento": "  moto   parabolico "})
    assert risposta.status_code == 200, risposta.text
    assert _attendi(client, creata["id"])["stato"] == "completata"
    dettaglio = client.get(f"/api/lezioni/{creata['id']}").json()
    assert "## Approfondimento: moto parabolico" in dettaglio["approfondimento"]
    assert dettaglio["lezione"]["da_approfondire"] == []

    from sbobina.esporta import trova_browser
    if not trova_browser():
        pytest.skip("Chrome non installato: il PDF non si può generare")
    pdf = client.get(f"/api/lezioni/{creata['id']}/scarica/pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    con_trascrizione = client.get(f"/api/lezioni/{creata['id']}/scarica/pdf?contenuto=trascrizione")
    assert con_trascrizione.status_code == 200 and "trascrizione" in con_trascrizione.headers["content-disposition"]
    assert len(con_trascrizione.content) != len(pdf.content)
    assert client.get(f"/api/lezioni/{creata['id']}/scarica/pdf?contenuto=boh").status_code == 400
    corso = client.get("/api/corsi/pdf", params={"corso": "Fisica 1"})
    assert corso.status_code == 200 and corso.content.startswith(b"%PDF")
    assert client.get("/api/corsi/pdf", params={"corso": "Inesistente"}).status_code == 404


def test_approfondisci_richiede_appunti_pronti(client, audio_prova):
    [creata] = _carica(client, audio_prova).json()
    _attendi(client, creata["id"])
    client.app.state.archivio.aggiorna(creata["id"], stato="errore")
    risposta = client.post(f"/api/lezioni/{creata['id']}/approfondisci", headers=PROTETTO, json={"argomento": "x"})
    assert risposta.status_code == 409


def test_ferma_lezione_in_coda(config, audio_prova):
    with TestClient(crea_app(config, avvia_coda=False), base_url="http://localhost") as client:
        [creata] = _carica(client, audio_prova).json()
        risposta = client.post(f"/api/lezioni/{creata['id']}/ferma", headers=PROTETTO)
        assert risposta.status_code == 200 and risposta.json()["stato"] == "fermata"
        assert client.post(f"/api/lezioni/{creata['id']}/ferma", headers=PROTETTO).status_code == 409


def test_host_estraneo_rifiutato(client):
    # DNS rebinding: la richiesta arriva a 127.0.0.1 ma con l'Host del sito estraneo.
    assert client.get("/api/lezioni", headers={"Host": "evil.com"}).status_code == 400


def test_corsi_con_lo_stesso_slug_restano_separati(client):
    client.put("/api/glossario", headers=PROTETTO, json={"corso": "C", "termini": ["puntatore"]})
    client.put("/api/glossario", headers=PROTETTO, json={"corso": "C++", "termini": ["template"]})
    assert client.get("/api/glossario", params={"corso": "C"}).json()["termini"] == ["puntatore"]
    assert client.get("/api/glossario", params={"corso": "C++"}).json()["termini"] == ["template"]


def test_un_corso_rovinato_non_blocca_lo_stato(client, config):
    (config.cartella_dati / "corsi" / "rotto.json").write_text("{", encoding="utf-8")
    assert client.get("/api/stato").status_code == 200


def test_versione_una_sola_in_tutto_il_progetto():
    """pyproject, il pacchetto e l'etichetta in alto a sinistra dell'app dicono la stessa versione."""
    import tomllib
    from pathlib import Path

    import sbobina

    radice = Path(__file__).resolve().parents[1]
    assert tomllib.loads((radice / "pyproject.toml").read_text())["project"]["version"] == sbobina.__version__
    breve = ".".join(sbobina.__version__.split(".")[:2])
    assert f"SBOBINA.OS {breve}<" in (radice / "sbobina/static/index.html").read_text()
