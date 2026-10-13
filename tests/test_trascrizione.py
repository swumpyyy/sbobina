import pytest

from sbobina.archivio import dividi_termini, slug, unisci_termini
from sbobina.config import scegli_motori
from sbobina.trascrizione.base import (
    Parola,
    Trascrizione,
    estrai_testo,
    filtra_termini,
    in_blocchi,
    in_righe,
    tempo,
)
from sbobina.trascrizione import whisper_locale
from sbobina.trascrizione.whisper_locale import parole_suggerite, prompt_iniziale

from conftest import parole_finte


def test_tempo():
    assert tempo(0) == "00:00"
    assert tempo(754.9) == "12:34"
    assert tempo(3723) == "1:02:03"


def test_righe_si_chiudono_a_fine_frase_e_sulle_pause():
    parole = [
        Parola(0.0, 0.3, "Oggi"), Parola(0.4, 0.6, "vediamo"), Parola(0.7, 0.9, "il"), Parola(1.0, 1.2, "teorema"),
        Parola(1.3, 1.5, "di"), Parola(1.6, 1.8, "Rolle"), Parola(1.9, 2.0, "e"), Parola(2.1, 2.3, "poi"),
        Parola(2.4, 2.6, "Lagrange."), Parola(2.7, 2.9, "Partiamo"), Parola(5.0, 5.2, "dunque."),
    ]
    righe = in_righe(parole, min_parole=8, pausa=1.5)
    assert [r.testo for r in righe] == [
        "Oggi vediamo il teorema di Rolle e poi Lagrange.",
        "Partiamo",
        "dunque.",
    ]
    assert righe[1].inizio == 2.7 and righe[2].inizio == 5.0


def test_righe_con_limite_di_parole():
    righe = in_righe([Parola(i * 0.1, i * 0.1 + 0.05, "x") for i in range(100)], max_parole=45)
    assert [len(r.testo.split()) for r in righe] == [45, 45, 10]


def test_blocchi_coprono_tutto_senza_buchi():
    righe = in_righe(parole_finte(200, passo=3.0))  # 10 minuti
    blocchi = in_blocchi(righe, secondi=120)
    assert sum(len(b.righe) for b in blocchi) == len(righe)
    for prima, dopo in zip(blocchi, blocchi[1:]):
        assert prima.fine == dopo.inizio
    assert blocchi[-1].fine is None
    assert all(r.inizio < 600 for r in blocchi[-1].righe)


def test_ultimo_blocco_corto_viene_unito():
    righe = in_righe(parole_finte(43, passo=3.0))  # ~126 s: l'ultimo pezzo dura pochi secondi
    blocchi = in_blocchi(righe, secondi=60)
    assert len(blocchi) == 2
    assert blocchi[-1].fine is None


def test_testo_tra_usa_inizio_parola():
    parole = [Parola(0.0, 0.5, "a"), Parola(9.9, 10.2, "b"), Parola(10.0, 10.5, "c"), Parola(20, 21, "d")]
    assert estrai_testo(parole, 0, 10) == "a b"
    assert estrai_testo(parole, 10, None) == "c d"


def test_blocco_testo_con_marcatori():
    blocchi = in_blocchi(in_righe(parole_finte(20)), secondi=600)
    assert blocchi[0].testo.splitlines()[0].startswith("[00:00] parola0")
    assert blocchi[0].numero_parole == 20


def test_filtra_termini_rispetta_i_limiti():
    termini = ["Rolle", "rolle", "teorema del valor medio di Lagrange", "x" * 60, "a<b>", "", "De Moivre"]
    assert filtra_termini(termini, massimo=10, max_parole=5, max_caratteri=49, caratteri_vietati="<>") == [
        "Rolle", "a b", "De Moivre",
    ]
    assert filtra_termini(["a", "b", "c"], massimo=2, max_parole=5, max_caratteri=10) == ["a", "b"]


def test_trascrizione_andata_e_ritorno():
    t = Trascrizione("finto", [Parola(1.234, 2.345, "ciao", 0.98765)], 10.0)
    copia = Trascrizione.da_dict(t.a_dict())
    assert copia.motore == "finto" and copia.durata == 10.0
    assert copia.parole[0].testo == "ciao" and copia.parole[0].inizio == 1.23


def test_campioni_per_whisper_decodificati_con_ffmpeg(audio_prova):
    pytest.importorskip("numpy")
    from sbobina.trascrizione.whisper_locale import campioni_16k

    campioni = campioni_16k(audio_prova)
    assert str(campioni.dtype) == "float32"
    assert abs(len(campioni) - 20 * 16000) < 16000  # 20 secondi a 16 kHz


def test_prompt_whisper_limitati():
    termini = [f"termine{i}" for i in range(200)]
    assert len(prompt_iniziale("Lezione di Analisi.", termini)) <= 600
    suggerite = parole_suggerite(termini)
    assert len(suggerite) <= 300 and suggerite.startswith("termine0, termine1")


def test_scelta_motori():
    assert scegli_motori("auto", {}) == ("whisper",)
    assert scegli_motori("auto", {"ASSEMBLYAI_API_KEY": "k", "ELEVENLABS_API_KEY": "k"}) == ("assemblyai", "elevenlabs")
    assert scegli_motori("elevenlabs, whisper", {}) == ("elevenlabs", "whisper")


def test_termini_e_slug():
    assert unisci_termini(["Rolle", " rolle "], ["Lagrange", "Rolle."]) == ["Rolle", "Lagrange"]
    assert dividi_termini("Rolle, Lagrange\nDe Moivre; ") == ["Rolle", "Lagrange", "De Moivre"]
    assert slug("Lezione 3 – Teorema di Rolle!") == "lezione-3-teorema-di-rolle"


def test_repo_mlx_usa_cartella_locale_solo_se_completa(tmp_path, monkeypatch):
    monkeypatch.setattr(whisper_locale, "MODELLI_LOCALI", tmp_path)
    assert whisper_locale.repo_mlx("large-v3-turbo") == "mlx-community/whisper-large-v3-turbo"
    cartella = tmp_path / "whisper-large-v3-turbo"
    cartella.mkdir()
    (cartella / "config.json").write_text("{}")
    assert whisper_locale.repo_mlx("large-v3-turbo") == "mlx-community/whisper-large-v3-turbo"  # pesi mancanti
    (cartella / "weights.safetensors").write_bytes(b"")
    assert whisper_locale.repo_mlx("large-v3-turbo") == str(cartella)


def test_modello_pronto_ripiega_su_un_modello_gia_scaricato(tmp_path, monkeypatch):
    monkeypatch.setattr(whisper_locale, "MODELLI_LOCALI", tmp_path)
    assert whisper_locale.modello_pronto("large-v3") == "mlx-community/whisper-large-v3-mlx"  # niente sul disco
    cartella = tmp_path / "whisper-large-v3-turbo"
    cartella.mkdir()
    (cartella / "config.json").write_text("{}")
    (cartella / "weights.safetensors").write_bytes(b"")
    assert whisper_locale.modello_pronto("large-v3") == str(cartella)  # niente download a metà trascrizione


def test_microfono_windows_prende_il_primo_dispositivo_audio(monkeypatch):
    from types import SimpleNamespace

    from sbobina import registrazione

    uscita = ('[dshow @ 0x1] "Integrated Camera" (video)\n'
              '[dshow @ 0x1]   Alternative name "@device_pnp_..."\n'
              '[dshow @ 0x1] "Microfono (Realtek(R) Audio)" (audio)\n')
    monkeypatch.setattr(registrazione.subprocess, "run", lambda *a, **k: SimpleNamespace(stderr=uscita))
    assert registrazione.microfono_windows() == "Microfono (Realtek(R) Audio)"
