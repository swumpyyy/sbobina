"""App nativa per macOS: finestra propria (WebKit) sopra il server locale, con Ollama avviato in automatico."""

from __future__ import annotations

import re
import socket
import threading
import time
from pathlib import Path
from urllib.parse import unquote

import httpx2

from sbobina.config import Config


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Ponte:
    """Funzioni chiamabili dalla pagina come window.pywebview.api.*"""

    def __init__(self, indirizzo: str):
        self.indirizzo = indirizzo
        self.finestra = None

    def salva(self, percorso: str, nome: str = "") -> str:
        """Scarica un file dal server locale e lo salva dove sceglie lo studente (finestra Salva di macOS)."""
        import webview

        if not percorso.startswith("/api/"):  # solo risorse del server locale
            return "Percorso non valido."
        risposta = httpx2.get(self.indirizzo + percorso, timeout=None)
        if risposta.status_code != 200:
            try:
                return risposta.json().get("detail") or f"Errore {risposta.status_code}"
            except ValueError:
                return f"Errore {risposta.status_code}"
        if not nome:
            intestazione = risposta.headers.get("content-disposition", "")
            trovato = re.search(r"filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)", intestazione)
            nome = unquote(trovato.group(1) or trovato.group(2)) if trovato else "sbobina"
        nome = nome.replace("/", "-")
        scelta = self.finestra.create_file_dialog(
            webview.FileDialog.SAVE, directory=str(Path.home() / "Downloads"), save_filename=nome
        )
        if not scelta:
            return ""
        destinazione = Path(scelta if isinstance(scelta, str) else scelta[0])
        destinazione.write_bytes(risposta.content)
        return str(destinazione)

    def badge(self, testo: str = "") -> None:
        """Il numero sull'icona nel Dock (lezioni in elaborazione); vuoto per toglierlo."""
        try:
            from AppKit import NSApplication
            from PyObjCTools import AppHelper
        except ImportError:
            return
        AppHelper.callAfter(lambda: NSApplication.sharedApplication().dockTile().setBadgeLabel_(str(testo) or None))

    def notifica(self, titolo: str, testo: str) -> None:
        """Notifica di macOS a fine lezione. Nel bundle usa UserNotifications, altrimenti osascript."""
        import subprocess

        try:
            from UserNotifications import (
                UNMutableNotificationContent,
                UNNotificationRequest,
                UNUserNotificationCenter,
            )

            centro = UNUserNotificationCenter.currentNotificationCenter()
            centro.requestAuthorizationWithOptions_completionHandler_(0b111, lambda *_: None)
            contenuto = UNMutableNotificationContent.alloc().init()
            contenuto.setTitle_(titolo)
            contenuto.setBody_(testo)
            richiesta = UNNotificationRequest.requestWithIdentifier_content_trigger_(str(time.time()), contenuto, None)
            centro.addNotificationRequest_withCompletionHandler_(richiesta, None)
        except Exception:  # noqa: BLE001 - fuori dal bundle .app UserNotifications non funziona
            pulisci = lambda s: s.replace("\\", "").replace('"', "'")  # noqa: E731
            subprocess.run(
                ["osascript", "-e", f'display notification "{pulisci(testo)}" with title "{pulisci(titolo)}"'],
                check=False, capture_output=True,
            )

    def tema(self, scuro: bool) -> None:
        """La barra del titolo segue il tema scelto nell'app."""
        _barra_titolo(self.finestra, scuro)


def _identita_macos() -> None:
    """Nome e icona nel Dock: il processo è Python, quindi senza questo il Dock mostrerebbe "Python"."""
    import os
    import sys

    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSBundle
    except ImportError:
        return
    info = NSBundle.mainBundle().infoDictionary()
    if info is not None:
        info["CFBundleName"] = "Sbobina"
    icona = os.environ.get("SBOBINA_ICONA")
    if icona and Path(icona).exists():
        NSApplication.sharedApplication().setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(icona))


def main() -> None:
    import uvicorn
    import webview

    from sbobina import impostazioni
    from sbobina.llm import avvia_ollama
    from sbobina.server import crea_app

    config = Config.da_ambiente()
    effettiva = impostazioni.carica(config.cartella_dati).applica(config)
    if effettiva.locale and "/" not in effettiva.modello:  # Ollama parte con l'app (con MLX non serve)
        threading.Thread(target=avvia_ollama, daemon=True).start()

    porta = _porta_libera()
    indirizzo = f"http://127.0.0.1:{porta}"
    server = uvicorn.Server(uvicorn.Config(crea_app(config), host="127.0.0.1", port=porta, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)

    _identita_macos()
    ponte = Ponte(indirizzo)
    ponte.finestra = webview.create_window(
        "Sbobina", indirizzo, js_api=ponte, width=1280, height=840, min_size=(900, 620), background_color="#edf2fa"
    )
    ponte.finestra.events.shown += lambda: _barra_titolo(ponte.finestra, None)
    webview.start()
    server.should_exit = True


def _barra_titolo(finestra, scuro: bool | None) -> None:
    """Barra del titolo trasparente sul cielo dell'app; None = segue il sistema."""
    try:
        from AppKit import NSAppearance, NSColor
        from PyObjCTools import AppHelper
    except ImportError:
        return

    def applica() -> None:
        nativa = finestra.native
        if scuro is None:
            nativa.setAppearance_(None)
            from AppKit import NSApplication

            nome = NSApplication.sharedApplication().effectiveAppearance().name() or ""
            buio = "Dark" in nome
        else:
            buio = scuro
            nativa.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua" if buio else "NSAppearanceNameAqua"))
        nativa.setTitlebarAppearsTransparent_(True)
        r, g, b = (0x06, 0x0C, 0x19) if buio else (0xED, 0xF2, 0xFA)
        nativa.setBackgroundColor_(NSColor.colorWithSRGBRed_green_blue_alpha_(r / 255, g / 255, b / 255, 1.0))

    AppHelper.callAfter(applica)


if __name__ == "__main__":
    main()
