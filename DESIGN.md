---
name: Sbobina
description: Vetro smerigliato su un cielo chiaro, accenti blu e bianchi; gli appunti stanno su carta piena.
colors:
  campo: "#edf2fa"
  vetro: "rgba(255,255,255,0.56)"
  vetro-forte: "rgba(255,255,255,0.82)"
  filo: "rgba(255,255,255,0.85)"
  filo-scuro: "rgba(20,44,92,0.09)"
  inchiostro: "#0e1a31"
  inchiostro-tenue: "#475877"
  inchiostro-lieve: "#63738f"
  blu: "#1f66f2"
  blu-forte: "#0d4fd6"
  blu-testo: "#0c4bcc"
  guasto: "#c3321e"
  carta: "#ffffff"
typography:
  titolo:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "clamp(34px, 4.6vw, 60px)"
    fontWeight: 900
    lineHeight: 0.95
    letterSpacing: "-0.045em"
  sezione:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    letterSpacing: "-0.02em"
  ui:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
  etichette:
    fontFamily: "Departure Mono, ui-monospace, monospace"
    fontSize: "13px"
    fontWeight: 400
  appunti:
    fontFamily: "Iowan Old Style, Charter, Georgia, serif"
    fontSize: "17px"
    lineHeight: 1.7
radius:
  grande: "28px"
  medio: "20px"
  piccolo: "14px"
  pillola: "999px"
motion:
  molla: "cubic-bezier(0.32, 0.72, 0, 1)"
  uscita: "cubic-bezier(0.16, 1, 0.3, 1)"
---

# Sbobina: design

**Aggiornamento 13/10/2026 (sera): Sbobina adotta lo stile di Lectio** (vedi `progetto1/Lectio/Documenti/DESIGN.md`): sistema operativo retro a 1 bit, carta #FEFEFE e inchiostro #1E1E1E, finestre con barra del titolo nera (`data-titolo` sui pannelli, es. "Lezioni 1.1"), Departure Mono per etichette e numeri, Geist Black per i titoli, griglia a puntini e retino, angoli vivi e ombre nette sfalsate, un solo accento rosa #D45BB6, desktop rosa a puntini #F386A1 mentre si registra. Il vetro resta solo su ciò che galleggia (barra in alto, download, trasporto audio, comandi di registrazione). Regole fisse: **tutto ad angoli vivi** (anche schede, interruttori, distintivi, cursori dei range e nodi delle mappe SVG; tondi solo i punti REC/"in corso"); ogni pannello e ogni foglio ha la barra del titolo nera; le scelte sono ChoiceChip «✣» (inchiostro + ombra d'accento quando scelte). **Temi colore** in Impostazioni > Aspetto: Jev rosa (predefinito), Menta, Arancio, Cobalto, Limone, Seppia (cambia anche carta e inchiostro), Tuo colore (#RRGGBB libero); ognuno imposta `--lectio` (accento) e `--rosa` (desktop di registrazione). Interruttori Griglia a puntini e Vetro (spento: carta piena). Implementato come blocco «TEMA LECTIO» in fondo ad `app.css`, che ridefinisce i gettoni; il resto di questo documento descrive la versione precedente.

**Il tema colora tutto (15/10/2026, su richiesta del proprietario: il nero era cupo):** ciò che era nero pieno (barre del titolo, tasti pieni, riga scelta, marchio, avvisi, cursori, ombre nette e bordi) usa `--tema`, l'accento del tema portato a luminosità OKLCH ≤ 0,5 così il testo bianco (`--su-tema`) resta ≥ 4,5:1 con ogni colore, anche «Tuo colore» chiaro; bordi e ombre usano `--tema-linea` (al buio si schiarisce), il testo d'accento `--tema-testo`. Lo sfondo resta bianco; finestre e griglia a puntini prendono una velatura dell'accento al posto del grigio (Seppia tiene la sua pergamena). Il testo resta d'inchiostro. Fallback senza colori relativi: `color-mix` al 72% con nero.

**Sezione nerd (15/10/2026):** impostazione nascosta, si svela con 5 clic sul titolo «Impostazioni». Accesa, compare il tasto «Statistiche» (mono, filo del tema) sotto ogni risposta di Chiedi e in «dietro le quinte» durante l'elaborazione: griglia di numeri (motore, modello, token letti/scritti, velocità di lettura e scrittura, primo token, memoria al picco, durata, contesto…). Mentre l'AI pensa, una riga mono con i numeri in diretta sotto la bobina.

**Chiedi alle tue lezioni (15/10/2026):** tasto «Chiedi» nella testata → vista con conversazione su tutte le lezioni pronte (filtro per corso con le ChoiceChip, domande di partenza cliccabili, sotto ogni risposta i tasti delle lezioni usate). Mentre l'AI pensa compare la **bobina che pensa**: il marchio su piastrella bianca con filo d'inchiostro, solo le cinque linee audio che ondeggiano in sequenza (la centrale blu #1f5bff), più i secondi trascorsi dopo 5 s. Sostituisce i tre puntini in ogni attesa dell'AI.

Direzione precedente: **glassmorphism con accenti blu e bianchi**, finitura professionale. Sostituisce il precedente pannello hi-fi in neumorfismo.

## Mondo
- **Cielo:** fondo chiaro `campo` con tre nebbie blu sfocate che si spostano piano (livello fisso `body::before`, 38 s) e una grana leggerissima. Al buio (`prefers-color-scheme: dark`) il cielo diventa blu notte.
- **Vetro:** testata, rastrelliera, trasporto audio, commutatore, menu: bianco traslucido, `backdrop-filter: blur(22px) saturate(1.6)`, filo bianco di 1 px, luce interna in alto, ombra morbida tinta di blu. Il blur sta solo su elementi fissi o piccoli.
- **Doppia cornice:** i pannelli importanti (avanzamento, moduli, vassoio) hanno un anello di vetro più chiaro attorno alla lastra (box-shadow a 6–8 px).
- **Carta:** appunti, trascrizione e verifica stanno su un foglio pieno (`carta`), mai su vetro: si leggono e si stampano.

## Componenti
- **Testata a isola:** pillola sospesa, sticky a 14 px dall'alto: logo (lastra blu con onda bianca), stato dell'AI, tasto Nuova lezione.
- **Tasto principale:** pillola blu con l'icona nel suo pozzetto circolare che scivola al passaggio; si preme scalando a 0,98.
- **Vassoio (benvenuto):** grande zona dove trascinare la registrazione; il disco blu si alza e ruota quando ci passa sopra un file.
- **Avanzamento:** l'unico momento animato davvero. Percentuale grande, barra liquida con riflesso che scorre mentre lavora, sei tappe (fatte con la spunta, corrente con battito), tasti Ferma / Riprendi. Stati: in coda, attiva, fermata (grigia), errore (rossa).
- **Dietro le quinte (dentro l'avanzamento):** riga con la girandola (asterisco disegnato in SVG che gira e respira, mai un glifo Unicode), un verbo buffo che cambia ogni ~4 s mettendosi a fuoco dalla nebbia (metà italiano, metà inglese, a tema con la tappa: Whisper "Origliando", la revisione "Limando", gli appunti "Scarabocchiando"), i secondi trascorsi e chi sta lavorando. Sotto, il testo in diretta su **carta** (serif degli appunti): frasi di Whisper con il minuto in blu, oppure gli appunti mentre il modello li scrive, con le parole nuove che passano dal blu all'inchiostro e un cursore blu. Richiudibile; la scelta resta.
- **Download dei modelli:** lastra di vetro sticky sotto la testata, pozzetto blu con la freccia che scende, nome del modello, "GB di GB · MB/s · tempo che manca", barra liquida e percentuale. Compare e scompare mettendosi a fuoco; è l'unico posto dove si vede un download.
- **Commutatore delle schede:** il cursore bianco scivola sotto la scheda scelta; cambia solo il foglio, non la pagina.

## Movimento
- Curve: `molla` per oggetti che si spostano, `uscita` per comparse e colori. Niente linear o ease-in-out.
- Ingresso delle viste: i blocchi salgono di 14 px e si mettono a fuoco (blur 6 px → 0) in sequenza.
- `prefers-reduced-motion`: tutto ridotto a 1 ms, cielo fermo.

## Accessibilità
Testo ≥ 4,5:1 sul vetro (inchiostro-tenue #475877 su bianco ~7:1), anello di focus blu 2 px, selezione e cursore del testo blu, barre di scorrimento sottili a tema.
