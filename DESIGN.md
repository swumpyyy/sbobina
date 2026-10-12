---
name: Sbobina
description: Un apparecchio hi-fi italiano che sintonizza le lezioni e ne fa appunti.
colors:
  campo: "#e3e7ee"
  luce: "#ffffff"
  ombra: "#b5bfd0"
  ombra-forte: "#a3aec2"
  inchiostro: "#1d2330"
  inchiostro-tenue: "#4f596d"
  incisione: "#8792a6"
  lampada: "#ff6a13"
  lampada-testo: "#a8420a"
  guasto: "#b3261e"
  carta: "#fbfcfe"
  accento-tenue: "#fbe6d8"
typography:
  titolo:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.03em"
  sezione:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 650
    letterSpacing: "-0.02em"
  ui:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  legenda:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 550
  dati:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "0.8125rem"
rounded:
  pillola: "999px"
  modulo: "28px"
  scheda: "24px"
  tasto: "18px"
  tacca: "4px"
components:
  tasto:
    backgroundColor: "{colors.campo}"
    textColor: "{colors.inchiostro}"
    rounded: "{rounded.pillola}"
  tasto-grande:
    backgroundColor: "{colors.campo}"
    textColor: "{colors.inchiostro}"
    rounded: "{rounded.pillola}"
    height: "52px"
  spia-ai:
    backgroundColor: "{colors.campo}"
    textColor: "{colors.inchiostro-tenue}"
    rounded: "{rounded.pillola}"
  foglio-appunti:
    backgroundColor: "{colors.carta}"
    textColor: "{colors.inchiostro}"
    rounded: "{rounded.scheda}"
---

# Sbobina: sistema visivo

## Overview

Sbobina è un apparecchio hi-fi italiano, non un sito di appunti: un pannello grigio stampato con tasti in rilievo, un selettore rotativo delle fasi, un VU meter e una sola spia ambra. Una lezione si "sintonizza"; mentre viene elaborata la manopola e il meter si muovono; quando è pronta esce dal pannello un foglio di carta, gli appunti. Il neumorfismo è fissato dal proprietario (PRODUCT.md). Modalità: Operate. Pensato per l'ADHD: una sola azione per schermata e avanzamento sempre visibile.

È un'app nativa per macOS (`Sbobina.app`, una finestra WebKit sopra il server locale): la barra del titolo prende il grigio del pannello, così la finestra sembra un unico pezzo stampato.

## Colors

- **Campo** `#e3e7ee`: l'unico fondo stampato. Ogni controllo sta qui sopra, mai sul bianco.
- **Luce / Ombra** `#ffffff` / `#b5bfd0`: sempre in coppia (luce in alto a sinistra, ombra in basso a destra) per modellare il rilievo. Mai l'una senza l'altra.
- **Inchiostro** `#1d2330`: testo e indici. **Inchiostro tenue** `#4f596d` per il testo secondario (AA sul campo).
- **Incisione** `#8792a6`: solo tacche della scala, mai testo.
- **Lampada** `#ff6a13`: l'unico colore che "si accende". Significa attivo o selezionato e nient'altro. Sul testo diventa **lampada-testo** `#a8420a` (AA). L'alone della spia è un'eccezione voluta al rilevatore dark-glow (registrata in `.impeccable/config.json`).
- **Carta** `#fbfcfe`: solo il foglio degli appunti, l'unica superficie non stampata.
- **Guasto** `#b3261e`: solo errori, sempre insieme a icona e testo.

## Typography

**Saira** (OFL, variabile 100–900, nel progetto in `static/fonts`) per tutto: le sue forme squadrate discendono dall'Eurostile, il carattere serigrafato sui pannelli hi-fi italiani degli anni '70, quindi le etichette sembrano legende del pannello ma il testo resta leggibile. **Martian Mono** (OFL, variabile) solo per i dati: durate, percentuali, minutaggi, con cifre tabellari.

Quattro gradini fissi, mai vie di mezzo: legenda 13px, ui 15px, sezione 20px, titolo 32px. Pesi: 400 testo, 550 etichette, 650 titoli. I titoli stringono la spaziatura (-0.02/-0.03em); niente etichette tutte maiuscole.

## Layout

Striscia in alto (badge, spia AI, tasto Nuova lezione a destra). A sinistra la rastrelliera: un modulo per corso, le lezioni come tasti di preselezione. A destra il banco: una decisione alla volta (benvenuto, nuova lezione, elaborazione con manopola e VU, foglio degli appunti). Finestra stretta: solo il banco, la rastrelliera diventa una striscia. Finestra minima 900×620.

## Elevation & Depth

Solo due livelli, entrambi in rilievo, mai schede che galleggiano:
- **Estruso** (a riposo, premibile): `7px 7px 16px ombra, -7px -7px 16px luce`; versione piccola 4/10px.
- **Incassato** (premuto, selezionato, campi, meter): la stessa coppia, verso l'interno.
Un cambio di stato passa da estruso a incassato, mai solo con il colore.

## Shapes

Pillole (999px) per tasti, ricerca e spia AI. Pozzetti tondi (50%) per icone e manopola. Moduli 28px, fogli 24px, tasti piccoli 18px. Nei riquadri niente bordo spesso a sinistra.

## Components

- **Tasto**: pillola in rilievo; premuto diventa incassato; il focus è un contorno inchiostro di 2.5px a 3px di distanza.
- **Tasto grande**: l'unica azione principale della schermata (Nuova lezione, Carica la prima lezione).
- **Spia AI**: pillola incassata con la lampada. Accesa: AI pronta. Spenta con "AI non pronta": compare l'avviso con il tasto **Prepara l'AI**, che avvia Ollama e scarica il modello con la barra di avanzamento.
- **Selettore di fase + VU**: manopola con indice d'inchiostro e 40 LED; la lancetta e la percentuale in Martian Mono dicono sempre a che punto è la lezione.
- **Foglio appunti**: il foglio di carta; tipografia e riquadri in `appunti.css`, usati anche dal PDF.

## Do's and Don'ts

- Do: un solo tasto principale per schermata.
- Do: ogni stato si vede dalla forma (estruso/incassato, LED acceso/spento, posizione della manopola), non solo dal colore.
- Do: testo sempre AA sul campo; il neumorfismo non deve schiarire l'inchiostro.
- Don't: nuovi colori; la spia ambra è l'unico accento.
- Don't: finestre di dialogo o modali; tutto si apre nel banco.
- Don't: easing che rimbalza; si usa `cubic-bezier(0.22,1,0.36,1)`.
- Don't: animare larghezze o layout; solo transform e opacity.
