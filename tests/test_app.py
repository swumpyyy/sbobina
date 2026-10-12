from sbobina.app import Ponte


def test_salva_accetta_solo_risorse_del_server_locale():
    ponte = Ponte("http://127.0.0.1:1")
    assert ponte.salva("https://esempio.it/file") == "Percorso non valido."
    assert ponte.salva("../../etc/passwd") == "Percorso non valido."
