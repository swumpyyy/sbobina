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
    fontFamily: "Schibsted Grotesk, system-ui, sans-serif"
    fontSize: "clamp(34px, 4.6vw, 60px)"
    fontWeight: 650
    lineHeight: 1.04
    letterSpacing: "-0.04em"
  sezione:
    fontFamily: "Schibsted Grotesk, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 650
    letterSpacing: "-0.025em"
  ui:
    fontFamily: "Schibsted Grotesk, system-ui, sans-serif"
    fontSize: "15px"
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

Direzione scelta dal proprietario il 13/10/2026: **glassmorphism con accenti blu e bianchi**, finitura professionale. Sostituisce il precedente pannello hi-fi in neumorfismo.

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
- **Commutatore delle schede:** il cursore bianco scivola sotto la scheda scelta; cambia solo il foglio, non la pagina.

## Movimento
- Curve: `molla` per oggetti che si spostano, `uscita` per comparse e colori. Niente linear o ease-in-out.
- Ingresso delle viste: i blocchi salgono di 14 px e si mettono a fuoco (blur 6 px → 0) in sequenza.
- `prefers-reduced-motion`: tutto ridotto a 1 ms, cielo fermo.

## Accessibilità
Testo ≥ 4,5:1 sul vetro (inchiostro-tenue #475877 su bianco ~7:1), anello di focus blu 2 px, selezione e cursore del testo blu, barre di scorrimento sottili a tema.
