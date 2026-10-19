"""App nativa per macOS e Windows: finestra propria (WebKit / WebView2) sopra il server locale; i modelli girano dentro Sbobina."""

from __future__ import annotations

import re
import socket
import sys
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
        # Attributi con "_": pywebview espone alla pagina tutto ciò che è pubblico e su Windows
        # esplorerebbe la finestra .NET all'infinito (RecursionError, e window.pywebview.api non nasce).
        self._finestra = None
        self._registratore = None  # la finestrella del widget di registrazione
        self._barra = None  # l'icona nella barra dei menu (macOS) o nell'area di notifica (Windows)

    # --- widget di registrazione -------------------------------------------

    def widget(self) -> None:
        """Apre (o rimette davanti) il registratore piccolo, sempre in primo piano."""
        import webview

        if self._registratore is not None:
            self._registratore.show()
            return
        larghezza, altezza = 380, 78
        schermo = webview.screens[0] if webview.screens else None
        x = (schermo.width - larghezza - 24) if schermo else None
        self._registratore = webview.create_window(
            "Registratore", self.indirizzo + "/static/widget.html", js_api=self,
            width=larghezza, height=altezza, x=x, y=48 if schermo else None,
            resizable=False, frameless=True, on_top=True, transparent=True, focus=False,
        )
        self._registratore.events.closed += self._widget_chiuso
        self._barra = BarraMenu.crea(self) or AreaNotifica.crea(self)

    def riduci_widget(self) -> None:
        """Nasconde il widget: resta l'icona nella barra dei menu (macOS) o nell'area di notifica (Windows)."""
        if self._registratore is None:
            return
        if self._barra is not None:
            self._registratore.hide()
        else:
            self._registratore.minimize()

    def chiudi_widget(self) -> None:
        if self._registratore is not None:
            self._registratore.destroy()

    def _widget_chiuso(self) -> None:
        self._registratore = None
        if self._barra is not None:
            self._barra.togli()
            self._barra = None

    def comando_registrazione(self, azione: str) -> None:
        """Pausa, riprendi o ferma (salva soltanto), dalla barra dei menu."""
        corpo = {"elabora": False} if azione == "ferma" else {}
        try:
            httpx2.post(f"{self.indirizzo}/api/registrazione/{azione}", json=corpo, headers={"X-Sbobina": "1"}, timeout=60)
        except httpx2.HTTPError:
            pass  # il widget mostra l'errore al prossimo aggiornamento
        if azione == "ferma":
            self.lezione_salvata()

    def lezione_salvata(self) -> None:
        """La finestra principale ridisegna l'elenco: la lezione «da elaborare» compare subito."""
        if self._finestra is not None:
            self._finestra.evaluate_js("window.sbobinaAggiornaElenco && window.sbobinaAggiornaElenco()")

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
        scelta = self._finestra.create_file_dialog(
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
            # shortcut: su Windows il numero va nel titolo, non sull'icona della barra (servirebbe ITaskbarList3 via COM)
            if self._finestra is not None:
                self._finestra.set_title(f"({testo}) Sbobina" if testo else "Sbobina")
            return
        AppHelper.callAfter(lambda: NSApplication.sharedApplication().dockTile().setBadgeLabel_(str(testo) or None))

    def notifica(self, titolo: str, testo: str) -> None:
        """Notifica di sistema a fine lezione: osascript su macOS, un toast via PowerShell su Windows.

        Niente UserNotifications: il processo è python3, non il bundle, e currentNotificationCenter()
        fallisce con un'asserzione Objective-C che chiude l'app (non è catturabile da Python).
        """
        import os
        import subprocess

        if os.name == "nt":
            # Testi passati come variabili d'ambiente: niente da "escapare" nello script.
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]>$null;"
                "$x=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(5);"  # ToastText02: titolo + testo
                "$t=$x.GetElementsByTagName('text');"
                "$t[0].AppendChild($x.CreateTextNode($env:SB_TITOLO))>$null;$t[1].AppendChild($x.CreateTextNode($env:SB_TESTO))>$null;"
                # AUMID di PowerShell: un'app non registrata non può mostrare toast.
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
                "'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe')"
                ".Show([Windows.UI.Notifications.ToastNotification]::new($x))"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                env={**os.environ, "SB_TITOLO": titolo, "SB_TESTO": testo},
                check=False, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return

        pulisci = lambda s: s.replace("\\", "").replace('"', "'")  # noqa: E731
        subprocess.run(
            ["osascript", "-e", f'display notification "{pulisci(testo)}" with title "{pulisci(titolo)}"'],
            check=False, capture_output=True,
        )

    def tema(self, scuro: bool, sfondo: str = "") -> None:
        """La barra del titolo segue il tema scelto nell'app; `sfondo` è il colore della pagina ("rgb(r, g, b)")."""
        numeri = [int(n) for n in re.findall(r"\d+", sfondo)[:3]]
        _barra_titolo(self._finestra, scuro, tuple(numeri) if len(numeri) == 3 else None)


class BarraMenu:
    """L'icona del registratore nella barra dei menu di macOS, accanto all'orologio: tempo e comandi."""

    _bersaglio_classe = None

    @classmethod
    def crea(cls, ponte: Ponte) -> BarraMenu | None:
        try:
            from AppKit import NSMenu, NSMenuItem, NSStatusBar, NSVariableStatusItemLength
            from Foundation import NSObject
            from PyObjCTools import AppHelper
        except ImportError:
            return None
        if cls._bersaglio_classe is None:
            # Una classe Objective-C si registra una volta sola per processo.
            class SbobinaBarraBersaglio(NSObject):
                def mostra_(self, _):
                    self.ponte.widget()

                def pausa_(self, _):
                    threading.Thread(target=self.ponte.comando_registrazione, args=(self.azione_pausa,), daemon=True).start()

                def ferma_(self, _):
                    threading.Thread(target=self.ponte.comando_registrazione, args=("ferma",), daemon=True).start()

                def chiudi_(self, _):
                    self.ponte.chiudi_widget()

            cls._bersaglio_classe = SbobinaBarraBersaglio
        barra = cls()
        barra.attiva = True

        def costruisci() -> None:
            bersaglio = cls._bersaglio_classe.alloc().init()
            bersaglio.ponte, bersaglio.azione_pausa = ponte, "pausa"
            voce = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
            voce.button().setTitle_("Sbobina")
            menu = NSMenu.alloc().init()
            menu.setAutoenablesItems_(False)
            voci = {}
            for chiave, titolo, azione in (("mostra", "Mostra il registratore", "mostra:"), ("pausa", "Pausa", "pausa:"),
                                           ("ferma", "Ferma e salva", "ferma:"), ("chiudi", "Chiudi il registratore", "chiudi:")):
                v = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(titolo, azione, "")
                v.setTarget_(bersaglio)
                menu.addItem_(v)
                voci[chiave] = v
            voce.setMenu_(menu)
            barra.voce, barra.voci, barra.bersaglio = voce, voci, bersaglio

        AppHelper.callAfter(costruisci)
        threading.Thread(target=barra._aggiorna, args=(ponte.indirizzo,), daemon=True).start()
        return barra

    def _aggiorna(self, indirizzo: str) -> None:
        from PyObjCTools import AppHelper

        while self.attiva:
            try:
                s = httpx2.get(f"{indirizzo}/api/registrazione", timeout=5).json()
            except (httpx2.HTTPError, ValueError):
                s = {"attiva": False}
            AppHelper.callAfter(self._mostra, s)
            time.sleep(1)

    def _mostra(self, s: dict) -> None:
        if not self.attiva or not hasattr(self, "voce"):
            return
        secondi = int(s.get("secondi") or 0)
        tempo = f"{secondi // 3600}:{secondi // 60 % 60:02d}:{secondi % 60:02d}" if secondi >= 3600 else f"{secondi // 60}:{secondi % 60:02d}"
        attiva, pausa = s.get("attiva"), s.get("pausa")
        self.voce.button().setTitle_(f"{'⏸' if pausa else '●'} {tempo}" if attiva else "Sbobina")
        self.bersaglio.azione_pausa = "riprendi" if pausa else "pausa"
        self.voci["pausa"].setTitle_("Riprendi" if pausa else "Pausa")
        self.voci["pausa"].setEnabled_(bool(attiva))
        self.voci["ferma"].setEnabled_(bool(attiva))
        self.voci["chiudi"].setEnabled_(not attiva)  # chiudere non deve mai buttare una registrazione

    def togli(self) -> None:
        from AppKit import NSStatusBar
        from PyObjCTools import AppHelper

        self.attiva = False
        if hasattr(self, "voce"):
            AppHelper.callAfter(lambda: NSStatusBar.systemStatusBar().removeStatusItem_(self.voce))


class AreaNotifica:
    """Su Windows il registratore sta nell'area di notifica, accanto all'orologio: tempo nel suggerimento e gli stessi comandi del Mac."""

    @classmethod
    def crea(cls, ponte: Ponte) -> AreaNotifica | None:
        if sys.platform != "win32":
            return None
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return None
        barra = cls()
        barra.attiva, barra.stato = True, {}
        attiva = lambda _: bool(barra.stato.get("attiva"))  # noqa: E731
        in_pausa = lambda: bool(barra.stato.get("pausa"))  # noqa: E731

        def comando(azione) -> None:
            threading.Thread(target=ponte.comando_registrazione, args=(azione,), daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem("Mostra il registratore", lambda: ponte.widget(), default=True),  # anche il clic sull'icona
            pystray.MenuItem(lambda _: "Riprendi" if in_pausa() else "Pausa",
                             lambda: comando("riprendi" if in_pausa() else "pausa"), enabled=attiva),
            pystray.MenuItem("Ferma e salva", lambda: comando("ferma"), enabled=attiva),
            # chiudere non deve mai buttare una registrazione
            pystray.MenuItem("Chiudi il registratore", lambda: ponte.chiudi_widget(), enabled=lambda _: not attiva(None)),
        )
        barra.icona = pystray.Icon("Sbobina", Image.open(ICONA), "Sbobina", menu)
        barra.icona.run_detached()
        threading.Thread(target=barra._aggiorna, args=(ponte.indirizzo,), daemon=True).start()
        return barra

    def _aggiorna(self, indirizzo: str) -> None:
        while self.attiva:
            try:
                self.stato = httpx2.get(f"{indirizzo}/api/registrazione", timeout=5).json()
            except (httpx2.HTTPError, ValueError):
                self.stato = {"attiva": False}
            secondi = int(self.stato.get("secondi") or 0)
            tempo = f"{secondi // 3600}:{secondi // 60 % 60:02d}:{secondi % 60:02d}" if secondi >= 3600 else f"{secondi // 60}:{secondi % 60:02d}"
            if self.attiva:
                self.icona.title = f"Sbobina · {'in pausa' if self.stato.get('pausa') else 'registra'} {tempo}" if self.stato.get("attiva") else "Sbobina"
                self.icona.update_menu()
            time.sleep(1)

    def togli(self) -> None:
        self.attiva = False
        self.icona.stop()


ICONA = Path(__file__).parent / "static" / "sbobina.ico"


def _identita_windows() -> None:
    """Sulla barra delle applicazioni Sbobina ha la sua icona e non si raggruppa con Python."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Sbobina.Sbobina")


def _identita_macos() -> None:
    """Nome e icona nel Dock: il processo è Python, quindi senza questo il Dock mostrerebbe "Python"."""
    import os

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

    from sbobina.server import crea_app

    config = Config.da_ambiente()
    porta = _porta_libera()
    indirizzo = f"http://127.0.0.1:{porta}"
    server = uvicorn.Server(uvicorn.Config(crea_app(config), host="127.0.0.1", port=porta, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)

    _identita_macos()
    _identita_windows()
    ponte = Ponte(indirizzo)
    ponte._finestra = webview.create_window(
        "Sbobina", indirizzo, js_api=ponte, width=1280, height=840, min_size=(900, 620), background_color="#edf2fa"
    )
    ponte._finestra.events.shown += lambda: _barra_titolo(ponte._finestra, None)
    webview.start(icon=str(ICONA))  # l'icona conta solo su Windows; sul Mac la mette _identita_macos
    try:
        # Una registrazione in corso si chiude per bene (il pezzo resta in dati/registrazioni):
        # senza, ffmpeg sopravvive all'app e tiene il microfono acceso.
        httpx2.post(f"{indirizzo}/api/registrazione/pausa", headers={"X-Sbobina": "1"}, timeout=20)
    except httpx2.HTTPError:
        pass
    server.should_exit = True
    from sbobina.llm import ferma_download, ferma_llama

    ferma_download()  # i download riprendono dai file a metà al prossimo avvio
    ferma_llama()  # os._exit non chiude i processi figli: llama-server terrebbe occupata la scheda video
    # Senza questo Python attende i thread di trascrizione (non daemon) e l'app resta con la rotella.
    # La lezione resta "in elaborazione" e riparte da sola al prossimo avvio.
    import os

    os._exit(0)


def _barra_titolo(finestra, scuro: bool | None, colore: tuple[int, int, int] | None = None) -> None:
    """Barra del titolo del colore dello sfondo dell'app; None = segue il sistema."""
    if sys.platform == "win32":
        _barra_titolo_windows(finestra, scuro, colore)
        return
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
        r, g, b = colore or ((0x14, 0x14, 0x14) if buio else (0xFE, 0xFE, 0xFE))  # --campo del tema Lectio
        nativa.setBackgroundColor_(NSColor.colorWithSRGBRed_green_blue_alpha_(r / 255, g / 255, b / 255, 1.0))

    AppHelper.callAfter(applica)


def _barra_titolo_windows(finestra, scuro: bool | None, colore: tuple[int, int, int] | None) -> None:
    """DWM: testo e pulsanti chiari o scuri, e (Windows 11) la barra dello stesso colore dello sfondo."""
    import ctypes
    import winreg

    if scuro is None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as chiave:
                scuro = winreg.QueryValueEx(chiave, "AppsUseLightTheme")[0] == 0
        except OSError:
            scuro = False
    r, g, b = colore or ((0x14, 0x14, 0x14) if scuro else (0xFE, 0xFE, 0xFE))
    try:
        hwnd = ctypes.c_void_p(finestra.native.Handle.ToInt64())
    except AttributeError:
        return  # finestra non ancora creata
    dwm = ctypes.windll.dwmapi
    for attributo, valore in ((20, int(bool(scuro))), (35, r | g << 8 | b << 16)):  # DARK_MODE, CAPTION_COLOR (0x00BBGGRR)
        v = ctypes.c_int(valore)
        dwm.DwmSetWindowAttribute(hwnd, attributo, ctypes.byref(v), ctypes.sizeof(v))  # su Windows 10 il colore è ignorato


if __name__ == "__main__":
    main()
