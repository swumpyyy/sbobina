import io
import zipfile
from datetime import date

import pytest
from fastapi.testclient import TestClient

from sbobina import studio
from sbobina.archivio import Lezione
from sbobina.registrazione import Registratore
from sbobina.server import crea_app, stime

PROTETTO = {"X-Sbobina": "1"}


class LLMStudio:
    """Risponde come farebbe il modello: quiz, carte o una risposta con il minuto."""

    def __init__(self):
        self.contenuti = []

    def json(self, *, system, contenuto, schema, sforzo, max_tokens=0):
        self.contenuti.append(contenuto)
        if "domande" in schema["properties"]:
            return {"domande": [
                {"domanda": "Che cosa tutela l'art. 18?", "opzioni": ["Associazione", "Sciopero", "Voto", "Culto"],
                 "corretta": 0, "spiegazione": "La libertà di associazione.", "tempo": "00:24"},
                {"domanda": "rotta", "opzioni": ["a"], "corretta": 5, "spiegazione": "", "tempo": ""},
            ]}, None
        return {"carte": [{"fronte": "Art. 18", "retro": "Libertà di\tassociazione", "tempo": "00:24"},
                          {"fronte": "", "retro": "vuota", "tempo": ""}]}, None

    def testo(self, *, system, contenuto, sforzo, max_tokens=0):
        self.contenuti.append(contenuto)
        return "Ne parla al minuto [00:24].", None


@pytest.fixture
def lezione(archivio, audio_prova):
    lez = archivio.crea_lezione(audio=audio_prova, nome_audio="a.wav", corso="Diritto pubblico", titolo="Associazioni",
                                data_lezione="2026-10-12")
    cartella = archivio.cartella(lez.id)
    (cartella / "appunti.md").write_text("# Associazioni\n### Art. 18 ⏱ 00:24\nLa libertà di associazione è garantita.\n", encoding="utf-8")
    (cartella / "trascrizione.md").write_text("[00:00] Buongiorno.\n\n[00:24] L'articolo 18 garantisce la libertà di associazione, perché sì.\n", encoding="utf-8")
    return archivio.aggiorna(lez.id, stato="completata", durata_secondi=600)


def test_ricerca_senza_accenti_con_tempo(archivio, lezione):
    risultati = studio.cerca(archivio, "perche ASSOCIAZIONE")
    assert len(risultati) == 1 and risultati[0]["fonte"] == "trascrizione" and risultati[0]["tempo"] == "00:24"
    assert {r["fonte"] for r in studio.cerca(archivio, "libertà")} == {"appunti", "trascrizione"}
    assert studio.cerca(archivio, " ") == []


def test_quiz_carte_e_domande(archivio, lezione):
    llm = LLMStudio()
    quiz = studio.genera_quiz(archivio, lezione, llm)
    assert len(quiz["domande"]) == 1  # la domanda rotta viene scartata
    mazzo = studio.genera_carte(archivio, lezione, llm)
    assert [c["fronte"] for c in mazzo["carte"]] == ["Art. 18"]
    storia = studio.chiedi(archivio, lezione, llm, "Dove parla dell'art. 18?")
    assert storia[-1] == {"ruolo": "sbobina", "testo": "Ne parla al minuto [00:24]."}
    assert "<trascrizione>" in llm.contenuti[-1][0]["text"]  # la domanda vede la trascrizione con i tempi
    anki = studio.esporta_anki(archivio, lezione)
    assert "#deck:Sbobina::Diritto pubblico" in anki and "Art. 18\tLibertà di associazione\tdiritto-pubblico" in anki


def test_chiedi_a_tutte_le_lezioni(archivio, lezione, audio_prova):
    altra = archivio.crea_lezione(audio=audio_prova, nome_audio="b.wav", corso="Matematica", titolo="Derivate",
                                  data_lezione="2026-10-13")
    (archivio.cartella(altra.id) / "appunti.md").write_text("# Derivate\nLa derivata misura la pendenza.\n", encoding="utf-8")
    archivio.aggiorna(altra.id, stato="completata")
    llm = LLMStudio()
    storia = studio.chiedi_tutte(archivio, llm, "Cosa dice l'articolo 18 sulle associazioni?")
    assert [f["titolo"] for f in storia[-1]["fonti"]] == ["Associazioni"]  # solo la lezione che ne parla
    assert "Derivate" not in llm.contenuti[-1][0]["text"]
    storia = studio.chiedi_tutte(archivio, llm, "Riassumi tutto")  # nessuna parola trovata: tutte le lezioni
    assert {f["titolo"] for f in storia[-1]["fonti"]} == {"Associazioni", "Derivate"}
    assert len(storia) == 4 and (archivio.radice / "chat.json").is_file()
    assert studio.chiedi_tutte(archivio, llm, "Riassumi tutto", corso="Matematica")[-1]["fonti"][0]["titolo"] == "Derivate"
    with pytest.raises(ValueError):
        studio.chiedi_tutte(archivio, llm, "Ciao", corso="Storia")


def test_leitner(archivio, lezione):
    studio.genera_carte(archivio, lezione, LLMStudio())
    ripasso = studio.Ripasso(archivio)
    oggi = date(2026, 10, 13)
    [carta] = ripasso.da_ripassare(oggi=oggi)
    assert carta["scatola"] == 1
    assert ripasso.esito(carta["id"], True, oggi) == {"scatola": 2, "prossima": "2026-10-15"}
    assert ripasso.da_ripassare(oggi=oggi) == []
    assert len(ripasso.da_ripassare(oggi=date(2026, 10, 15))) == 1
    assert ripasso.esito(carta["id"], False, oggi)["scatola"] == 1


def test_obsidian(archivio, lezione):
    with zipfile.ZipFile(io.BytesIO(studio.esporta_obsidian(archivio, "Diritto pubblico"))) as z:
        nomi = z.namelist()
        indice = z.read("diritto-pubblico/Diritto pubblico.md").decode()
        nota = z.read("diritto-pubblico/2026-10-12 Associazioni.md").decode()
    assert len(nomi) == 2 and "[[2026-10-12 Associazioni]]" in indice
    assert nota.startswith("---\ncorso: \"Diritto pubblico\"") and "tags: [sbobina, diritto-pubblico]" in nota
    with pytest.raises(ValueError):
        studio.esporta_obsidian(archivio, "Nessuno")


def test_stime_della_coda():
    def lez(id_, stato, durata, progresso=0.0, secondi=0.0, creata="1"):
        return Lezione(id=id_, titolo=id_, corso="c", data="", file_audio="a", stato=stato, durata_secondi=durata,
                       progresso=progresso, secondi_elaborazione=secondi, creata=creata)
    lezioni = [lez("fatta", "completata", 600, secondi=1200), lez("corrente", "in_elaborazione", 600, 0.5, creata="2"),
               lez("dopo", "in_coda", 300, creata="3")]
    assert stime(lezioni) == {"corrente": 600, "dopo": 1200}  # ritmo 2×: metà di 1200, poi 600 in più


def test_modifica_appunti_e_ripristino(config, lezione):
    with TestClient(crea_app(config, avvia_coda=False), base_url="http://localhost") as client:
        url = f"/api/lezioni/{lezione.id}/appunti"
        assert client.put(url, json={"testo": "x"}).status_code == 403
        risposta = client.put(url, headers=PROTETTO, json={"testo": "# Mie note\nCorrette a mano."})
        assert risposta.status_code == 200 and risposta.json()["originali"] is True
        assert client.get(f"/api/lezioni/{lezione.id}").json()["appunti"].startswith("# Mie note")
        client.post(f"{url}/ripristina", headers=PROTETTO)
        assert client.get(f"/api/lezioni/{lezione.id}").json()["appunti"].startswith("# Associazioni")
        assert client.get("/api/cerca", params={"q": "articolo 18"}).json()[0]["lezione"] == lezione.id
        assert client.get(f"/api/lezioni/{lezione.id}/anki").status_code == 404  # niente flashcard ancora
        assert "stima_secondi" in client.get("/api/lezioni").json()[0]


def test_registratore_senza_registrazione(tmp_path):
    registratore = Registratore(tmp_path)
    assert registratore.stato()["attiva"] is False
    with pytest.raises(RuntimeError, match="nessuna registrazione"):
        registratore.ferma()
