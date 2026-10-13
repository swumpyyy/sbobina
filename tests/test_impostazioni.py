import json

import pytest
from fastapi.testclient import TestClient

from sbobina import impostazioni, prompt
from sbobina.config import Config
from sbobina.impostazioni import Impostazioni
from sbobina.llm import _estrai_json
from sbobina.server import crea_app

PROTETTO = {"X-Sbobina": "1"}


def test_validazione_e_chiave_mascherata(tmp_path):
    imp = Impostazioni.da_dict({"lunghezza": "dettagliata", "chiave_claude": "sk-ant-segreta1234", "sconosciuto": 1})
    assert imp.lunghezza == "dettagliata"
    assert imp.a_dict()["chiave_claude"] == "••••1234"
    # Il client rimanda la chiave mascherata: non deve sovrascrivere quella vera
    assert Impostazioni.da_dict({"chiave_claude": "••••1234"}, imp).chiave_claude == "sk-ant-segreta1234"
    with pytest.raises(ValueError, match="tema"):
        Impostazioni.da_dict({"tema": "viola"})
    with pytest.raises(ValueError):
        Impostazioni.da_dict({"temperatura": 9})
    impostazioni.salva(tmp_path, imp)
    assert impostazioni.carica(tmp_path).chiave_claude == "sk-ant-segreta1234"
    assert oct((tmp_path / "impostazioni.json").stat().st_mode)[-3:] == "600"


def test_file_rovinato_non_blocca(tmp_path):
    (tmp_path / "impostazioni.json").write_text("{non json", encoding="utf-8")
    assert impostazioni.carica(tmp_path) == Impostazioni()


def test_motore_sceglie_il_modello():
    config = Config(modello="gemma4:12b")
    assert Impostazioni(motore_llm="mlx").applica(config).modello == "mlx-community/gemma-4-12B-it-4bit"
    assert Impostazioni(motore_llm="mlx", modello="gemma4:e4b").applica(config).modello.endswith("e4b-it-4bit")
    # chi aveva scelto Ollama passa a MLX con lo stesso modello
    vecchie = Impostazioni.da_dict({"motore_llm": "ollama", "modello": "gemma4:e2b"})
    assert vecchie.motore_llm == "mlx" and vecchie.applica(config).modello == "mlx-community/gemma-4-e2b-it-4bit"
    assert Impostazioni(motore_llm="claude").applica(config).modello.startswith("claude")
    assert Impostazioni(sezioni={"verifica": False}).applica(config).verifica is False


def test_regole_seguono_le_impostazioni():
    assert prompt.regole_appunti(None) == prompt.REGOLE_APPUNTI
    imp = Impostazioni(sezioni={"mappa": False, "glossario": False, "schemi": False}, stile="schematico",
                       area="giurisprudenza", prompt_extra="Usa esempi di casi reali.")
    regole = prompt.regole_appunti(imp)
    assert "## Mappa concettuale" not in regole and "## Glossario" not in regole and "Mermaid" not in regole
    assert "## Appunti" in regole and "## Domande di ripasso" in regole
    assert "schematico" in regole and "articoli, commi" in regole and "casi reali" in regole
    assert "Mappa concettuale, Glossario" in prompt.istruzioni_verifica("bozza", imp)


def test_json_dal_modello_integrato():
    assert _estrai_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _estrai_json('Ecco il risultato: {"a": [1, 2]} spero vada bene') == {"a": [1, 2]}
    with pytest.raises(json.JSONDecodeError):
        _estrai_json("niente")


def test_api_impostazioni(config):
    with TestClient(crea_app(config, avvia_coda=False), base_url="http://localhost") as client:
        assert client.get("/api/impostazioni").json()["tema"] == "sistema"
        assert client.put("/api/impostazioni", json={"tema": "scuro"}).status_code == 403
        risposta = client.put("/api/impostazioni", headers=PROTETTO, json={"tema": "scuro", "scala_testo": 120})
        assert risposta.status_code == 200 and risposta.json()["scala_testo"] == 120
        assert client.get("/api/stato").json()["impostazioni"]["tema"] == "scuro"
        assert client.put("/api/impostazioni", headers=PROTETTO, json={"scala_testo": 300}).status_code == 400
        sistema = client.get("/api/sistema").json()
        assert sistema["modelli"] and "ram_gb" in sistema["mac"] and "economia" in sistema["aree"]


def test_temi_colore_lectio():
    assert Impostazioni.da_dict({"accento": "blu"}).accento == "cobalto"  # vecchio tema a vetro
    assert Impostazioni.da_dict({"accento": "personalizzato", "colore": "#12ab9F"}).colore == "#12ab9F"
    with pytest.raises(ValueError):
        Impostazioni.da_dict({"colore": "rosso"})


def test_estrai_json_ripara_latex_e_virgole():
    # Gli errori veri di Gemma su flashcard e quiz: \frac con una barra sola e una virgola prima della graffa.
    rotto = '{"carte": [{"fronte": "Derivata di $\\frac{1}{x}$", "retro": "$-\\frac{1}{x^2}$ e \\sum, \\alpha",},], "nota": "riga\\nnuova \\\\beta"}'
    dati = _estrai_json(rotto)
    assert dati["carte"][0]["fronte"] == "Derivata di $\\frac{1}{x}$"
    assert dati["carte"][0]["retro"] == "$-\\frac{1}{x^2}$ e \\sum, \\alpha"
    assert dati["nota"] == "riga\nnuova \\beta"  # \n vero e \\ già corretto restano com'erano
