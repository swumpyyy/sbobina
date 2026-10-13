"""Esportazione degli appunti in una pagina HTML autonoma (apribile offline e stampabile in PDF)."""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

STATIC = Path(__file__).parent / "static"

# Librerie per il rendering, incluse nel progetto (static/vendor): gli appunti si vedono anche offline.
# marked 15.0.12, DOMPurify 3.4.15, KaTeX 0.16.47, Mermaid 11.17.2 (licenze in static/vendor/LICENZE.txt).


def librerie(base: str = "/static") -> str:
    """Tag delle librerie; `base` è "/static" per le pagine servite dall'app, un URI file:// per il PDF."""
    v = f"{base}/vendor"
    return (
        f'<link rel="stylesheet" href="{v}/katex/katex.min.css">\n'
        f'<script src="{v}/marked.min.js"></script>\n'
        f'<script src="{v}/purify.min.js"></script>\n'
        f'<script src="{v}/katex/katex.min.js"></script>\n'
        f'<script src="{v}/mermaid.min.js"></script>'
    )


LIBRERIE = librerie()


def _json_in_script(valore) -> str:
    """JSON sicuro da inserire dentro <script> (niente chiusura prematura del tag)."""
    return json.dumps(valore, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")


def esporta_html(*, titolo: str, corso: str, data: str, appunti: str) -> str:
    css = (STATIC / "appunti.css").read_text(encoding="utf-8")
    render_js = (STATIC / "render.js").read_text(encoding="utf-8")
    return (
        "<!doctype html>\n<html lang=\"it\" data-tema=\"chiaro\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(titolo)} · {html.escape(corso)}</title>\n"
        f"{LIBRERIE}\n<style>\n{css}\n"
        ".pagina{max-width:860px;margin:32px auto;padding:40px clamp(20px,5vw,56px) 56px;background:var(--superficie);"
        "border-radius:28px;box-shadow:10px 12px 28px rgb(163 174 194/.55),-8px -8px 22px #fff}"
        ".meta{color:var(--testo-tenue);font-size:.9rem;margin-bottom:8px;display:flex;gap:12px;"
        "flex-wrap:wrap;align-items:center;justify-content:space-between}"
        ".meta button{font:inherit;font-weight:600;min-height:44px;padding:0 20px;border-radius:999px;"
        "border:1px solid rgb(255 255 255/.6);background:var(--sfondo);color:var(--testo);cursor:pointer;"
        "box-shadow:4px 4px 10px #b5bfd0,-4px -4px 10px #fff}"
        ".meta button:active{box-shadow:inset 2px 2px 5px #b5bfd0,inset -2px -2px 5px #fff}"
        "@media print{.meta button{display:none}.pagina{margin:0;padding:0;box-shadow:none;border-radius:0}}\n"
        "</style>\n</head>\n<body>\n"
        "<div class=\"pagina\">\n"
        f"<div class=\"meta\"><span>{html.escape(corso)} · {html.escape(data)}</span>"
        "<button onclick=\"window.print()\">Stampa / salva PDF</button></div>\n"
        "<article id=\"appunti\" class=\"appunti\"></article>\n</div>\n"
        f"<script>\n{render_js}\n</script>\n"
        f"<script>Sbobina.render(document.getElementById('appunti'), {_json_in_script(appunti)});</script>\n"
        "</body>\n</html>\n"
    )


# --- PDF della lezione: appunti + approfondimento, impaginati per lo studio ----------

# Un colore per corso, sempre lo stesso: aiuta a riconoscere la materia a colpo d'occhio.
COLORI_CORSO = ("#1d4ed8", "#047857", "#7c3aed", "#c2410c", "#0f766e", "#be123c")

CHROME = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
)


def colore_corso(corso: str) -> str:
    return COLORI_CORSO[sum(corso.strip().casefold().encode()) % len(COLORI_CORSO)]


def trova_browser() -> str | None:
    for percorso in CHROME:
        if Path(percorso).is_file():
            return percorso
    for nome in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
        if trovato := shutil.which(nome):
            return trovato
    return None


CSS_PDF = """
@page { size: A4; margin: 18mm 17mm 20mm;
  @bottom-center { content: counter(page); font: 9pt system-ui, sans-serif; color: #9ca3af; } }
@page :first { @bottom-center { content: none; } }
html, body { background: #fff; }
body { font: 10.8pt/1.6 "Geist", system-ui, -apple-system, sans-serif; color: #1f2937; }
.copertina { height: 250mm; display: flex; flex-direction: column; justify-content: center; }
.copertina .corso { font-size: 11pt; letter-spacing: .18em; text-transform: uppercase; color: var(--c); font-weight: 600; }
.copertina h1 { font-size: 34pt; line-height: 1.12; margin: 6mm 0 4mm; color: #111827; letter-spacing: -0.02em; }
.copertina .data { color: #4b5563; font-size: 12pt; margin-bottom: 10mm; }
.copertina .barra { width: 28mm; height: 2.2mm; background: var(--c); border-radius: 2mm; margin-bottom: 12mm; }
.copertina ol { font-size: 12.5pt; padding-left: 6mm; margin: 0 0 14mm; }
.copertina li { margin-bottom: 3mm; }
.legenda { font-size: 9.8pt; color: #4b5563; border-top: 1px solid #e5e7eb; padding-top: 5mm; }
.legenda span { display: inline-block; margin-right: 7mm; }
section.parte { break-before: page; }
section.parte > h1.titolo-parte { font-size: 20pt; color: #111827; margin: 0 0 6mm; padding-bottom: 3mm; border-bottom: 2.5px solid var(--c); }
.appunti { font-size: 10.8pt; line-height: 1.6; }
.appunti h1 { display: none; }
.appunti h2 { color: var(--c); font-size: 14pt; border-bottom: 0; margin: 8mm 0 3mm; }
.appunti h3 { font-size: 11.8pt; margin: 6mm 0 2mm; }
.appunti th { background: var(--c); color: #fff; }
.appunti th strong { color: #fff; }
.appunti tr:nth-child(even) td { background: #f9fafb; }
.appunti blockquote { break-inside: avoid; }
.appunti details { display: block; }
.appunti details > * { display: block; }
.appunti .tempo { color: var(--c); background: none; padding: 0; }
.q { font-size: 8.6pt; color: #92400e; background: #fef3c7; border-radius: 1.2mm; padding: .2mm 1.4mm; white-space: nowrap; }
"""

MARCA_INCERTI = """
document.querySelectorAll('.appunti').forEach(function (radice) {
  var giro = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT);
  var nodi = []; while (giro.nextNode()) nodi.push(giro.currentNode);
  nodi.forEach(function (n) {
    if (!/\\[(da verificare|incerto|incomprensibile)\\]/i.test(n.nodeValue)) return;
    var span = document.createElement('span');
    span.innerHTML = n.nodeValue.replace(/[&<>]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]; })
      .replace(/\\[(da verificare|incerto|incomprensibile)\\]/gi, '<span class="q">$1</span>');
    n.replaceWith(span);
  });
});
"""


def esporta_pdf_html(
    *, titolo: str, corso: str, data: str, appunti: str, approfondimento: str | None, base: str | None = None
) -> str:
    """Pagina impaginata per il PDF: copertina con indice, poi appunti e approfondimento.

    `base`: da dove caricare font e librerie ("/static" se servita dall'app; di default i file locali).
    """
    base = base or STATIC.as_uri()
    css = (STATIC / "appunti.css").read_text(encoding="utf-8")
    render_js = (STATIC / "render.js").read_text(encoding="utf-8")
    font = f"{base}/fonts/Geist-Variable.woff2"
    parti = [("appunti", "Appunti della lezione", appunti)]
    if approfondimento:
        parti.append(("approfondimento", "Approfondimento", approfondimento))
    indice = "".join(f"<li>{html.escape(nome)}</li>" for _, nome, _ in parti)
    sezioni = "".join(
        f'<section class="parte"><h1 class="titolo-parte">{html.escape(nome)}</h1>'
        f'<article id="{chiave}" class="appunti"></article></section>'
        for chiave, nome, _ in parti
    )
    render = "Sbobina.pronto([" + ",".join(
        f"Sbobina.render(document.getElementById('{chiave}'), {_json_in_script(testo)})"
        for chiave, _, testo in parti
    ) + "]);\n"
    return (
        "<!doctype html>\n<html lang=\"it\" data-tema=\"chiaro\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{html.escape(titolo)} · {html.escape(corso)}</title>\n{librerie(base)}\n<style>\n"
        f"@font-face {{ font-family: 'Geist'; src: url('{font}') format('woff2'); font-weight: 100 900; }}\n"
        f"{css}\n:root {{ --c: {colore_corso(corso)}; }}\n{CSS_PDF}\n</style>\n</head>\n<body>\n"
        f'<div class="copertina"><div class="corso">{html.escape(corso)}</div><h1>{html.escape(titolo)}</h1>'
        f'<div class="data">{html.escape(data)}</div><div class="barra"></div><ol>{indice}</ol>'
        '<div class="legenda"><span>⭐ indicato dal docente</span><span>Integrazione: oltre la lezione</span>'
        '<span><span class="q">da verificare</span> controlla sul libro</span></div></div>\n'
        f"{sezioni}\n<script>\n{render_js}\n</script>\n<script>\n{render}{MARCA_INCERTI}</script>\n"
        "</body>\n</html>\n"
    )


def crea_pdf(pagina: str, destinazione: Path) -> None:
    """Stampa la pagina in PDF con Chrome (o Chromium/Edge) senza interfaccia."""
    browser = trova_browser()
    if not browser:
        raise RuntimeError(
            "Per creare il PDF serve Google Chrome (o Chromium o Edge). "
            "In alternativa apri la versione stampabile e usa Stampa → Salva come PDF."
        )
    with tempfile.TemporaryDirectory() as cartella:
        sorgente = Path(cartella) / "pagina.html"
        sorgente.write_text(pagina, encoding="utf-8")
        temporaneo = Path(cartella) / "appunti.pdf"
        risultato = subprocess.run(
            [browser, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
             f"--user-data-dir={Path(cartella) / 'profilo'}", "--virtual-time-budget=20000",
             f"--print-to-pdf={temporaneo}", sorgente.as_uri()],
            capture_output=True, text=True, timeout=180,
        )
        if risultato.returncode != 0 or not temporaneo.is_file() or temporaneo.stat().st_size < 1000:
            raise RuntimeError(f"Creazione del PDF non riuscita: {risultato.stderr.strip()[-300:]}")
        shutil.move(str(temporaneo), destinazione)
