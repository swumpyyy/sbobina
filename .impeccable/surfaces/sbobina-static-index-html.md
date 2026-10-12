---
version: 1
slug: "sbobina-static-index-html"
primary_target: "sbobina/static/index.html"
related_targets: ["sbobina/static/app.css","sbobina/static/app.js"]
---

# Surface brief: app shell (index.html)

Scope: the whole local web app (lesson list, new lesson, processing, notes reader, glossary). Visitor mode: Operate.
Audience and job: Italian university students turn a lecture recording into study notes, leave it running, come back, read, print, review.
Constraints: neumorphism is pinned by the owner; ADHD-friendly (one next action, visible progress); WCAG AA text and focus; Italian copy; free local AI; notes stay paper-readable and printable.
Memorable moment: the phase selector knob and VU meter turning while a lesson is "tuned in".

## Direction contract

THESIS: Sbobina is an Italian hi-fi apparatus, not a notes website. A lesson is tuned in on a dial, a rotary selector shows which phase is playing (Trascrizione, Revisione, Appunti, Verifica), and a VU meter shows how much is left. Refuses the sidebar-plus-document SaaS layout and the flat card grid.

OWN-WORLD: one cool grey moulded field (#e3e7ee) with soft paired shadows (white top-left, blue-grey bottom-right); controls are extruded when idle and inset when pressed or selected; round icon wells, pill switches, one engraved tuning scale; ink #1d2330; one amber indicator lamp (#ff6a13 family, darkened for text) used only for "live/selected". States are never colour-only: knob position, LED shape, inset vs extruded. One sans family on four fixed steps, like screen-printed panel legends.

STORY: the student sees the apparatus with the lessons already tuned. One big key says Nuova lezione. While a lesson processes, the dial and meter show the phase and remaining time; a finished lesson keeps its lamp lit until opened. Opening it lowers a paper sheet out of the panel: the notes, readable and printable.

FIRST VIEWPORT: top strip with the Sbobina badge and a pill "AI locale · gratuita" status lamp. Left, a module rack: one extruded module per course with its lessons as preset buttons (lamp, title, duration). Right, the main deck: selected lesson title, the rotary phase selector plus VU meter while processing, or the notes sheet when ready; under it, transport keys (Stampa / PDF, Markdown, Rielabora, Glossario). Primary action Nuova lezione is the largest key, top right. Mobile: only the deck with the next decision, the rack becomes a preset strip.

FORM: Brionvega-style Italian hi-fi panel, candidate 6 of 7 on the ordered list; seed key ad589287. Raises kept: single next decision on small screens (wayfinding), colour-independent states (exposure record), fixed course modules reflowing in whole cells (roster), one family on fixed steps (bitmap specimen).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved
- Dark mode: the moulded field is designed light; a dark variant is out of scope for this pass.
