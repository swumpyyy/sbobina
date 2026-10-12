"""Esportazione degli appunti in una pagina HTML autonoma (apribile offline e stampabile in PDF)."""

from __future__ import annotations

import html
import json
from pathlib import Path

STATIC = Path(__file__).parent / "static"

# Librerie per il rendering (versioni fissate). Usate sia dall'app sia dalle pagine esportate.
LIBRERIE = """\
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.47/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/marked@15.0.12/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.4.15/dist/purify.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.47/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.min.js"></script>
<script>window.markmap = { autoLoader: { manual: true, toolbar: false } };</script>
<script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@0.18.12/dist/index.js"></script>"""


def _json_in_script(valore) -> str:
    """JSON sicuro da inserire dentro <script> (niente chiusura prematura del tag)."""
    return json.dumps(valore, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")


def esporta_html(*, titolo: str, corso: str, data: str, appunti: str) -> str:
    css = (STATIC / "appunti.css").read_text(encoding="utf-8")
    render_js = (STATIC / "render.js").read_text(encoding="utf-8")
    return (
        "<!doctype html>\n<html lang=\"it\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(titolo)} · {html.escape(corso)}</title>\n"
        f"{LIBRERIE}\n<style>\n{css}\n"
        ".pagina{max-width:860px;margin:0 auto;padding:24px 16px 64px}"
        ".meta{color:var(--testo-tenue);font-size:.9rem;margin-bottom:8px;display:flex;gap:12px;"
        "flex-wrap:wrap;align-items:center;justify-content:space-between}"
        ".meta button{font:inherit;padding:6px 12px;border-radius:8px;border:1px solid var(--bordo);"
        "background:var(--superficie);color:var(--testo);cursor:pointer}"
        "@media print{.meta button{display:none}}\n</style>\n</head>\n<body>\n"
        "<div class=\"pagina\">\n"
        f"<div class=\"meta\"><span>{html.escape(corso)} · {html.escape(data)}</span>"
        "<button onclick=\"window.print()\">Stampa / salva PDF</button></div>\n"
        "<article id=\"appunti\" class=\"appunti\"></article>\n</div>\n"
        f"<script>\n{render_js}\n</script>\n"
        f"<script>Sbobina.render(document.getElementById('appunti'), {_json_in_script(appunti)});</script>\n"
        "</body>\n</html>\n"
    )
