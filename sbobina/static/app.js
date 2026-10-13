/* Sbobina: interfaccia web (vetro, accenti blu). */
(function () {
  "use strict";

  const $ = (selettore, radice = document) => radice.querySelector(selettore);
  const ATTIVI = new Set(["in_coda", "in_elaborazione"]);
  const TIPI_PROBLEMA = {
    non_supportato: "Non detto a lezione",
    errato: "Errato",
    omesso: "Mancante",
    integrazione_errata: "Integrazione errata",
    schema: "Schema",
    formato: "Formato",
  };
  // Le tappe dell'elaborazione. Il server salva la fase come etichetta ("Revisione della trascrizione"):
  // ogni tappa riconosce le etichette dall'inizio.
  const TACCHE = [
    { etichetta: "Preparazione", inizi: ["preparazione", "analisi"] },
    { etichetta: "Trascrizione", inizi: ["trascrizione"] },
    { etichetta: "Revisione", inizi: ["revisione"] },
    { etichetta: "Appunti", inizi: ["scrittura", "appunti"] },
    { etichetta: "Verifica", inizi: ["verifica", "correzione"] },
    { etichetta: "Approfondimento", inizi: ["approfondimento"] },
  ];
  const ACCETTA_AUDIO = "audio/*,video/*,.m4a,.mp3,.wav,.ogg,.opus,.flac,.aac,.amr,.3gp,.caf,.webm,.mp4,.wma";

  const ICONE = {
    piu: '<path d="M12 5v14M5 12h14"/>',
    microfono: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
    play: '<path d="M8 5.5v13l10.5-6.5z" fill="currentColor"/>',
    pausa: '<path d="M8 5v14M16 5v14" stroke-width="3"/>',
    indietro: '<path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.5"/><path d="M4 4v4.5h4.5"/>',
    avanti: '<path d="M20 12a8 8 0 1 1-2.4-5.7L20 8.5"/><path d="M20 4v4.5h-4.5"/>',
    stampa: '<path d="M7 9V3.5h10V9"/><rect x="3.5" y="9" width="17" height="8" rx="2"/><path d="M7 14h10v6.5H7z"/>',
    scarica: '<path d="M12 4v11M7 10.5 12 15.5l5-5M5 20h14"/>',
    ricarica: '<path d="M20 11a8 8 0 0 0-14.5-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.5 4.5L20 16M20 20v-4h-4"/>',
    glossario: '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z"/><path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19M9 8h6M9 11.5h4"/>',
    cestino: '<path d="M4.5 7h15M10 11v6M14 11v6M6.5 7l1 13h9l1-13M9.5 7V4h5v3"/>',
    freccia: '<path d="m9 6 6 6-6 6"/>',
    avviso: '<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.2v.3"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.3"/>',
    calendario: '<rect x="4" y="5.5" width="16" height="14.5" rx="2.5"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
    orologio: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    graffetta: '<path d="m20 11.5-7.8 7.8a5 5 0 0 1-7.1-7.1l8.3-8.3a3.4 3.4 0 0 1 4.8 4.8l-8.3 8.3a1.7 1.7 0 0 1-2.4-2.4l7.6-7.6"/>',
    onda: '<path d="M3 12h2M7 8v8M11 5v14M15 9v6M19 7v10M21 12h0"/>',
    matita: '<path d="M4 20h4L19.5 8.5a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m14 6 4 4"/>',
    spunta: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    ferma: '<rect x="6.5" y="6.5" width="11" height="11" rx="2.5"/>',
    carica: '<path d="M12 15.5V4.5M7.5 9 12 4.5 16.5 9"/><path d="M4.5 14.5v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3"/>',
    cuffie: '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4.5" height="6.5" rx="2"/><rect x="16.5" y="14" width="4.5" height="6.5" rx="2"/>',
  };

  const stato = {
    info: null,
    lezioni: [],
    selezionata: null,
    dettaglio: null,
    scheda: "appunti",
    filtro: "",
    timer: null,
    timerInfo: null,
    vista: "benvenuto",
  };

  // --- utilità ------------------------------------------------------------

  /** Crea un elemento DOM. I figli stringa diventano nodi di testo (niente HTML iniettato). */
  function h(tag, attributi = {}, ...figli) {
    const el = document.createElement(tag);
    for (const [chiave, valore] of Object.entries(attributi || {})) {
      if (valore === null || valore === undefined || valore === false) continue;
      if (chiave === "class") el.className = valore;
      else if (chiave.startsWith("on")) el.addEventListener(chiave.slice(2), valore);
      else el.setAttribute(chiave, valore === true ? "" : valore);
    }
    for (const figlio of figli.flat()) {
      if (figlio === null || figlio === undefined || figlio === false) continue;
      el.append(figlio instanceof Node ? figlio : document.createTextNode(String(figlio)));
    }
    return el;
  }

  function icona(nome) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "icona");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.innerHTML = ICONE[nome]; // solo costanti di questo file
    return svg;
  }

  async function api(percorso, opzioni = {}) {
    const intestazioni = { ...(opzioni.headers || {}) };
    if (opzioni.method && opzioni.method !== "GET") intestazioni["X-Sbobina"] = "1";
    const risposta = await fetch(percorso, { ...opzioni, headers: intestazioni });
    if (!risposta.ok) {
      let messaggio = `Errore ${risposta.status}`;
      try {
        const corpo = await risposta.json();
        if (corpo.detail) messaggio = typeof corpo.detail === "string" ? corpo.detail : JSON.stringify(corpo.detail);
      } catch (e) { /* risposta non JSON */ }
      throw new Error(messaggio);
    }
    return risposta.status === 204 ? null : risposta.json();
  }

  function formattaDurata(secondi) {
    if (!secondi) return "";
    const minuti = Math.round(secondi / 60);
    if (minuti < 60) return `${minuti} min`;
    return `${Math.floor(minuti / 60)} h ${String(minuti % 60).padStart(2, "0")} min`;
  }

  function formattaOrologio(secondi) {
    if (!Number.isFinite(secondi)) return "0:00";
    const s = Math.max(0, Math.floor(secondi));
    const ore = Math.floor(s / 3600);
    const min = Math.floor((s % 3600) / 60);
    const sec = String(s % 60).padStart(2, "0");
    return ore ? `${ore}:${String(min).padStart(2, "0")}:${sec}` : `${min}:${sec}`;
  }

  function formattaData(iso) {
    if (!iso) return "";
    const data = new Date(`${iso}T12:00:00`);
    if (Number.isNaN(data.getTime())) return iso;
    return new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "short", year: "numeric" }).format(data);
  }

  const percentuale = (valore) => `${Math.round((valore || 0) * 100)}%`;

  /** Riempie la piastra; con `anima` i blocchi entrano in sequenza. */
  function riempiPiastra(elementi, anima = true) {
    const piastra = $("#contenuto");
    piastra.replaceChildren(...elementi);
    if (!anima) return;
    piastra.classList.remove("entra");
    void piastra.offsetWidth; // riavvia l'animazione
    piastra.classList.add("entra");
  }

  // Una lezione pronta resta "accesa" finché non la apri.
  const CHIAVE_VISTE = "sbobina-viste";
  function viste() {
    try { return new Set(JSON.parse(localStorage.getItem(CHIAVE_VISTE) || "[]")); } catch (e) { return new Set(); }
  }
  function segnaVista(id) {
    const insieme = viste();
    if (insieme.has(id)) return;
    insieme.add(id);
    try { localStorage.setItem(CHIAVE_VISTE, JSON.stringify([...insieme])); } catch (e) { /* storage pieno */ }
  }

  function segnale(l, giaViste) {
    let tipo = "letta";
    let descrizione = "Pronta";
    if (l.stato === "errore") { tipo = "guasto"; descrizione = "Interrotta da un errore"; }
    else if (l.stato === "in_coda") { tipo = "coda"; descrizione = "In coda"; }
    else if (l.stato === "in_elaborazione") { tipo = "attiva"; descrizione = "In elaborazione"; }
    else if (l.stato === "fermata") { tipo = "fermata"; descrizione = "Fermata"; }
    else if (!giaViste.has(l.id)) { tipo = "nuova"; descrizione = "Pronta, non ancora aperta"; }
    return h("span", { class: `segnale ${tipo}`, role: "img", "aria-label": descrizione });
  }

  // --- stato dell'AI e avvisi -----------------------------------------------

  function mostraStatoAI() {
    const pillola = $("#stato-ai");
    const info = stato.info;
    pillola.replaceChildren();
    if (!info) return;
    const pronta = info.llm;
    pillola.classList.toggle("spenta", !pronta);
    let testo;
    if (info.locale) testo = pronta ? [info.motore === "mlx" ? "AI integrata" : "AI locale", h("span", { class: "testo-lungo" }, " · gratuita")] : ["AI non pronta"];
    else testo = pronta ? ["Claude", h("span", { class: "testo-lungo" }, " · a pagamento")] : ["Manca la chiave di Claude"];
    pillola.append(h("span", { class: "lampadina", "aria-hidden": "true" }), h("span", {}, ...testo));
    pillola.title = info.modello;
  }

  function avvisiConfigurazione() {
    const info = stato.info;
    const avvisi = [];
    if (!info) return avvisi;
    if (!info.ffmpeg) {
      avvisi.push(h("div", { class: "avviso grave", role: "alert" }, icona("avviso"),
        h("strong", {}, "Manca ffmpeg, che serve per leggere l'audio."),
        h("span", {}, "Installalo e riavvia Sbobina.")));
    }
    if (!info.llm && info.locale) {
      const p = info.preparazione || {};
      const corpo = p.attiva
        ? h("div", { class: "preparazione" },
            h("span", {}, p.messaggio),
            h("span", { class: "mini-meter", role: "progressbar", "aria-valuenow": Math.round((p.progresso || 0) * 100),
              "aria-valuemin": 0, "aria-valuemax": 100 }, h("div", { style: `width:${percentuale(p.progresso || 0)}` })))
        : h("div", { class: "preparazione" },
            p.errore ? h("span", { role: "alert" }, p.errore) : h("span", {}, info.motore === "mlx" ? "Una volta sola: Sbobina scarica il modello sul tuo Mac." : "Una volta sola: Sbobina avvia Ollama e scarica il modello."),
            h("button", { class: "tasto", type: "button", onclick: preparaAI }, p.errore ? "Riprova" : "Prepara l'AI"));
      avvisi.push(h("div", { class: "avviso", role: "status" }, icona("info"),
        h("strong", {}, "L'AI che scrive gli appunti non è ancora pronta."), corpo));
    } else if (!info.llm) {
      avvisi.push(h("div", { class: "avviso", role: "status" }, icona("info"),
        h("strong", {}, "Manca la chiave di Claude."),
        h("span", {}, "Aggiungi ANTHROPIC_API_KEY al file .env, oppure torna al modello locale gratuito.")));
    }
    return avvisi;
  }

  async function preparaAI() {
    await api("/api/ai/prepara", { method: "POST" });
    aggiornaInfo();
  }

  async function aggiornaInfo() {
    try {
      const prima = stato.info && stato.info.llm;
      const preparava = stato.info && stato.info.preparazione && stato.info.preparazione.attiva;
      stato.info = await api("/api/stato");
      applicaAspetto();
      mostraStatoAI();
      const prepara = stato.info.preparazione && stato.info.preparazione.attiva;
      if (stato.vista === "benvenuto" && ((prima === false && stato.info.llm) || prepara || preparava)) mostraBenvenuto();
    } catch (e) { /* server momentaneamente irraggiungibile */ }
    clearTimeout(stato.timerInfo);
    const attiva = stato.info && stato.info.preparazione && stato.info.preparazione.attiva;
    if (stato.info && !stato.info.llm) stato.timerInfo = setTimeout(aggiornaInfo, attiva ? 1000 : 10000);
  }

  // --- rastrelliera: un modulo per corso, una preselezione per lezione -------

  function mostraElenco() {
    const contenitore = $("#elenco");
    contenitore.replaceChildren();
    const filtro = stato.filtro.trim().toLowerCase();
    const lezioni = stato.lezioni.filter((l) =>
      !filtro || l.titolo.toLowerCase().includes(filtro) || l.corso.toLowerCase().includes(filtro));
    if (!stato.lezioni.length) {
      contenitore.append(h("p", { class: "vuoto-elenco" }, "Ancora nessuna lezione."));
      return;
    }
    if (!lezioni.length) {
      contenitore.append(h("p", { class: "vuoto-elenco" }, `Nessuna lezione per "${stato.filtro.trim()}".`));
      return;
    }
    const giaViste = viste();
    const perCorso = new Map();
    for (const l of lezioni) {
      if (!perCorso.has(l.corso)) perCorso.set(l.corso, []);
      perCorso.get(l.corso).push(l);
    }
    for (const corso of [...perCorso.keys()].sort((a, b) => a.localeCompare(b, "it"))) {
      const voci = perCorso.get(corso);
      const elenco = h("div", { class: "preselezioni" });
      for (const l of voci) {
        const attiva = ATTIVI.has(l.stato);
        const sotto = attiva
          ? h("span", { class: "sotto" },
              h("span", { class: "dati" }, l.stato === "in_coda" ? "in coda" : percentuale(l.progresso)),
              h("span", { class: "mini-meter", "aria-hidden": "true" }, h("div", { style: `width:${percentuale(l.progresso)}` })))
          : h("span", { class: "sotto" },
              h("span", {}, formattaData(l.data)),
              l.durata_secondi ? h("span", { class: "dati" }, formattaDurata(l.durata_secondi)) : null,
              l.stato === "errore" ? h("span", {}, "· da riprovare") : null,
              l.stato === "fermata" ? h("span", {}, "· fermata") : null);
        elenco.append(h("button", {
          class: "preselezione",
          type: "button",
          "aria-current": l.id === stato.selezionata ? "true" : null,
          onclick: () => apriLezione(l.id),
        }, segnale(l, giaViste), h("span", { class: "titolo" }, l.titolo), sotto));
      }
      contenitore.append(h("section", { class: "modulo", "aria-label": corso },
        h("div", { class: "modulo-testa" },
          h("h2", {}, corso),
          h("span", { class: "conta", "aria-label": `${voci.length} lezioni` }, String(voci.length).padStart(2, "0")),
          (() => {
            const tasto = h("button", {
              class: "tasto tondo", type: "button", title: `PDF di tutto il corso ${corso}`, "aria-label": `PDF di tutto il corso ${corso}`,
            }, icona("scarica"));
            tasto.addEventListener("click", () => scaricaPdf(tasto, `/api/corsi/pdf?corso=${encodeURIComponent(corso)}`, `${corso} - tutte le lezioni.pdf`));
            return tasto;
          })(),
          h("button", {
            class: "tasto tondo",
            type: "button",
            title: `Glossario di ${corso}`,
            "aria-label": `Glossario di ${corso}`,
            onclick: () => mostraGlossario(corso),
          }, icona("glossario"))),
        elenco));
    }
  }

  // --- benvenuto --------------------------------------------------------------

  function mostraBenvenuto() {
    stato.vista = "benvenuto";
    const ciSonoLezioni = stato.lezioni.length > 0;
    const input = h("input", { type: "file", accept: ACCETTA_AUDIO, multiple: true });
    const vassoio = h("label", { class: "vassoio" },
      h("span", { class: "disco", "aria-hidden": "true" }, icona("carica")),
      h("strong", {}, "Trascina qui la registrazione"),
      h("span", {}, "oppure fai clic per sceglierla · m4a, mp3, wav e altri formati"),
      input);
    input.addEventListener("change", () => input.files.length && mostraNuova(input.files));
    vassoio.addEventListener("dragover", (e) => { e.preventDefault(); vassoio.classList.add("sopra"); });
    vassoio.addEventListener("dragleave", () => vassoio.classList.remove("sopra"));
    vassoio.addEventListener("drop", (e) => {
      e.preventDefault();
      vassoio.classList.remove("sopra");
      if (e.dataTransfer.files.length) mostraNuova(e.dataTransfer.files);
    });

    const pronte = stato.lezioni.filter((l) => l.stato === "completata");
    const ore = pronte.reduce((somma, l) => somma + (l.durata_secondi || 0), 0) / 3600;
    const corsi = new Set(stato.lezioni.map((l) => l.corso)).size;
    const passo = (nome, testo) => h("li", {}, icona(nome), testo);

    riempiPiastra([
      ...avvisiConfigurazione(),
      h("section", { class: "benvenuto" },
        h("h1", {}, ciSonoLezioni
          ? ["Riprendi da dove eri, ", h("em", {}, "o aggiungi una lezione.")]
          : ["Dalla registrazione agli appunti, ", h("em", {}, "sul tuo computer.")]),
        h("p", { class: "sottotitolo" }, "Sbobina trascrive la lezione, corregge i termini con le tue slide, scrive appunti con schemi e domande di ripasso e li ricontrolla con l'audio. Niente account, niente costi, l'audio non esce dal Mac."),
        vassoio,
        ciSonoLezioni
          ? h("ul", { class: "contatori" },
              h("li", {}, h("b", {}, String(pronte.length)), pronte.length === 1 ? "lezione pronta" : "lezioni pronte"),
              h("li", {}, h("b", {}, ore.toLocaleString("it-IT", { maximumFractionDigits: 1 })), "ore sbobinate"),
              h("li", {}, h("b", {}, String(corsi)), corsi === 1 ? "corso" : "corsi"))
          : h("ol", { class: "percorso", "aria-label": "Come funziona" },
              passo("microfono", "Carica l'audio"),
              passo("onda", "Lascia lavorare, anche a finestra chiusa"),
              passo("stampa", "Studia, riascolta, stampa il PDF"))),
    ]);
  }

  // --- dettaglio lezione ----------------------------------------------------

  async function apriLezione(id, { mantieniScheda = false } = {}) {
    const stessaLezione = stato.selezionata === id && stato.vista === "lezione";
    stato.selezionata = id;
    if (!mantieniScheda) stato.scheda = "appunti";
    if (location.hash !== `#${id}`) history.replaceState(null, "", `#${id}`);
    try {
      stato.dettaglio = await api(`/api/lezioni/${id}`);
    } catch (e) {
      stato.selezionata = null;
      history.replaceState(null, "", location.pathname);
      mostraElenco();
      mostraBenvenuto();
      return;
    }
    if (stato.dettaglio.lezione.stato === "completata") segnaVista(id);
    mostraElenco();
    mostraDettaglio({ conservaAudio: stessaLezione });
  }

  function indiceTacca(fase) {
    const testo = (fase || "").toLowerCase();
    const i = TACCHE.findIndex((t) => t.inizi.some((inizio) => testo.startsWith(inizio)));
    return i === -1 ? 0 : i;
  }

  /** L'avanzamento: percentuale, barra liquida, le sei tappe e i tasti Ferma / Riprendi. */
  function consoleElaborazione(l) {
    const tappe = h("ol", { class: "tappe" }, TACCHE.map((t) =>
      h("li", { class: "tappa" }, h("span", { class: "punto", "aria-hidden": "true" }, icona("spunta")), t.etichetta)));
    const console = h("section", { class: "pannello avanzamento", id: "console", "aria-label": "Elaborazione" },
      h("div", { class: "avanz-testa" },
        h("div", { class: "percento", "aria-hidden": "true" }, h("span", { class: "valore" }, "0"), h("span", { class: "unita" }, "%")),
        h("div", { class: "fase-blocco" },
          h("span", { class: "fase", role: "status", "aria-live": "polite" }),
          h("p", { class: "messaggio" })),
        h("div", { class: "azioni" })),
      h("div", { class: "liquido", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100 },
        h("div", { class: "riempimento" })),
      tappe);
    aggiornaConsole(console, l);
    return console;
  }

  function aggiornaConsole(console, l) {
    const inCoda = l.stato === "in_coda";
    const guasto = l.stato === "errore";
    const fermata = l.stato === "fermata";
    const attiva = l.stato === "in_elaborazione";
    const corrente = indiceTacca(l.fase);
    const progresso = Math.max(0, Math.min(1, l.progresso || 0));
    console.classList.toggle("attiva", attiva);
    console.classList.toggle("guasto", guasto);
    console.classList.toggle("fermata", fermata);
    console.querySelectorAll(".tappa").forEach((tappa, i) => {
      tappa.className = "tappa";
      if (inCoda) return;
      if (i < corrente) tappa.classList.add("fatta");
      if (i === corrente) tappa.classList.add(guasto ? "guasto" : "corrente");
    });
    const nomeFase = inCoda ? "In coda" : TACCHE[corrente].etichetta;
    $(".riempimento", console).style.setProperty("--p", String(progresso));
    $(".liquido", console).setAttribute("aria-valuenow", String(Math.round(progresso * 100)));
    $(".valore", console).textContent = String(Math.round(progresso * 100));
    $(".fase", console).textContent = guasto ? `Interrotta durante ${nomeFase.toLowerCase()}`
      : fermata ? `Fermata durante ${nomeFase.toLowerCase()}` : nomeFase;
    $(".messaggio", console).textContent = guasto
      ? (l.errore || "Errore sconosciuto")
      : fermata ? "Il lavoro fatto è salvato: Riprendi riparte da qui."
      : (l.messaggio || (inCoda ? "Parte quando finiscono le lezioni prima di questa." : "In corso…"));

    // I tasti cambiano solo con lo stato, non a ogni aggiornamento (non perdono il focus).
    const azioni = $(".azioni", console);
    if (azioni.dataset.stato === l.stato) return;
    azioni.dataset.stato = l.stato;
    if (ATTIVI.has(l.stato)) {
      const tasto = h("button", { class: "tasto ferma", type: "button" }, icona("ferma"), "Ferma");
      tasto.addEventListener("click", () => fermaLezione(tasto));
      azioni.replaceChildren(tasto);
    } else {
      azioni.replaceChildren(h("button", { class: "tasto grande", type: "button", onclick: () => rielabora("riprendi") },
        icona("ricarica"), guasto ? "Riprova da qui" : "Riprendi"));
    }
  }

  async function fermaLezione(tasto) {
    const l = stato.dettaglio.lezione;
    tasto.disabled = true;
    tasto.replaceChildren(icona("orologio"), "Mi fermo…");
    try {
      await api(`/api/lezioni/${l.id}/ferma`, { method: "POST" });
      await aggiornaElenco();
    } catch (e) {
      alert(e.message);
      tasto.disabled = false;
      tasto.replaceChildren(icona("ferma"), "Ferma");
    }
  }

  function vaiA(secondi) {
    const audio = $("#lettore-audio");
    if (!audio) return;
    audio.currentTime = secondi;
    audio.play().catch(() => {});
  }

  /** Il trasporto: tasto play, salti di 15 secondi e la scala di sintonia per scorrere la registrazione. */
  function trasporto(l, audioPrecedente) {
    const audio = audioPrecedente || h("audio", {
      id: "lettore-audio",
      preload: "metadata",
      src: `/api/lezioni/${l.id}/audio`,
      "data-lezione": l.id,
    });
    const tastoPlay = h("button", { class: "tasto tondo grande", type: "button", "aria-label": "Riproduci" }, icona("play"));
    const scala = h("input", { class: "sintonia", type: "range", min: "0", max: "1000", value: "0", step: "1", "aria-label": "Posizione nella registrazione" });
    const letto = h("span", { class: "tempo-letto" }, "0:00");
    const VELOCITA = [1, 1.25, 1.5, 2];
    const velocita = h("button", { class: "tasto velocita", type: "button", title: "Velocità di riproduzione" });
    const impostaVelocita = (v) => {
      audio.playbackRate = v;
      velocita.textContent = `${String(v).replace(".", ",")}×`;
      velocita.setAttribute("aria-label", `Velocità ${String(v).replace(".", ",")} per`);
      try { localStorage.setItem("sbobina-velocita", String(v)); } catch (e) { /* storage pieno */ }
    };
    velocita.addEventListener("click", () => impostaVelocita(VELOCITA[(VELOCITA.indexOf(audio.playbackRate) + 1) % VELOCITA.length] || 1));
    impostaVelocita(Number(localStorage.getItem("sbobina-velocita")) || 1);
    const salto = (delta, nome, etichetta) => h("button", {
      class: "tasto tondo salto", type: "button", "aria-label": etichetta, title: etichetta,
      onclick: () => { audio.currentTime = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + delta)); },
    }, icona(nome));

    const aggiorna = () => {
      const durata = audio.duration || 0;
      letto.textContent = `${formattaOrologio(audio.currentTime)} / ${formattaOrologio(durata)}`;
      if (durata && document.activeElement !== scala) scala.value = String(Math.round((audio.currentTime / durata) * 1000));
      scala.style.setProperty("--pos", `${Number(scala.value) / 10}%`);
    };
    const statoPlay = () => {
      const fermo = audio.paused;
      tastoPlay.replaceChildren(icona(fermo ? "play" : "pausa"));
      tastoPlay.setAttribute("aria-label", fermo ? "Riproduci" : "Pausa");
    };
    // Proprietà, non listener: lo stesso <audio> viene riusato tra un ridisegno e l'altro.
    audio.ontimeupdate = () => { aggiorna(); seguiTrascrizione(audio.currentTime); };
    audio.onloadedmetadata = aggiorna;
    audio.onplay = statoPlay;
    audio.onpause = statoPlay;
    tastoPlay.addEventListener("click", () => (audio.paused ? audio.play().catch(() => {}) : audio.pause()));
    scala.addEventListener("input", () => {
      if (audio.duration) audio.currentTime = (Number(scala.value) / 1000) * audio.duration;
      scala.style.setProperty("--pos", `${Number(scala.value) / 10}%`);
    });
    statoPlay();
    aggiorna();
    return h("div", { class: "trasporto", role: "group", "aria-label": "Registrazione" },
      audio, tastoPlay, salto(-15, "indietro", "Indietro di 15 secondi"), salto(15, "avanti", "Avanti di 15 secondi"), scala, letto, velocita);
  }

  function mostraDettaglio({ conservaAudio = false, anima = !conservaAudio } = {}) {
    stato.vista = "lezione";
    const d = stato.dettaglio;
    const l = d.lezione;
    const precedente = $("#lettore-audio");
    const audioPrecedente = conservaAudio && precedente && precedente.dataset.lezione === l.id ? precedente : null;

    const elementi = [...avvisiConfigurazione()];

    elementi.push(h("header", { class: "intestazione" },
      h("h1", {}, l.titolo),
      h("ul", { class: "legende" },
        h("li", {}, icona("glossario"), l.corso),
        l.data ? h("li", {}, icona("calendario"), formattaData(l.data)) : null,
        l.durata_secondi ? h("li", {}, icona("orologio"), h("span", { class: "dati" }, formattaDurata(l.durata_secondi))) : null,
        l.materiali.length ? h("li", {}, icona("graffetta"), `${l.materiali.length} ${l.materiali.length === 1 ? "materiale" : "materiali"}`) : null)));

    if (ATTIVI.has(l.stato) || l.stato === "errore" || l.stato === "fermata") elementi.push(consoleElaborazione(l));

    if (l.da_approfondire && l.da_approfondire.length && ATTIVI.has(l.stato)) {
      elementi.push(h("div", { class: "avviso" }, icona("onda"),
        h("strong", {}, "Da approfondire"),
        h("ul", {}, l.da_approfondire.map((a) => h("li", {}, a)))));
    }
    if (l.avvisi && l.avvisi.length) {
      elementi.push(h("div", { class: "avviso" }, icona("avviso"),
        h("strong", {}, "Da controllare"),
        h("ul", {}, l.avvisi.map((a) => h("li", {}, a)))));
    }

    if (d.audio) elementi.push(trasporto(l, audioPrecedente));

    const problemi = d.verifica ? d.verifica.problemi.length : null;
    const commutatore = h("div", { class: "commutatore", role: "tablist", "aria-label": "Cosa vuoi vedere" },
      h("span", { class: "cursore", "aria-hidden": "true" }));
    const schede = [["appunti", "Appunti", null], ["approfondimento", "Approfondimento", null], ["trascrizione", "Trascrizione", null], ["verifica", "Verifica", problemi]];
    for (const [chiave, etichetta, conteggio] of schede) {
      commutatore.append(h("button", {
        type: "button",
        role: "tab",
        id: `scheda-${chiave}`,
        "data-scheda": chiave,
        "aria-selected": stato.scheda === chiave ? "true" : "false",
        "aria-controls": "corpo-scheda",
        onclick: () => cambiaScheda(chiave),
      }, etichetta, conteggio !== null ? h("span", { class: "conteggio", "aria-label": `${conteggio} correzioni` }, conteggio) : null));
    }
    elementi.push(commutatore);
    const area = h("div", { class: "area-scheda", id: "area-scheda" });
    riempiScheda(area, d);
    elementi.push(area);

    elementi.push(tastiera(d));
    const piede = [];
    if (l.motori && l.motori.length) piede.push(`Trascrizione: ${l.motori.join(" + ")}`);
    if (d.costo !== null && d.costo !== undefined) piede.push(`Costo stimato di Claude: $${d.costo.toFixed(2)}`);
    if (piede.length) elementi.push(h("p", { class: "piede" }, piede.join(" · ")));

    riempiPiastra(elementi, anima);
    posizionaCursore(commutatore);
    requestAnimationFrame(() => commutatore.classList.add("pronto"));
  }

  function riempiScheda(area, d) {
    const l = d.lezione;
    const foglio = h("section", { class: "foglio", id: "corpo-scheda", role: "tabpanel", "aria-labelledby": `scheda-${stato.scheda}` });
    if (stato.scheda === "appunti") mostraAppunti(foglio, d);
    else if (stato.scheda === "approfondimento") mostraApprofondimento(foglio, d);
    else if (stato.scheda === "trascrizione") mostraTrascrizione(foglio, d);
    else mostraVerifica(foglio, d);
    area.replaceChildren(foglio);
    if (stato.scheda === "approfondimento" && d.approfondimento && l.stato === "completata") area.append(pannelloEspansione(d));
  }

  function posizionaCursore(commutatore) {
    const attivo = commutatore.querySelector('[aria-selected="true"]');
    if (!attivo) return;
    commutatore.style.setProperty("--x", `${attivo.offsetLeft}px`);
    commutatore.style.setProperty("--w", `${attivo.offsetWidth}px`);
  }

  /** Cambia scheda senza ridisegnare la pagina: il cursore scivola e cambia solo il foglio. */
  function cambiaScheda(chiave) {
    if (chiave === stato.scheda) return;
    stato.scheda = chiave;
    const commutatore = $(".commutatore");
    commutatore.querySelectorAll('[role="tab"]').forEach((b) =>
      b.setAttribute("aria-selected", b.dataset.scheda === chiave ? "true" : "false"));
    posizionaCursore(commutatore);
    const area = $("#area-scheda");
    riempiScheda(area, stato.dettaglio);
    area.classList.remove("cambia");
    void area.offsetWidth;
    area.classList.add("cambia");
  }

  /** Illumina il paragrafo della trascrizione che si sta ascoltando. */
  function seguiTrascrizione(secondi, radice = document.querySelector(".appunti.trascrizione")) {
    if (!radice) return;
    let corrente = null;
    for (const par of radice.querySelectorAll(".battuta")) {
      if (Number(par.dataset.secondi) <= secondi + 0.3) corrente = par; else break;
    }
    const prima = radice.querySelector(".battuta.in-ascolto");
    if (prima === corrente) return;
    if (prima) prima.classList.remove("in-ascolto");
    if (!corrente) return;
    corrente.classList.add("in-ascolto");
    const audio = $("#lettore-audio");
    const r = corrente.getBoundingClientRect();
    if (audio && !audio.paused && (r.top < 160 || r.bottom > innerHeight - 40)) {
      corrente.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    }
  }

  function nota(testo) {
    return h("p", { class: "nota" }, icona("info"), h("span", {}, testo));
  }

  function mostraAppunti(foglio, d) {
    if (!d.appunti) {
      foglio.append(h("p", { class: "segnaposto" }, "Gli appunti compaiono qui quando l'elaborazione arriva ad Appunti."));
      return;
    }
    if (d.bozza) foglio.append(nota("Bozza: la verifica con la registrazione è in corso e potrebbe correggerla."));
    const articolo = h("article", { class: "appunti" });
    foglio.append(articolo);
    window.Sbobina.render(articolo, d.appunti, { onTempo: d.audio ? vaiA : null });
  }

  function mostraApprofondimento(foglio, d) {
    const l = d.lezione;
    if (!d.approfondimento) {
      const pronta = l.stato === "completata";
      foglio.append(h("div", { class: "segnaposto" },
        h("p", {}, pronta
          ? "Questa lezione non ha ancora un approfondimento: spiegazioni più ampie, esempi, esercizi e domande d'esame."
          : "L'approfondimento compare qui dopo gli appunti: spiegazioni più ampie, esempi, esercizi e domande d'esame."),
        pronta ? h("button", { class: "tasto grande", type: "button", onclick: () => approfondisci("") },
          icona("onda"), "Crea l'approfondimento") : null));
      return;
    }
    foglio.append(nota("Va oltre il riassunto: spiega il perché, aggiunge esempi ed esercizi. Ciò che non è stato detto a lezione è nei riquadri Integrazione."));
    const articolo = h("article", { class: "appunti" });
    foglio.append(articolo);
    window.Sbobina.render(articolo, d.approfondimento, { onTempo: d.audio ? vaiA : null });
  }

  /** Gli spunti della sezione "Per approfondire ancora", da usare come tasti. */
  function spunti(markdown) {
    const parti = markdown.split(/^##\s+Per approfondire ancora\s*$/m);
    if (parti.length < 2) return [];
    return parti[1].split(/^##\s/m)[0].split("\n")
      .map((riga) => riga.match(/^\s*[-*]\s+(.+)$/))
      .filter(Boolean)
      .map((m) => m[1].replace(/[*_`]/g, "").trim())
      .filter((testo) => testo && testo.length <= 120)
      .slice(0, 6);
  }

  function pannelloEspansione(d) {
    const fatti = new Set([...d.approfondimento.matchAll(/^##\s+Approfondimento:\s*(.+)$/gm)].map((m) => m[1].trim().toLowerCase()));
    const proposte = spunti(d.approfondimento).filter((s) => !fatti.has(s.toLowerCase()));
    const campo = h("input", { name: "argomento", required: true, maxlength: "200", placeholder: "es. la differenza tra imposte e tasse", autocomplete: "off" });
    const errore = h("p", { class: "errore-modulo", role: "alert", hidden: true });
    const form = h("form", { class: "modulo-form" },
      proposte.length ? h("div", { class: "spunti", role: "group", "aria-label": "Argomenti suggeriti" },
        proposte.map((testo) => h("button", { class: "tasto", type: "button", onclick: () => approfondisci(testo, errore) },
          icona("piu"), testo))) : null,
      h("label", { class: "campo" }, h("span", {}, "Oppure scrivi tu cosa approfondire"), campo),
      errore,
      h("div", { class: "azioni-form" },
        h("button", { class: "tasto grande", type: "submit" }, icona("onda"), "Approfondisci")));
    form.addEventListener("submit", (evento) => {
      evento.preventDefault();
      approfondisci(campo.value.trim(), errore);
    });
    return h("section", { class: "pannello", "aria-labelledby": "titolo-espansione" },
      h("h2", { id: "titolo-espansione" }, "Approfondisci ancora"),
      h("p", {}, "Scegli un punto: l'AI aggiunge una nuova sezione all'approfondimento e al PDF. Ci vuole qualche minuto."),
      form);
  }

  async function approfondisci(argomento, errore) {
    const l = stato.dettaglio.lezione;
    try {
      await api(`/api/lezioni/${l.id}/approfondisci`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ argomento }),
      });
      stato.scheda = "approfondimento";
      await aggiornaElenco();
      await apriLezione(l.id, { mantieniScheda: true });
    } catch (e) {
      if (errore) { errore.textContent = e.message; errore.hidden = false; } else alert(e.message);
    }
  }

  /** Scarica il PDF: la prima volta va creato, quindi il tasto mostra l'attesa. */
  async function scaricaPdf(tasto, url, nomeFile) {
    const etichetta = [...tasto.childNodes];
    tasto.disabled = true;
    tasto.replaceChildren(icona("orologio"), ...(tasto.classList.contains("tondo") ? [] : ["Preparo il PDF…"]));
    try {
      if (window.pywebview) {  // app nativa: finestra Salva di macOS
        const esito = await window.pywebview.api.salva(url, nomeFile);
        if (esito && !esito.startsWith("/")) throw new Error(esito);
        return;
      }
      const risposta = await fetch(url);
      if (!risposta.ok) {
        let messaggio = `Errore ${risposta.status}`;
        try { messaggio = (await risposta.json()).detail || messaggio; } catch (e) { /* non JSON */ }
        throw new Error(messaggio);
      }
      const blob = URL.createObjectURL(await risposta.blob());
      const collegamento = h("a", { href: blob, download: nomeFile });
      document.body.append(collegamento);
      collegamento.click();
      collegamento.remove();
      setTimeout(() => URL.revokeObjectURL(blob), 10000);
    } catch (e) {
      alert(e.message);
    } finally {
      tasto.disabled = false;
      tasto.replaceChildren(...etichetta);
    }
  }

  function mostraTrascrizione(foglio, d) {
    if (!d.trascrizione) {
      foglio.append(h("p", { class: "segnaposto" }, "La trascrizione revisionata compare qui dopo la fase di revisione."));
      return;
    }
    foglio.append(nota(d.audio
      ? "Fedele a ciò che è stato detto. Clicca un paragrafo per riascoltarlo: mentre l'audio va, il paragrafo in corso si illumina."
      : "Fedele a ciò che è stato detto, con i termini corretti. [incerto] e [incomprensibile] segnano i punti da riascoltare."));
    const articolo = h("article", { class: "appunti trascrizione" });
    foglio.append(articolo);
    window.Sbobina.render(articolo, d.trascrizione, { onTempo: d.audio ? vaiA : null });
    if (!d.audio) return;
    // Ogni paragrafo che inizia con un tempo diventa un punto dell'audio.
    for (const par of articolo.querySelectorAll("p")) {
      const tempo = par.querySelector(".tempo");
      if (!tempo || par.firstElementChild !== tempo) continue;
      const [a, b, c] = tempo.textContent.replace(/[^\d:]/g, "").split(":").map(Number);
      par.dataset.secondi = String(c === undefined ? a * 60 + b : a * 3600 + b * 60 + c);
      par.classList.add("battuta");
      par.addEventListener("click", (e) => { if (!e.target.closest("a")) vaiA(Number(par.dataset.secondi)); });
    }
    const audio = $("#lettore-audio");
    if (audio) seguiTrascrizione(audio.currentTime, articolo);
  }

  function mostraVerifica(foglio, d) {
    if (!d.verifica) {
      foglio.append(h("p", { class: "segnaposto" },
        stato.info && !stato.info.verifica
          ? "La verifica è disattivata (SBOBINA_VERIFICA=0)."
          : "Il controllo degli appunti con la registrazione compare qui alla fine."));
      return;
    }
    const v = d.verifica;
    const box = h("div", { class: "verifica" });
    foglio.append(box);
    box.append(nota("Prima di consegnarti gli appunti, Sbobina li ha confrontati frase per frase con la trascrizione. I problemi qui sotto sono già corretti nella versione finale."));
    box.append(h("h3", {}, "Giudizio"), h("p", { class: "giudizio" }, v.giudizio));
    box.append(h("h3", {}, v.problemi.length ? `Correzioni fatte (${v.problemi.length})` : "Nessun problema trovato"));
    for (const p of v.problemi) {
      box.append(h("div", { class: `problema ${p.gravita}` },
        h("div", { class: "etichette" },
          h("span", { class: "etichetta" }, TIPI_PROBLEMA[p.tipo] || p.tipo),
          h("span", { class: "etichetta gravita" }, `gravità ${p.gravita}`)),
        h("dl", {},
          h("dt", {}, "Dove"), h("dd", {}, p.posizione),
          h("dt", {}, "Evidenza"), h("dd", {}, p.evidenza),
          h("dt", {}, "Correzione"), h("dd", {}, p.correzione))));
    }
    if (v.termini_chiave && v.termini_chiave.length) {
      box.append(h("h3", {}, "Termini aggiunti al glossario del corso"),
        h("div", { class: "termini" }, v.termini_chiave.map((t) => h("span", {}, t))));
    }
  }

  function tastiera(d) {
    const l = d.lezione;
    const attiva = ATTIVI.has(l.stato);
    const barra = h("div", { class: "tastiera", role: "toolbar", "aria-label": "Azioni sulla lezione" });
    if (l.stato === "completata") {
      const base = `/api/lezioni/${l.id}/scarica/pdf`;
      const nome = `${l.corso} - ${l.titolo}`;
      const tastoPdf = h("button", { class: "tasto grande", type: "button" }, icona("scarica"), "Scarica il PDF");
      tastoPdf.addEventListener("click", () => scaricaPdf(tastoPdf, base, `${nome}.pdf`));
      const variante = (contenuto, titolo, spiegazione) => h("button", { type: "button", onclick: (e) => {
        e.currentTarget.closest("details").removeAttribute("open");
        scaricaPdf(tastoPdf, `${base}?contenuto=${contenuto}`, `${nome}${contenuto === "appunti" ? "" : ` - ${contenuto}`}.pdf`);
      } }, titolo, h("small", {}, spiegazione));
      barra.append(
        tastoPdf,
        h("details", { class: "menu" },
          h("summary", { class: "tasto", role: "button", "aria-label": "Altri PDF" }, icona("stampa"), "Altri PDF"),
          h("div", { class: "voci-menu" },
            variante("appunti", "Solo appunti", "Il PDF da ricopiare nel quaderno."),
            variante("approfondimento", "Appunti + approfondimento", "Con spiegazioni, esempi ed esercizi."),
            variante("trascrizione", "Appunti + trascrizione", "Con il testo completo della lezione."))),
        h("a", { class: "tasto", href: `/api/lezioni/${l.id}/scarica/html`, target: "_blank", rel: "noopener" },
          icona("stampa"), "Stampa"),
        h("a", { class: "tasto", href: `/api/lezioni/${l.id}/scarica/md` }, icona("scarica"), "Markdown"),
        h("a", { class: "tasto", href: `/api/lezioni/${l.id}/scarica/trascrizione` }, icona("scarica"), "Trascrizione"));
    }
    if (!attiva) {
      const voce = (da, titolo, spiegazione) => h("button", { type: "button", onclick: () => rielabora(da) },
        titolo, h("small", {}, spiegazione));
      barra.append(h("details", { class: "menu" },
        h("summary", { class: "tasto", role: "button" }, icona("ricarica"), "Rielabora"),
        h("div", { class: "voci-menu" },
          voce("appunti", "Riscrivi gli appunti", "Dalla trascrizione già revisionata, per esempio dopo aver aggiornato il glossario."),
          voce("revisione", "Rivedi la trascrizione", "Ripete la correzione dei termini e poi gli appunti."),
          voce("tutto", "Ricomincia da capo", "Ritrascrive anche l'audio: richiede più tempo."))));
    }
    barra.append(h("button", { class: "tasto", type: "button", onclick: () => mostraGlossario(l.corso) },
      icona("glossario"), "Glossario"));
    if (l.stato !== "in_elaborazione") {
      barra.append(h("button", { class: "tasto pericolo", type: "button", onclick: eliminaLezione }, icona("cestino"), "Elimina"));
    }
    return barra;
  }

  async function rielabora(da) {
    const l = stato.dettaglio.lezione;
    const conferme = {
      appunti: "Riscrivere gli appunti di questa lezione? Quelli attuali verranno sostituiti.",
      revisione: "Rifare la revisione della trascrizione e gli appunti?",
      tutto: "Ricominciare da capo, trascrizione compresa?",
    };
    if (conferme[da] && !confirm(conferme[da])) return;
    try {
      await api(`/api/lezioni/${l.id}/rielabora`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ da }),
      });
      await aggiornaElenco();
      await apriLezione(l.id);
    } catch (e) {
      alert(e.message);
    }
  }

  async function eliminaLezione() {
    const l = stato.dettaglio.lezione;
    if (!confirm(`Eliminare "${l.titolo}"? Verranno cancellati audio, trascrizione e appunti.`)) return;
    try {
      await api(`/api/lezioni/${l.id}`, { method: "DELETE" });
      stato.selezionata = null;
      stato.dettaglio = null;
      history.replaceState(null, "", location.pathname);
      await aggiornaElenco();
      mostraBenvenuto();
    } catch (e) {
      alert(e.message);
    }
  }

  // --- aggiornamento periodico --------------------------------------------

  async function aggiornaElenco() {
    const precedenti = new Map(stato.lezioni.map((l) => [l.id, l]));
    stato.lezioni = await api("/api/lezioni");
    mostraElenco();
    for (const l of stato.lezioni) {
      const prima = precedenti.get(l.id);
      if (prima && ATTIVI.has(prima.stato) && l.stato === "completata") lezionePronta(l);
    }
    aggiornaBadge();
    const attuale = stato.lezioni.find((l) => l.id === stato.selezionata);
    const prima = precedenti.get(stato.selezionata);
    if (attuale && prima && stato.dettaglio && stato.vista === "lezione") {
      if (attuale.stato !== prima.stato || attuale.fase !== prima.fase) {
        // Nuova fase o fine dell'elaborazione: ricarica (compaiono trascrizione e bozza).
        await apriLezione(attuale.id, { mantieniScheda: true });
      } else {
        const console = $("#console");
        if (console && ATTIVI.has(attuale.stato)) aggiornaConsole(console, attuale);
      }
    }
    programmaAggiornamento();
  }

  function programmaAggiornamento() {
    clearTimeout(stato.timer);
    if (stato.lezioni.some((l) => ATTIVI.has(l.stato))) {
      stato.timer = setTimeout(() => aggiornaElenco().catch(() => programmaAggiornamento()), 3000);
    }
  }

  // --- nuova lezione ----------------------------------------------------------

  function tornaIndietro() {
    if (stato.selezionata && stato.lezioni.some((l) => l.id === stato.selezionata)) apriLezione(stato.selezionata);
    else mostraBenvenuto();
  }

  function vanoFile({ nome, accetta, multiplo, obbligatorio, icona: nomeIcona, titolo, aiuto }) {
    const input = h("input", { type: "file", name: nome, accept: accetta, multiple: multiplo, required: obbligatorio });
    const scelti = h("span", { class: "scelti", "aria-live": "polite" });
    const vano = h("label", { class: "vano" },
      h("span", { class: "pozzetto", "aria-hidden": "true" }, icona(nomeIcona)),
      h("strong", {}, titolo), h("small", { class: "spiegazione" }, aiuto), scelti, input);
    const aggiorna = () => {
      const nomi = [...input.files].map((f) => f.name);
      scelti.textContent = nomi.length > 2 ? `${nomi.length} file scelti` : nomi.join(" · ");
    };
    input.addEventListener("change", aggiorna);
    input.addEventListener("dragenter", () => vano.classList.add("sopra"));
    for (const evento of ["dragleave", "drop"]) input.addEventListener(evento, () => vano.classList.remove("sopra"));
    return { vano, input };
  }

  function mostraNuova(fileIniziali) {
    stato.vista = "nuova";
    const audio = vanoFile({
      nome: "audio", accetta: ACCETTA_AUDIO, multiplo: true, obbligatorio: true, icona: "microfono",
      titolo: "Scegli o trascina la registrazione",
      aiuto: "m4a, mp3, wav e altri formati. Più file diventano più lezioni.",
    });
    const materiali = vanoFile({
      nome: "materiali", accetta: ".pdf,.txt,.md,.jpg,.jpeg,.png,.webp", multiplo: true, obbligatorio: false, icona: "graffetta",
      titolo: "Slide, dispense o foto della lavagna",
      aiuto: "Facoltativi, ma migliorano molto i termini tecnici.",
    });
    const corsi = h("datalist", { id: "elenco-corsi" }, ...(stato.info ? stato.info.corsi : []).map((c) => h("option", { value: c.nome })));
    const campoTitolo = h("input", { name: "titolo", placeholder: "es. Lezione 5, Derivate" });
    audio.input.addEventListener("change", () => {
      const tanti = audio.input.files.length > 1;
      campoTitolo.disabled = tanti;
      campoTitolo.placeholder = tanti ? "Preso dal nome di ogni file" : "es. Lezione 5, Derivate";
    });
    const barra = h("div");
    const testoCaricamento = h("span", {}, "");
    const caricamento = h("div", { class: "meter-caricamento", hidden: true, role: "status" },
      h("div", { class: "barra" }, barra), testoCaricamento);
    const errore = h("p", { class: "errore-modulo", role: "alert", hidden: true });
    const invia = h("button", { class: "tasto grande", type: "submit" }, icona("onda"), "Carica ed elabora");

    const form = h("form", { class: "modulo-form" },
      audio.vano,
      h("div", { class: "due" },
        h("label", { class: "campo" }, h("span", {}, "Corso"),
          h("input", { name: "corso", list: "elenco-corsi", required: true, placeholder: "es. Diritto privato", autocomplete: "off",
            value: stato.dettaglio ? stato.dettaglio.lezione.corso : null }), corsi),
        h("label", { class: "campo" }, h("span", {}, "Data"),
          h("input", { type: "date", name: "data", value: new Date().toISOString().slice(0, 10) }))),
      h("label", { class: "campo" }, h("span", {}, "Titolo ", h("small", {}, "(facoltativo)")), campoTitolo),
      h("details", { class: "facoltativi" },
        h("summary", {}, icona("freccia"), "Aggiungi slide, termini difficili o indicazioni"),
        h("div", { class: "campi" },
          materiali.vano,
          h("label", { class: "campo" }, h("span", {}, "Nomi e termini difficili"),
            h("textarea", { name: "termini", rows: "2", placeholder: "Nome del docente, autori, sigle, termini tecnici, separati da virgola" })),
          h("label", { class: "campo" }, h("span", {}, "Indicazioni per gli appunti"),
            h("textarea", { name: "note", rows: "2", placeholder: "es. argomento della lezione, cose su cui insistere" })))),
      caricamento,
      errore,
      h("div", { class: "azioni-form" },
        h("button", { class: "tasto", type: "button", onclick: tornaIndietro }, "Annulla"),
        invia));
    form.addEventListener("submit", (evento) => inviaNuova(evento, { barra, testoCaricamento, caricamento, errore, invia }));

    riempiPiastra([
      ...avvisiConfigurazione(),
      h("section", { class: "pannello", "aria-labelledby": "titolo-nuova" },
        h("h2", { id: "titolo-nuova" }, "Nuova lezione"),
        h("p", {}, "Scegli l'audio e il corso. Al resto pensa Sbobina, sul tuo computer."),
        form)]);
    if (fileIniziali && fileIniziali.length) {
      const trasferimento = new DataTransfer();
      for (const file of fileIniziali) trasferimento.items.add(file);
      audio.input.files = trasferimento.files;
      audio.input.dispatchEvent(new Event("change"));
      form.querySelector('[name="corso"]').focus();
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function inviaNuova(evento, { barra, testoCaricamento, caricamento, errore, invia }) {
    evento.preventDefault();
    const form = evento.target;
    const dati = new FormData(form);
    errore.hidden = true;
    caricamento.hidden = false;
    invia.disabled = true;

    const mostraErrore = (messaggio) => {
      invia.disabled = false;
      caricamento.hidden = true;
      errore.textContent = messaggio;
      errore.hidden = false;
    };

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/lezioni");
    xhr.setRequestHeader("X-Sbobina", "1");
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const p = Math.round((e.loaded / e.total) * 100);
      barra.style.width = `${p}%`;
      testoCaricamento.textContent = `Caricamento ${p}%`;
    };
    xhr.upload.onload = () => { testoCaricamento.textContent = "Salvataggio…"; };
    xhr.onerror = () => mostraErrore("Connessione con Sbobina interrotta. Controlla che il server sia ancora acceso e riprova.");
    xhr.onload = async () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const create = JSON.parse(xhr.responseText);
        stato.info = await api("/api/stato");
        await aggiornaElenco();
        if (create.length) await apriLezione(create[0].id);
      } else {
        let messaggio = `Errore ${xhr.status}`;
        try { messaggio = JSON.parse(xhr.responseText).detail || messaggio; } catch (e) { /* non JSON */ }
        mostraErrore(typeof messaggio === "string" ? messaggio : JSON.stringify(messaggio));
      }
    };
    xhr.send(dati);
  }

  // --- glossario ----------------------------------------------------------

  async function mostraGlossario(corso) {
    let dati;
    try {
      dati = await api(`/api/glossario?corso=${encodeURIComponent(corso)}`);
    } catch (e) {
      alert(e.message);
      return;
    }
    stato.vista = "glossario";
    const area = h("textarea", { name: "termini", rows: "14", "aria-describedby": "spiega-glossario" });
    area.value = dati.termini.join("\n");
    const errore = h("p", { class: "errore-modulo", role: "alert", hidden: true });
    const form = h("form", { class: "modulo-form" },
      h("label", { class: "campo" }, h("span", {}, "Un termine per riga"), area),
      errore,
      h("div", { class: "azioni-form" },
        h("button", { class: "tasto", type: "button", onclick: tornaIndietro }, "Annulla"),
        h("button", { class: "tasto grande", type: "submit" }, icona("spunta"), "Salva il glossario")));
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const termini = area.value.split("\n").map((t) => t.trim()).filter(Boolean);
      try {
        await api("/api/glossario", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ corso, termini }),
        });
        stato.info = await api("/api/stato");
        tornaIndietro();
      } catch (e) {
        errore.textContent = e.message;
        errore.hidden = false;
      }
    });
    riempiPiastra([h("section", { class: "pannello", "aria-labelledby": "titolo-glossario" },
      h("h2", { id: "titolo-glossario" }, `Glossario di ${corso}`),
      h("p", { id: "spiega-glossario" },
        "Questi termini aiutano il riconoscimento vocale e l'AI a scriverli giusti. Il glossario cresce da solo dopo ogni lezione: aggiungi il nome del docente o correggi una grafia sbagliata."),
      form)]);
    area.focus();
  }

  // --- impostazioni -------------------------------------------------------

  const imp = () => (stato.info && stato.info.impostazioni) || {};

  /** Tema, accento, dimensione del testo e movimento dalle impostazioni. */
  function applicaAspetto(i = imp()) {
    const radice = document.documentElement;
    if (i.tema && i.tema !== "sistema") radice.dataset.tema = i.tema; else delete radice.dataset.tema;
    if (i.accento && i.accento !== "blu") radice.dataset.accento = i.accento; else delete radice.dataset.accento;
    if (i.animazioni_ridotte) radice.dataset.movimento = "ridotto"; else delete radice.dataset.movimento;
    radice.style.fontSize = i.scala_testo && i.scala_testo !== 100 ? `${i.scala_testo}%` : "";
    if (window.pywebview && window.pywebview.api.tema) {
      const scuro = i.tema === "scuro" || (i.tema !== "chiaro" && matchMedia("(prefers-color-scheme: dark)").matches);
      window.pywebview.api.tema(scuro);
    }
  }

  async function salvaImpostazioni(modifiche) {
    const salvate = await api("/api/impostazioni", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(modifiche),
    });
    if (stato.info) stato.info.impostazioni = salvate;
    applicaAspetto(salvate);
    return salvate;
  }

  /** Un gruppo di pillole a scelta singola (radio accessibili). */
  function scelte(nome, opzioni, valore, onCambia) {
    const gruppo = h("div", { class: "scelte", role: "radiogroup" });
    for (const [chiave, etichetta, aiuto] of opzioni) {
      const input = h("input", { type: "radio", name: nome, value: chiave, checked: chiave === valore });
      input.addEventListener("change", () => input.checked && onCambia(chiave));
      gruppo.append(h("label", { class: "scelta", title: aiuto || null }, input, h("span", {}, etichetta)));
    }
    return gruppo;
  }

  function interruttore(etichetta, valore, onCambia, aiuto) {
    const input = h("input", { type: "checkbox", role: "switch", checked: !!valore });
    input.addEventListener("change", () => onCambia(input.checked));
    return h("label", { class: "interruttore" },
      h("span", { class: "testo" }, h("span", {}, etichetta), aiuto ? h("small", {}, aiuto) : null),
      input, h("span", { class: "levetta", "aria-hidden": "true" }));
  }

  function riga(titolo, aiuto, controllo) {
    return h("div", { class: "riga-imp" },
      h("div", { class: "riga-testo" }, h("strong", {}, titolo), aiuto ? h("small", {}, aiuto) : null),
      controllo);
  }

  let avvisoSalvato = null;
  function salvato(testo = "Salvato") {
    if (!avvisoSalvato) {
      avvisoSalvato = h("div", { class: "brindisi", role: "status", "aria-live": "polite" });
      document.body.append(avvisoSalvato);
    }
    avvisoSalvato.textContent = testo;
    avvisoSalvato.classList.remove("mostra");
    void avvisoSalvato.offsetWidth;
    avvisoSalvato.classList.add("mostra");
  }

  /** Salva subito una modifica e mostra "Salvato" (o l'errore). */
  function cambia(modifiche, dopo) {
    salvaImpostazioni(modifiche)
      .then((s) => { salvato(); if (dopo) dopo(s); })
      .catch((e) => salvato(e.message));
  }

  const ETICHETTE_SEZIONI = {
    mappa: ["Mappa concettuale", "L'albero dei concetti all'inizio degli appunti"],
    schemi: ["Schemi e diagrammi", "Flussi e classificazioni disegnati quando aiutano"],
    domande: ["Domande di ripasso", "8-15 domande con risposta a scomparsa"],
    glossario: ["Glossario", "I termini tecnici della lezione in tabella"],
    indicazioni: ["Indicazioni del docente", "Esame, cose importanti, avvisi"],
    approfondimento: ["Approfondimento automatico", "Spiegazioni più ampie, esempi ed esercizi (più tempo)"],
    verifica: ["Verifica con l'audio", "Ricontrolla gli appunti frase per frase (più tempo, più precisione)"],
  };
  const NOMI_AREE = {
    economia: "Economia", giurisprudenza: "Giurisprudenza", ingegneria: "Ingegneria", medicina: "Medicina",
    umanistica: "Umanistica", scienze: "Scienze", altro: "Altro",
  };

  /** Le schede dei modelli adatti a questo Mac, con quello consigliato in evidenza. */
  function schedeModelli(sistema, valore, onCambia) {
    const gruppo = h("div", { class: "modelli", role: "radiogroup", "aria-label": "Modello che scrive gli appunti" });
    for (const m of sistema.modelli) {
      const input = h("input", { type: "radio", name: "modello", value: m.tag, checked: m.tag === valore, disabled: !m.adatto });
      input.addEventListener("change", () => input.checked && onCambia(m.tag));
      gruppo.append(h("label", { class: `modello${m.adatto ? "" : " inadatto"}` },
        input,
        h("span", { class: "modello-testa" },
          h("strong", {}, m.nome),
          m.consigliato ? h("span", { class: "distintivo" }, "Consigliato") : null,
          m.installato ? h("span", { class: "distintivo pieno" }, "Scaricato") : null),
        h("span", { class: "modello-dati" }, `${m.gb.toLocaleString("it-IT")} GB · da ${m.ram} GB di memoria`),
        h("small", {}, m.adatto ? m.descrizione : `Serve un Mac con almeno ${m.ram} GB di memoria.`)));
    }
    return gruppo;
  }

  /** Avanzamento della preparazione dell'AI (download dei modelli), aggiornato da /api/stato. */
  function pannelloPreparazione(onPronta) {
    const barra = h("div", { class: "riempimento" });
    const testo = h("p", { class: "messaggio" }, "");
    const tasto = h("button", { class: "tasto grande", type: "button" }, icona("scarica"), "Scarica e prepara");
    const box = h("div", { class: "preparazione-box" },
      h("div", { class: "liquido" }, barra), testo, h("div", { class: "azioni" }, tasto));
    let timer = null;
    const aggiorna = async () => {
      clearTimeout(timer);
      try { stato.info = await api("/api/stato"); } catch (e) { return; }
      const p = stato.info.preparazione || {};
      barra.style.setProperty("--p", String(stato.info.llm && !p.attiva ? 1 : p.progresso || 0));
      box.classList.toggle("attiva", !!p.attiva);
      if (p.attiva) {
        testo.textContent = p.messaggio || "Preparo…";
        tasto.disabled = true;
        timer = setTimeout(aggiorna, 900);
      } else if (p.errore) {
        testo.textContent = p.errore;
        tasto.disabled = false;
        tasto.replaceChildren(icona("ricarica"), "Riprova");
      } else if (stato.info.llm) {
        testo.textContent = "Tutto pronto: i modelli sono sul tuo Mac.";
        tasto.hidden = true;
        mostraStatoAI();
        if (onPronta) onPronta();
      } else {
        testo.textContent = "Una volta sola: scarico i modelli sul tuo Mac. Puoi continuare a usare il computer.";
        tasto.disabled = false;
        tasto.hidden = false;
      }
    };
    tasto.addEventListener("click", async () => {
      tasto.disabled = true;
      await api("/api/ai/prepara", { method: "POST" });
      aggiorna();
    });
    aggiorna();
    return box;
  }

  async function mostraImpostazioni() {
    let sistema;
    try {
      [sistema, stato.info] = await Promise.all([api("/api/sistema"), api("/api/stato")]);
    } catch (e) {
      alert(e.message);
      return;
    }
    stato.vista = "impostazioni";
    const i = imp();
    const sezione = (id, titolo, testo, ...figli) => h("section", { class: "pannello imp", "aria-labelledby": id },
      h("h2", { id }, titolo), testo ? h("p", {}, testo) : null, ...figli);

    // AI: motore, modello, chiave, Whisper
    const zonaAI = h("div", { class: "zona-ai" });
    const disegnaAI = () => {
      const c = imp();
      const mac = sistema.mac;
      const pezzi = [
        riga("Chi scrive gli appunti", "Integrato e Ollama sono gratuiti e restano sul Mac; Claude è a pagamento.",
          scelte("motore", [
            ["mlx", "Integrato", "Il modello gira dentro Sbobina, senza altri programmi"],
            ["ollama", "Ollama", "Usa l'app Ollama installata sul Mac"],
            ["claude", "Claude", "API di Anthropic, a pagamento"]], c.motore_llm,
            (v) => cambia({ motore_llm: v }, disegnaAI))),
      ];
      if (c.motore_llm === "claude") {
        const chiave = h("input", { type: "password", value: c.chiave_claude || "", placeholder: "sk-ant-…", autocomplete: "off", spellcheck: "false" });
        chiave.addEventListener("change", () => cambia({ chiave_claude: chiave.value.trim() }));
        pezzi.push(h("label", { class: "campo" }, h("span", {}, "Chiave API di Claude"), chiave,
          h("small", {}, "Resta solo su questo Mac, nel file impostazioni.json.")));
      } else {
        pezzi.push(h("p", { class: "mac" }, icona("info"),
          `${mac.chip} · ${mac.ram_gb} GB di memoria · ${mac.disco_libero_gb.toLocaleString("it-IT")} GB liberi`),
        schedeModelli(sistema, c.modello || sistema.consigliato, (v) => cambia({ modello: v }, disegnaAI)));
      }
      pezzi.push(riga("Riconoscimento vocale", "Il modello Whisper che trascrive l'audio.",
        scelte("whisper", sistema.whisper.map((w) => [w.id, w.nome, w.descrizione]), c.whisper || "large-v3-turbo",
          (v) => cambia({ whisper: v }))));
      pezzi.push(pannelloPreparazione());
      zonaAI.replaceChildren(...pezzi);
    };
    disegnaAI();

    const temperatura = h("input", { type: "range", min: "0", max: "1.2", step: "0.1", value: String(i.temperatura) });
    const valoreTemp = h("output", { class: "dati" }, String(i.temperatura).replace(".", ","));
    temperatura.addEventListener("input", () => { valoreTemp.textContent = temperatura.value.replace(".", ","); });
    temperatura.addEventListener("change", () => cambia({ temperatura: Number(temperatura.value) }));
    const istruzioni = h("textarea", { rows: "4", maxlength: "2000", placeholder: "es. Usa esempi tratti dal bilancio di aziende italiane. Scrivi le formule anche a parole." });
    istruzioni.value = i.prompt_extra || "";
    istruzioni.addEventListener("change", () => cambia({ prompt_extra: istruzioni.value }));

    const scala = h("input", { type: "range", min: "80", max: "140", step: "5", value: String(i.scala_testo) });
    const valoreScala = h("output", { class: "dati" }, `${i.scala_testo}%`);
    scala.addEventListener("input", () => {
      valoreScala.textContent = `${scala.value}%`;
      document.documentElement.style.fontSize = `${scala.value}%`;
    });
    scala.addEventListener("change", () => cambia({ scala_testo: Number(scala.value) }));

    const accenti = h("div", { class: "accenti", role: "radiogroup", "aria-label": "Colore di accento" },
      [["blu", "Blu"], ["indaco", "Indaco"], ["azzurro", "Azzurro"], ["verde", "Verde acqua"]].map(([chiave, nome]) => {
        const input = h("input", { type: "radio", name: "accento", value: chiave, checked: (i.accento || "blu") === chiave, "aria-label": nome });
        input.addEventListener("change", () => input.checked && cambia({ accento: chiave }));
        return h("label", { class: `campione ${chiave}`, title: nome }, input);
      }));

    const campoProfilo = (nome, etichetta, segnaposto) => {
      const input = h("input", { value: i[nome] || "", placeholder: segnaposto, autocomplete: "off" });
      input.addEventListener("change", () => cambia({ [nome]: input.value }));
      return h("label", { class: "campo" }, h("span", {}, etichetta), input);
    };

    riempiPiastra([
      h("header", { class: "intestazione" }, h("h1", {}, "Impostazioni"),
        h("p", { class: "sottotitolo" }, "Ogni modifica si salva subito e vale dalla prossima lezione.")),
      sezione("imp-appunti", "Appunti", "Come vuoi che siano scritti.",
        riga("Lunghezza", null, scelte("lunghezza", [["essenziale", "Essenziale"], ["normale", "Normale"], ["dettagliata", "Dettagliata"]],
          i.lunghezza, (v) => cambia({ lunghezza: v }))),
        riga("Stile", null, scelte("stile", [["discorsivo", "Discorsivo"], ["schematico", "Schematico"]],
          i.stile, (v) => cambia({ stile: v }))),
        h("div", { class: "griglia-interruttori" },
          Object.entries(ETICHETTE_SEZIONI).map(([chiave, [titolo, aiuto]]) =>
            interruttore(titolo, (i.sezioni || {})[chiave] !== false, (v) => cambia({ sezioni: { [chiave]: v } }), aiuto)))),
      sezione("imp-ai", "Intelligenza artificiale", null, zonaAI,
        h("details", { class: "facoltativi avanzate" },
          h("summary", {}, icona("freccia"), "Impostazioni avanzate"),
          h("div", { class: "campi" },
            riga("Creatività", "Bassa = più fedele alla lezione. Consigliato 0,3.", h("div", { class: "cursore-valore" }, temperatura, valoreTemp)),
            riga("Memoria per lezione", "Quanta lezione il modello legge insieme. Automatica in base al tuo Mac.",
              scelte("contesto", [["0", "Auto"], ["32768", "32 mila"], ["65536", "64 mila"], ["131072", "128 mila"]],
                String(i.contesto || 0), (v) => cambia({ contesto: Number(v) }))),
            h("label", { class: "campo" }, h("span", {}, "Istruzioni personali per gli appunti"), istruzioni,
              h("small", {}, "Si aggiungono alle regole di Sbobina; la fedeltà alla lezione resta prioritaria."))))),
      sezione("imp-profilo", "Il tuo profilo", "Aiuta l'AI a scrivere nel modo giusto per la tua materia.",
        h("div", { class: "due" }, campoProfilo("nome", "Nome", "es. Leonardo"), campoProfilo("universita", "Università", "es. Università di Firenze")),
        campoProfilo("corso_di_laurea", "Corso di laurea", "es. Economia aziendale"),
        riga("Area di studio", null, scelte("area", sistema.aree.map((a) => [a, NOMI_AREE[a] || a]), i.area, (v) => cambia({ area: v }))),
        riga("Anno", null, scelte("anno", sistema.anni.map((a) => [a, a]), i.anno, (v) => cambia({ anno: v })))),
      sezione("imp-pdf", "PDF", "Cosa mettere nel PDF quando premi Scarica.",
        scelte("pdf", [["appunti", "Solo appunti"], ["approfondimento", "Appunti + approfondimento"], ["trascrizione", "Con la trascrizione"]],
          i.pdf, (v) => cambia({ pdf: v }))),
      sezione("imp-aspetto", "Aspetto", null,
        riga("Tema", null, scelte("tema", [["sistema", "Come il Mac"], ["chiaro", "Chiaro"], ["scuro", "Scuro"]], i.tema, (v) => cambia({ tema: v }))),
        riga("Colore", null, accenti),
        riga("Dimensione del testo", "Vale per appunti e trascrizioni.", h("div", { class: "cursore-valore" }, scala, valoreScala)),
        interruttore("Riduci le animazioni", i.animazioni_ridotte, (v) => cambia({ animazioni_ridotte: v }), "Utile se il movimento ti distrae.")),
      sezione("imp-fine", "Quando una lezione è pronta", null,
        h("div", { class: "griglia-interruttori" },
          interruttore("Notifica", i.notifiche, (v) => { cambia({ notifiche: v }); if (v) chiediPermessoNotifiche(); }, "Anche se Sbobina è in secondo piano."),
          interruttore("Suono", i.suono, (v) => { cambia({ suono: v }); if (v) suonoFine(); }, "Un breve accordo."))),
      sezione("imp-dati", "I tuoi dati", "Audio, trascrizioni e appunti restano in questa cartella, sul tuo Mac.",
        h("div", { class: "riga-dati" },
          h("code", {}, sistema.cartella_dati),
          h("button", { class: "tasto", type: "button", onclick: () => api("/api/cartella-dati", { method: "POST" }) },
            icona("graffetta"), "Mostra nel Finder"))),
    ]);
  }

  // --- fine lezione: notifica, suono, badge -------------------------------

  function chiediPermessoNotifiche() {
    if (!window.pywebview && "Notification" in window && Notification.permission === "default") Notification.requestPermission();
  }

  /** Un accordo breve e morbido (do-mi-sol), generato: nessun file audio. */
  function suonoFine() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [523.25, 659.25, 783.99].forEach((f, n) => {
        const osc = ctx.createOscillator();
        const vol = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = f;
        const t0 = ctx.currentTime + n * 0.09;
        vol.gain.setValueAtTime(0, t0);
        vol.gain.linearRampToValueAtTime(0.12, t0 + 0.02);
        vol.gain.exponentialRampToValueAtTime(0.0001, t0 + 1.1);
        osc.connect(vol).connect(ctx.destination);
        osc.start(t0);
        osc.stop(t0 + 1.2);
      });
    } catch (e) { /* audio non disponibile */ }
  }

  function lezionePronta(l) {
    const i = imp();
    if (i.suono !== false) suonoFine();
    if (i.notifiche === false) return;
    const titolo = "Appunti pronti";
    const testo = `${l.titolo} · ${l.corso}`;
    if (window.pywebview && window.pywebview.api.notifica) window.pywebview.api.notifica(titolo, testo);
    else if ("Notification" in window && Notification.permission === "granted" && document.hidden) new Notification(titolo, { body: testo });
  }

  function aggiornaBadge() {
    const attive = stato.lezioni.filter((l) => ATTIVI.has(l.stato)).length;
    if (window.pywebview && window.pywebview.api.badge) window.pywebview.api.badge(attive ? String(attive) : "");
    document.title = attive ? `(${attive}) Sbobina` : "Sbobina";
  }

  // --- primo avvio ----------------------------------------------------------

  async function mostraPrimoAvvio(passo = 0) {
    let sistema;
    try { sistema = await api("/api/sistema"); } catch (e) { mostraBenvenuto(); return; }
    stato.vista = "primo-avvio";
    const i = imp();
    const TOT = 4;
    const avanti = (n) => mostraPrimoAvvio(n);
    const punti = h("ol", { class: "passi", "aria-label": `Passo ${passo + 1} di ${TOT}` },
      Array.from({ length: TOT }, (_, n) => h("li", { class: n < passo ? "fatto" : n === passo ? "corrente" : "" })));
    const piede = (...tasti) => h("div", { class: "azioni-form" }, ...tasti);
    const indietro = passo > 0 ? h("button", { class: "tasto", type: "button", onclick: () => avanti(passo - 1) }, "Indietro") : null;
    let corpo;

    if (passo === 0) {
      corpo = [
        h("h1", {}, "Ciao, sono ", h("em", {}, "Sbobina.")),
        h("p", { class: "sottotitolo" }, "Trasformo le registrazioni delle lezioni in appunti chiari, con schemi, glossario e domande di ripasso. Lavoro tutto sul tuo Mac: gratis, senza account, e l'audio non esce dal computer."),
        h("p", { class: "sottotitolo" }, "Ti faccio tre domande e preparo l'AI. Ci vogliono un paio di minuti più il download."),
        piede(h("button", { class: "tasto grande", type: "button", onclick: () => avanti(1) }, icona("freccia"), "Iniziamo")),
      ];
    } else if (passo === 1) {
      const nome = h("input", { value: i.nome || "", placeholder: "Come ti chiami?", autocomplete: "given-name" });
      const uni = h("input", { value: i.universita || "", placeholder: "es. Università di Firenze" });
      const cdl = h("input", { value: i.corso_di_laurea || "", placeholder: "es. Economia aziendale" });
      let area = i.area || "economia";
      let anno = i.anno || "1";
      corpo = [
        h("h1", {}, "Parlami dei tuoi studi"),
        h("p", { class: "sottotitolo" }, "Così gli appunti usano il linguaggio giusto per la tua materia."),
        h("div", { class: "due" },
          h("label", { class: "campo" }, h("span", {}, "Nome"), nome),
          h("label", { class: "campo" }, h("span", {}, "Università"), uni)),
        h("label", { class: "campo" }, h("span", {}, "Corso di laurea"), cdl),
        riga("Area di studio", null, scelte("area", sistema.aree.map((a) => [a, NOMI_AREE[a] || a]), area, (v) => { area = v; })),
        riga("Anno", null, scelte("anno", sistema.anni.map((a) => [a, a]), anno, (v) => { anno = v; })),
        piede(indietro, h("button", { class: "tasto grande", type: "button", onclick: async () => {
          await salvaImpostazioni({ nome: nome.value, universita: uni.value, corso_di_laurea: cdl.value, area, anno });
          avanti(2);
        } }, icona("freccia"), "Avanti")),
      ];
    } else if (passo === 2) {
      const mac = sistema.mac;
      let motore = mac.apple_silicon ? "mlx" : "ollama";
      let modello = sistema.consigliato;
      corpo = [
        h("h1", {}, "Scegliamo l'AI per il tuo Mac"),
        h("p", { class: "mac" }, icona("info"), `${mac.chip} · ${mac.ram_gb} GB di memoria · ${mac.disco_libero_gb.toLocaleString("it-IT")} GB liberi`),
        mac.apple_silicon
          ? riga("Dove gira", "Integrato non richiede altri programmi. Ollama se lo usi già.",
              scelte("motore", [["mlx", "Integrato (consigliato)"], ["ollama", "Ollama"]], motore, (v) => { motore = v; }))
          : null,
        schedeModelli(sistema, modello, (v) => { modello = v; }),
        piede(indietro, h("button", { class: "tasto grande", type: "button", onclick: async () => {
          await salvaImpostazioni({ motore_llm: motore, modello, whisper: "large-v3-turbo" });
          avanti(3);
        } }, icona("freccia"), "Avanti")),
      ];
    } else {
      const fine = h("button", { class: "tasto grande", type: "button", disabled: true, onclick: async () => {
        await salvaImpostazioni({ configurato: true });
        mostraBenvenuto();
      } }, icona("spunta"), "Inizia a usare Sbobina");
      const prep = pannelloPreparazione(() => { fine.disabled = false; });
      corpo = [
        h("h1", {}, "Preparo l'AI"),
        h("p", { class: "sottotitolo" }, "Scarico il modello che scrive gli appunti e quello che riconosce la voce. Succede una volta sola."),
        prep,
        piede(indietro,
          h("button", { class: "tasto", type: "button", onclick: async () => { await salvaImpostazioni({ configurato: true }); mostraBenvenuto(); } }, "Lo faccio dopo"),
          fine),
      ];
      // Parte da solo: lo studente ha già scelto tutto.
      setTimeout(() => { const t = prep.querySelector(".tasto.grande"); if (t && !t.hidden && !t.disabled) t.click(); }, 400);
    }
    riempiPiastra([h("section", { class: "pannello primo-avvio" }, punti, ...corpo)]);
  }

  // --- avvio --------------------------------------------------------------

  function collegaEventi() {
    $("#btn-nuova").addEventListener("click", () => mostraNuova());
    $("#btn-impostazioni").addEventListener("click", mostraImpostazioni);
    $("#marchio").addEventListener("click", (e) => {
      e.preventDefault();
      stato.selezionata = null;
      history.replaceState(null, "", location.pathname);
      mostraElenco();
      mostraBenvenuto();
    });
    $("#cerca").addEventListener("input", (e) => { stato.filtro = e.target.value; mostraElenco(); });
    window.addEventListener("resize", () => { const c = $(".commutatore"); if (c) posizionaCursore(c); });
    window.addEventListener("hashchange", () => {
      const id = location.hash.slice(1);
      if (id && id !== stato.selezionata && stato.lezioni.some((l) => l.id === id)) apriLezione(id);
    });
    document.addEventListener("click", (e) => {
      document.querySelectorAll("details.menu[open]").forEach((menu) => {
        if (!menu.contains(e.target)) menu.removeAttribute("open");
      });
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") document.querySelectorAll("details.menu[open]").forEach((m) => m.removeAttribute("open"));
    });
  }

  async function avvia() {
    collegaEventi();
    try {
      await aggiornaInfo();
      await aggiornaElenco();
    } catch (e) {
      $("#contenuto").replaceChildren(h("div", { class: "avviso grave", role: "alert" }, icona("avviso"),
        h("strong", {}, "Non riesco a contattare Sbobina."),
        h("span", {}, `Controlla che il server sia acceso (sbobina server) e ricarica la pagina. Dettaglio: ${e.message}`)));
      return;
    }
    const daHash = location.hash.slice(1);
    if (daHash === "impostazioni") mostraImpostazioni();
    else if (daHash === "primo-avvio" || (!imp().configurato && !stato.lezioni.length)) mostraPrimoAvvio();
    else if (daHash && stato.lezioni.some((l) => l.id === daHash)) await apriLezione(daHash);
    else mostraBenvenuto();
  }

  // App nativa: i collegamenti di download passano dalla finestra Salva di macOS.
  document.addEventListener("click", async (evento) => {
    const a = evento.target.closest("a[href^='/api/']");
    if (!a || !window.pywebview || a.target === "_blank") return;
    evento.preventDefault();
    const esito = await window.pywebview.api.salva(a.getAttribute("href"), "");
    if (esito && !esito.startsWith("/")) alert(esito);
  });

  avvia();
})();
