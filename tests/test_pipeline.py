import json
from dataclasses import replace

from sbobina.archivio import Archivio
from sbobina.pipeline import Elaborazione, File, prepara_rielaborazione

from conftest import APPUNTI_FINTI, FintoLLM, FintoMotore, parole_finte


def _crea(archivio: Archivio, audio, tmp_path, materiali=True):
    elenco = []
    if materiali:
        slide = tmp_path / "slide.txt"
        slide.write_text("Teorema di Rolle. Teorema di Lagrange.", encoding="utf-8")
        elenco = [("Slide lezione 3.txt", slide)]
    return archivio.crea_lezione(
        audio=audio, nome_audio=audio.name, corso="Analisi 1", data_lezione="2026-10-12",
        note="Insistere sulle ipotesi", materiali=elenco,
    )


def test_elaborazione_completa(config, archivio, audio_prova, tmp_path):
    lezione = _crea(archivio, audio_prova, tmp_path)
    motore, llm = FintoMotore(), FintoLLM()
    risultato = Elaborazione(config, archivio, llm, [motore]).esegui(lezione.id)

    assert risultato.stato == "completata", risultato.errore
    assert risultato.progresso == 1.0
    assert risultato.durata_secondi and 19 < risultato.durata_secondi < 21
    assert risultato.motori == ["finto"]
    f = File(archivio.cartella(lezione.id))
    for percorso in (f.ascolto, f.trascrizione, f.bozza, f.verifica, f.appunti, f.html, f.trascrizione_motore("finto")):
        assert percorso.is_file(), percorso
    assert not f.audio_trascrizione.exists(), "il FLAC temporaneo va cancellato dopo la trascrizione"

    # Fasi nell'ordine giusto, con più blocchi di revisione
    fasi = llm.fasi()
    assert fasi[0] == "termini"
    assert fasi.count("revisione") >= 2
    assert fasi[-4:] == ["appunti", "verifica", "correzione", "approfondimento"]

    # I termini estratti dai materiali arrivano al motore di trascrizione
    assert motore.chiamate[0]["termini"][:2] == ["Rolle", "Lagrange"]
    assert motore.chiamate[0]["lingua"] == "it"

    # La trascrizione revisionata mantiene i marcatori di tempo
    trascrizione = f.trascrizione.read_text()
    assert trascrizione.startswith("[00:00] Parola0")

    # Appunti, verifica e correzione condividono lo stesso prefisso in cache
    prefissi = [c["contenuto"][:-1] for c in llm.chiamate if c["fase"] in ("appunti", "verifica", "correzione")]
    assert prefissi[0] == prefissi[1] == prefissi[2]
    assert prefissi[0][-1]["cache_control"] == {"type": "ephemeral"}
    assert "<trascrizione>" in prefissi[0][-1]["text"]

    # La correzione applica le segnalazioni della verifica
    assert "intervallo chiuso" in f.appunti.read_text()

    # Il glossario del corso impara dalla lezione
    glossario = archivio.carica_corso("Analisi 1").glossario
    assert "teorema di Rolle" in glossario

    # Utilizzo registrato per fase e pagina esportata con gli appunti
    assert set(risultato.utilizzo) == {"termini", "revisione", "appunti", "verifica", "correzione", "approfondimento"}
    html = f.html.read_text()
    assert "Sbobina.render" in html and "teorema di rolle" in html.lower()
    assert "</script>" not in html.split("Sbobina.render(")[1].split(");</script>")[0]


def test_senza_problemi_niente_correzione(config, archivio, audio_prova, tmp_path):
    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    llm = FintoLLM(problemi=[])
    risultato = Elaborazione(config, archivio, llm, [FintoMotore()]).esegui(lezione.id)
    assert risultato.stato == "completata"
    assert "termini" not in llm.fasi(), "senza materiali non serve l'estrazione dei termini"
    assert "correzione" not in llm.fasi()
    assert File(archivio.cartella(lezione.id)).appunti.read_text().strip() == APPUNTI_FINTI


def test_due_motori_vengono_riconciliati(config, archivio, audio_prova, tmp_path):
    config = replace(config, motori=("a", "b"))
    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    a = FintoMotore("a", parole_finte(prefisso="parola"))
    b = FintoMotore("b", parole_finte(prefisso="termine"))
    llm = FintoLLM()
    risultato = Elaborazione(config, archivio, llm, [a, b]).esegui(lezione.id)
    assert risultato.stato == "completata"
    assert risultato.motori == ["a", "b"]
    messaggio = [c for c in llm.chiamate if c["fase"] == "revisione"][0]["contenuto"][0]["text"]
    assert '<trascrizione_alternativa motore="b">' in messaggio and "termine0" in messaggio


def test_un_motore_fallisce_ma_l_altro_basta(config, archivio, audio_prova, tmp_path):
    config = replace(config, motori=("a", "b"))
    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    risultato = Elaborazione(
        config, archivio, FintoLLM(), [FintoMotore("a", errore="quota esaurita"), FintoMotore("b")]
    ).esegui(lezione.id)
    assert risultato.stato == "completata"
    assert risultato.motori == ["b"]
    assert any("quota esaurita" in a for a in risultato.avvisi)


def test_errore_di_trascrizione_viene_mostrato(config, archivio, audio_prova, tmp_path):
    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    risultato = Elaborazione(config, archivio, FintoLLM(), [FintoMotore(errore="chiave non valida")]).esegui(lezione.id)
    assert risultato.stato == "errore"
    assert "chiave non valida" in risultato.errore


def test_audio_muto(config, archivio, audio_prova, tmp_path):
    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    risultato = Elaborazione(config, archivio, FintoLLM(), [FintoMotore(parole=[])]).esegui(lezione.id)
    assert risultato.stato == "errore" and "Nessuna parola" in risultato.errore


def test_revisione_troppo_corta_viene_ripetuta(config, archivio, audio_prova, tmp_path):
    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    config = replace(config, minuti_per_blocco=10)  # un solo blocco
    motore = FintoMotore(parole=parole_finte(120, passo=0.15))
    llm = FintoLLM(revisione_corta=True)
    risultato = Elaborazione(config, archivio, llm, [motore]).esegui(lezione.id)
    revisioni = [c for c in llm.chiamate if c["fase"] == "revisione"]
    assert len(revisioni) == 2
    assert "Non riassumere" in revisioni[1]["contenuto"][0]["text"]
    assert risultato.stato == "completata"


def test_ripresa_e_rielaborazione_non_ripetono_il_lavoro(config, archivio, audio_prova, tmp_path):
    lezione = _crea(archivio, audio_prova, tmp_path)
    motore, llm = FintoMotore(), FintoLLM()
    elaborazione = Elaborazione(config, archivio, llm, [motore])
    elaborazione.esegui(lezione.id)
    chiamate_iniziali = len(llm.chiamate)

    # Riprendere una lezione già completa non costa nulla
    prepara_rielaborazione(archivio, lezione.id, "riprendi")
    assert elaborazione.esegui(lezione.id).stato == "completata"
    assert len(llm.chiamate) == chiamate_iniziali and len(motore.chiamate) == 1

    # Rifare solo gli appunti non ritrascrive e non rivede la trascrizione
    prepara_rielaborazione(archivio, lezione.id, "appunti")
    assert elaborazione.esegui(lezione.id).stato == "completata"
    nuove = llm.fasi()[chiamate_iniziali:]
    assert nuove == ["appunti", "verifica", "correzione", "approfondimento"]
    assert len(motore.chiamate) == 1

    # Ricominciare da capo ritrascrive
    prepara_rielaborazione(archivio, lezione.id, "tutto")
    assert elaborazione.esegui(lezione.id).stato == "completata"
    assert len(motore.chiamate) == 2


def test_blocchi_gia_rivisti_non_vengono_ripagati(config, archivio, audio_prova, tmp_path):
    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    llm = FintoLLM()
    elaborazione = Elaborazione(config, archivio, llm, [FintoMotore()])
    elaborazione.esegui(lezione.id)
    blocchi = llm.fasi().count("revisione")
    f = File(archivio.cartella(lezione.id))
    # Simula un'interruzione durante la revisione: resta solo il primo blocco salvato
    for percorso in sorted(f.revisione.glob("blocco_*.md"))[1:]:
        percorso.unlink()
    f.trascrizione.unlink()
    for percorso in (f.bozza, f.verifica, f.appunti):
        percorso.unlink()
    llm.chiamate.clear()
    elaborazione.esegui(lezione.id)
    assert llm.fasi().count("revisione") == blocchi - 1


def test_materiali_pdf_e_immagini_diventano_blocchi(tmp_path):
    import subprocess

    from pypdf import PdfWriter

    from sbobina.materiali import carica_materiali

    cartella = tmp_path / "materiali"
    cartella.mkdir()
    scrittore = PdfWriter()
    scrittore.add_blank_page(width=200, height=200)
    with (cartella / "slide.pdf").open("wb") as f:
        scrittore.write(f)
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-f", "lavfi", "-i", "color=c=white:s=3000x2000", "-frames:v", "1",
         str(cartella / "lavagna.png")],
        check=True, capture_output=True,
    )
    (cartella / "appunti.md").write_text("Formula di Taylor", encoding="utf-8")
    materiali = carica_materiali(cartella, ["slide.pdf", "lavagna.png", "appunti.md"], tmp_path / "lavoro")
    tipi = [b["type"] for b in materiali.blocchi]
    assert tipi == ["document", "image", "text", "text"]
    assert materiali.blocchi[0]["source"]["media_type"] == "application/pdf"
    assert "Formula di Taylor" in materiali.testo
    ridotta = tmp_path / "lavoro" / "lavagna-ridotta.jpg"
    larghezza = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width", "-of", "csv=p=0",
         str(ridotta)], capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert int(larghezza) == 1600


def test_dati_lezione_salvati_come_json_leggibile(config, archivio, audio_prova, tmp_path):
    lezione = _crea(archivio, audio_prova, tmp_path)
    dati = json.loads((archivio.cartella(lezione.id) / "lezione.json").read_text())
    assert dati["corso"] == "Analisi 1" and dati["materiali"] == ["slide-lezione-3.txt"]
    assert dati["titolo"] == "Lezione 3 - Rolle"


def test_approfondimento_ed_espansioni(config, archivio, audio_prova, tmp_path):
    lezione = archivio.crea_lezione(audio=audio_prova, nome_audio="rolle.m4a", corso="Analisi", titolo="Rolle")
    llm = FintoLLM()
    Elaborazione(config, archivio, llm, [FintoMotore()]).esegui(lezione.id)
    f = File(archivio.cartella(lezione.id))
    assert f.approfondimento.read_text().startswith("# Approfondimento: Rolle")

    # Lo studente chiede di andare più a fondo: si aggiunge una sezione, il resto non si rifà.
    archivio.modifica(lezione.id, lambda lez: lez.da_approfondire.append("teorema di Lagrange"))
    chiamate_prima = len(llm.fasi())
    risultato = Elaborazione(config, archivio, llm, [FintoMotore()]).esegui(lezione.id)
    assert risultato.stato == "completata", risultato.errore
    assert llm.fasi()[chiamate_prima:] == ["espansione"]
    testo = f.approfondimento.read_text()
    assert "## Il quadro generale" in testo and "## Approfondimento: teorema di Lagrange" in testo
    assert archivio.carica(lezione.id).da_approfondire == []


def test_fermata_e_ripresa(config, archivio, audio_prova, tmp_path):
    from sbobina.llm import FERMA

    class LLMFermato(FintoLLM):
        def testo(self, **kw):
            if not self.chiamate:
                FERMA.set()  # come il pulsante "Ferma" durante la prima chiamata
            return super().testo(**kw)

    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    llm = LLMFermato()
    elaborazione = Elaborazione(config, archivio, llm, [FintoMotore()])
    fermata = elaborazione.esegui(lezione.id)
    assert fermata.stato == "fermata" and fermata.errore == ""

    prepara_rielaborazione(archivio, lezione.id, "riprendi")
    assert elaborazione.esegui(lezione.id).stato == "completata"


def test_fermata_durante_la_trascrizione(config, archivio, audio_prova, tmp_path):
    from sbobina.llm import FERMA

    class MotoreFermato(FintoMotore):
        def trascrivi(self, audio, *, avanzamento, **kw):
            FERMA.set()  # il pulsante "Ferma" mentre Whisper lavora
            avanzamento(0.5)
            return super().trascrivi(audio, avanzamento=avanzamento, **kw)

    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    risultato = Elaborazione(config, archivio, FintoLLM(), [MotoreFermato()]).esegui(lezione.id)
    assert risultato.stato == "fermata" and risultato.errore == ""


def test_blocco_in_loop_resta_trascrizione_originale(config, archivio, audio_prova, tmp_path):
    from sbobina.llm import ErroreRipetizione

    class LLMInLoop(FintoLLM):
        def testo(self, *, system, **kw):
            if isinstance(system, list):  # la revisione dei blocchi
                raise ErroreRipetizione("loop")
            return super().testo(system=system, **kw)

    lezione = _crea(archivio, audio_prova, tmp_path, materiali=False)
    risultato = Elaborazione(config, archivio, LLMInLoop(), [FintoMotore()]).esegui(lezione.id)
    assert risultato.stato == "completata"
    assert any("si ripeteva" in a for a in risultato.avvisi)


def test_fermata_mentre_era_in_coda_non_parte(config, archivio, audio_prova):
    # La coda ha già letto "in_coda", poi lo studente preme Stop: l'elaborazione non deve partire.
    lezione = archivio.crea_lezione(audio=audio_prova, nome_audio=audio_prova.name, corso="X")
    archivio.aggiorna(lezione.id, stato="fermata")
    elaborazione = Elaborazione(config, archivio, None, {})
    assert elaborazione.esegui(lezione.id).stato == "fermata"


def test_glossario_senza_perdite_tra_thread(archivio):
    import threading
    fili = [threading.Thread(target=archivio.aggiungi_al_glossario, args=("Fisica", [f"t{i}"])) for i in range(30)]
    [f.start() for f in fili]
    [f.join() for f in fili]
    assert len(archivio.carica_corso("Fisica").glossario) == 30
