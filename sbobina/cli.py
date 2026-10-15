"""Riga di comando: `sbobina server` per l'app web, `sbobina elabora` per elaborare file in blocco."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path

from sbobina.archivio import ESTENSIONI_AUDIO, Archivio, dividi_termini
from sbobina.config import Config


def _elaborazione(config: Config, archivio: Archivio):
    from sbobina.llm import crea_modello
    from sbobina.pipeline import Elaborazione
    from sbobina.trascrizione import crea_motori

    return Elaborazione(config, archivio, crea_modello(config.modello, lingua=config.lingua), crea_motori(config))


def _file_audio(percorsi: list[Path]) -> list[Path]:
    trovati: list[Path] = []
    for percorso in percorsi:
        if percorso.is_dir():
            trovati += sorted(p for p in percorso.iterdir() if p.suffix.lower() in ESTENSIONI_AUDIO)
        elif percorso.is_file():
            trovati.append(percorso)
        else:
            raise SystemExit(f"File o cartella non trovati: {percorso}")
    if not trovati:
        raise SystemExit("Nessun file audio trovato.")
    return trovati


def _esegui_con_avanzamento(elaborazione, archivio: Archivio, id_lezione: str):
    """Esegue l'elaborazione mostrando l'avanzamento sul terminale."""
    finito = threading.Event()

    def mostra() -> None:
        ultimo = ""
        while not finito.wait(2.0):
            lezione = archivio.carica(id_lezione)
            riga = f"  {round(lezione.progresso * 100):3d}%  {lezione.fase}  {lezione.messaggio}".rstrip()
            if riga != ultimo:
                print(riga, flush=True)
                ultimo = riga

    thread = threading.Thread(target=mostra, daemon=True)
    thread.start()
    try:
        return elaborazione.esegui(id_lezione)
    finally:
        finito.set()
        thread.join()


def _comando_elabora(args: argparse.Namespace, config: Config) -> int:
    archivio = Archivio(config.cartella_dati)
    audio = _file_audio(args.percorsi)
    for materiale in args.materiali:
        if not materiale.is_file():
            raise SystemExit(f"Materiale non trovato: {materiale}")
    if args.termini:
        archivio.aggiungi_al_glossario(args.corso, dividi_termini(args.termini))
    elaborazione = _elaborazione(config, archivio)
    falliti = 0
    for i, percorso in enumerate(audio, 1):
        lezione = archivio.crea_lezione(
            audio=percorso,
            nome_audio=percorso.name,
            corso=args.corso,
            titolo=args.titolo if len(audio) == 1 else "",
            data_lezione=args.data,
            note=args.note,
            materiali=[(m.name, m) for m in args.materiali],
        )
        print(f"[{i}/{len(audio)}] {lezione.titolo} ({lezione.id})", flush=True)
        lezione = _esegui_con_avanzamento(elaborazione, archivio, lezione.id)
        cartella = archivio.cartella(lezione.id)
        if lezione.stato == "completata":
            print(f"  Fatto. Appunti: {cartella / 'appunti.md'}")
            print(f"         Da stampare: {cartella / 'appunti.html'}")
        else:
            falliti += 1
            print(f"  Errore: {lezione.errore}", file=sys.stderr)
        for avviso in lezione.avvisi:
            print(f"  Attenzione: {avviso}")
    return 1 if falliti else 0


def _comando_rielabora(args: argparse.Namespace, config: Config) -> int:
    from sbobina.pipeline import prepara_rielaborazione

    archivio = Archivio(config.cartella_dati)
    try:
        prepara_rielaborazione(archivio, args.id, args.da)
    except KeyError:
        raise SystemExit(f"Lezione non trovata: {args.id}") from None
    lezione = _esegui_con_avanzamento(_elaborazione(config, archivio), archivio, args.id)
    if lezione.stato != "completata":
        print(f"Errore: {lezione.errore}", file=sys.stderr)
        return 1
    print(f"Fatto: {archivio.cartella(args.id) / 'appunti.md'}")
    return 0


def _comando_elenco(config: Config) -> int:
    lezioni = Archivio(config.cartella_dati).elenco()
    if not lezioni:
        print("Nessuna lezione.")
    for lez in lezioni:
        print(f"{lez.data}  {lez.stato:<15} {lez.corso} · {lez.titolo}  [{lez.id}]")
    return 0


def _comando_stato(config: Config) -> int:
    from sbobina.audio import ffmpeg_disponibile

    print(f"Cartella dati:  {config.cartella_dati.resolve()}")
    print(f"Modello AI:     {config.modello} ({'locale, gratuito' if config.locale else 'Claude, a pagamento'})")
    if config.locale:
        pronto = "pronto" if config.llm_pronto else "NON PRONTO: apri l'app e premi «Prepara l'AI» per scaricare il modello"
    else:
        pronto = "chiave presente" if config.llm_pronto else "NON TROVATA (ANTHROPIC_API_KEY)"
    print(f"Stato AI:       {pronto}")
    print(f"Trascrizione:   {' + '.join(config.motori)}")
    print(f"ffmpeg:         {'ok' if ffmpeg_disponibile() else 'NON INSTALLATO'}")
    print(f"Verifica:       {'attiva' if config.verifica else 'disattivata'}")
    return 0


def _comando_server(args: argparse.Namespace, config: Config) -> int:
    import uvicorn

    from sbobina.server import crea_app

    indirizzo = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    print(f"Sbobina è in esecuzione su {indirizzo}  (Ctrl+C per fermare)")
    if not args.non_aprire:
        import webbrowser

        threading.Timer(1.5, lambda: webbrowser.open(indirizzo)).start()
    locale = args.host in ("127.0.0.1", "localhost")
    # --host diverso = l'utente ha scelto di esporre l'app in rete: ogni Host è accettato.
    uvicorn.run(crea_app(config, host_ammessi=("127.0.0.1", "localhost") if locale else ("*",)), host=args.host, port=args.port, log_level="warning")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="sbobina", description="Trasforma le registrazioni delle lezioni in appunti e schemi accurati."
    )
    comandi = parser.add_subparsers(dest="comando", required=True)

    server = comandi.add_parser("server", help="avvia l'app web")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8000)
    server.add_argument("--non-aprire", action="store_true", help="non aprire il browser")

    elabora = comandi.add_parser("elabora", help="elabora una o più registrazioni (file o cartelle)")
    elabora.add_argument("percorsi", nargs="+", type=Path, help="file audio o cartelle che li contengono")
    elabora.add_argument("--corso", required=True, help="nome del corso (raggruppa le lezioni e il glossario)")
    elabora.add_argument("--materiali", nargs="*", type=Path, default=[], help="slide/dispense PDF, immagini, testi")
    elabora.add_argument("--titolo", default="", help="titolo (solo con un singolo file)")
    elabora.add_argument("--data", default="", help="data della lezione, AAAA-MM-GG")
    elabora.add_argument("--note", default="", help="indicazioni per gli appunti")
    elabora.add_argument("--termini", default="", help="nomi e termini difficili, separati da virgola")

    rielabora = comandi.add_parser("rielabora", help="rielabora una lezione esistente")
    rielabora.add_argument("id")
    rielabora.add_argument(
        "--da", default="appunti", choices=("riprendi", "appunti", "revisione", "tutto"), help="da quale fase ripartire"
    )

    comandi.add_parser("elenco", help="elenca le lezioni")
    comandi.add_parser("stato", help="mostra la configurazione")
    comandi.add_parser("app", help="apre Sbobina come app nativa (finestra propria)")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        config = Config.da_ambiente()
    except ValueError as e:
        raise SystemExit(f"Configurazione non valida: {e}") from None

    if args.comando == "app":
        from sbobina.app import main as app

        app()
        codice = 0
    elif args.comando == "server":
        codice = _comando_server(args, config)
    elif args.comando == "elabora":
        codice = _comando_elabora(args, config)
    elif args.comando == "rielabora":
        codice = _comando_rielabora(args, config)
    elif args.comando == "elenco":
        codice = _comando_elenco(config)
    else:
        codice = _comando_stato(config)
    sys.exit(codice)


if __name__ == "__main__":
    main()
