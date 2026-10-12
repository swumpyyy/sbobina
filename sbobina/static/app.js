/* Sbobina: interfaccia web (pannello hi-fi). */
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
  // Le tacche del selettore. Il server salva la fase come etichetta ("Revisione della trascrizione"):
  // ogni tacca riconosce le etichette dall'inizio.
  const TACCHE = [
    { etichetta: "Preparazione", inizi: ["preparazione", "analisi"] },
    { etichetta: "Trascrizione", inizi: ["trascrizione"] },
    { etichetta: "Revisione", inizi: ["revisione"] },
    { etichetta: "Appunti", inizi: ["scrittura", "appunti"] },
    { etichetta: "Verifica", inizi: ["verifica", "correzione"] },
    { etichetta: "Approfondimento", inizi: ["approfondimento"] },
  ];
  const ANGOLI = [-125, -75, -25, 25, 75, 125];
  const ANGOLO_CODA = -150;
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
    if (info.locale) testo = pronta ? ["AI locale", h("span", { class: "testo-lungo" }, " · gratuita")] : ["AI non pronta"];
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
      avvisi.push(h("div", { class: "avviso", role: "status" }, icona("info"),
        h("strong", {}, "L'AI che scrive gli appunti non è ancora pronta."),
        h("ol", {},
          h("li", {}, "Apri l'app Ollama (resta attiva nella barra dei menu)."),
          h("li", {}, "Nel Terminale esegui ", h("code", {}, `ollama pull ${info.modello}`), " (una volta sola, circa 8 GB)."),
          h("li", {}, "Questa spia si accende da sola quando il modello è pronto."))));
    } else if (!info.llm) {
      avvisi.push(h("div", { class: "avviso", role: "status" }, icona("info"),
        h("strong", {}, "Manca la chiave di Claude."),
        h("span", {}, "Aggiungi ANTHROPIC_API_KEY al file .env, oppure torna al modello locale gratuito.")));
    }
    return avvisi;
  }

  async function aggiornaInfo() {
    try {
      const prima = stato.info && stato.info.llm;
      stato.info = await api("/api/stato");
      mostraStatoAI();
      if (prima === false && stato.info.llm && stato.vista === "benvenuto") mostraBenvenuto();
    } catch (e) { /* server momentaneamente irraggiungibile */ }
    clearTimeout(stato.timerInfo);
    if (stato.info && !stato.info.llm) stato.timerInfo = setTimeout(aggiornaInfo, 10000);
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
              l.stato === "errore" ? h("span", {}, "· da riprovare") : null);
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
    const piastra = $("#contenuto");
    const ciSonoLezioni = stato.lezioni.length > 0;
    const passo = (nome, titolo, testo) => h("li", {},
      h("span", { class: "pozzetto", "aria-hidden": "true" }, icona(nome)), h("strong", {}, titolo), h("span", {}, testo));
    piastra.replaceChildren(
      ...avvisiConfigurazione(),
      h("section", { class: "benvenuto" },
        h("h1", {}, ciSonoLezioni ? "Scegli una lezione, oppure caricane una nuova." : "Dalla registrazione agli appunti, gratis sul tuo computer."),
        h("p", {}, "Sbobina trascrive l'audio della lezione, corregge i termini tecnici con le tue slide, scrive appunti con schemi e domande di ripasso e li ricontrolla con la registrazione. Tutto in locale: niente account, niente costi."),
        h("ol", { class: "percorso" },
          passo("microfono", "Carica la registrazione", "Note vocali, registratore, Teams o Zoom. Puoi aggiungere slide e dispense."),
          passo("onda", "Lascia lavorare", "Il selettore mostra la fase, l'indicatore quanto manca. Puoi chiudere e tornare dopo."),
          passo("stampa", "Studia e stampa", "Leggi a schermo, riascolta dal punto giusto, stampa il PDF da ricopiare.")),
        h("button", { class: "tasto grande", type: "button", onclick: mostraNuova }, icona("piu"),
          ciSonoLezioni ? "Nuova lezione" : "Carica la prima lezione")));
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

  /** Il selettore di fase con le sue tacche e il VU-metro. */
  function consoleElaborazione(l) {
    const guasto = l.stato === "errore";
    const selettore = h("div", { class: "selettore", role: "img" },
      h("div", { class: "anello" }),
      h("div", { class: "manopola" }),
      ...TACCHE.map((t, i) => {
        const radianti = (ANGOLI[i] * Math.PI) / 180;
        return h("span", {
          class: "tacca",
          style: `left:${50 + 44 * Math.sin(radianti)}%;top:${50 - 44 * Math.cos(radianti)}%`,
        }, t.etichetta);
      }));

    const tacche = [];
    for (let i = 0; i <= 40; i++) {
      const gradi = -90 + i * 4.5;
      const r = (gradi * Math.PI) / 180;
      const lunga = i % 5 === 0;
      const interno = lunga ? 96 : 106;
      tacche.push(`<line class="tick" data-i="${i}" x1="${160 + interno * Math.sin(r)}" y1="${150 - interno * Math.cos(r)}" x2="${160 + 126 * Math.sin(r)}" y2="${150 - 126 * Math.cos(r)}"/>`);
    }
    const quadrante = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    quadrante.setAttribute("viewBox", "0 0 320 165");
    quadrante.setAttribute("aria-hidden", "true");
    quadrante.innerHTML = `${tacche.join("")}<line class="lancetta" x1="160" y1="150" x2="160" y2="58"/><circle class="perno" cx="160" cy="150" r="7"/>`;

    const vu = h("div", { class: "vu" },
      quadrante,
      h("div", { class: "lettura" },
        h("span", { class: "valore" }),
        h("span", { class: "fase", "aria-live": "polite" })),
      h("p", { class: "messaggio" }));

    const console = h("section", { class: `pannello console${guasto ? " guasto" : ""}`, id: "console", "aria-label": "Elaborazione" },
      selettore, vu);
    if (guasto) {
      console.append(h("div", { class: "azioni" },
        h("button", { class: "tasto grande", type: "button", onclick: () => rielabora("riprendi") },
          icona("ricarica"), "Riprova da dove si era fermata")));
    }
    aggiornaConsole(console, l);
    return console;
  }

  function aggiornaConsole(console, l) {
    const inCoda = l.stato === "in_coda";
    const guasto = l.stato === "errore";
    const corrente = indiceTacca(l.fase);
    const progresso = Math.max(0, Math.min(1, l.progresso || 0));
    $(".manopola", console).style.setProperty("--angolo", `${inCoda ? ANGOLO_CODA : ANGOLI[corrente]}deg`);
    console.querySelectorAll(".tacca").forEach((tacca, i) => {
      tacca.className = "tacca";
      if (inCoda) return;
      if (i < corrente) tacca.classList.add("fatta");
      if (i === corrente) tacca.classList.add(guasto ? "guasto" : "corrente");
    });
    const nomeFase = inCoda ? "In coda" : TACCHE[corrente].etichetta;
    $(".selettore", console).setAttribute("aria-label", guasto ? `Interrotta durante: ${nomeFase}` : `Fase: ${nomeFase}`);
    const accese = Math.round(progresso * 40);
    console.querySelectorAll(".tick").forEach((t) => t.classList.toggle("acceso", Number(t.dataset.i) <= accese && accese > 0));
    $(".lancetta", console).style.transform = `rotate(${-90 + progresso * 180}deg)`;
    $(".valore", console).textContent = percentuale(progresso);
    $(".fase", console).textContent = guasto ? `Interrotta · ${nomeFase}` : nomeFase;
    $(".messaggio", console).textContent = guasto
      ? (l.errore || "Errore sconosciuto")
      : (l.messaggio || (inCoda ? "Parte quando finiscono le lezioni prima di questa." : "In corso…"));
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
    const salto = (delta, nome, etichetta) => h("button", {
      class: "tasto tondo salto", type: "button", "aria-label": etichetta, title: etichetta,
      onclick: () => { audio.currentTime = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + delta)); },
    }, icona(nome));

    const aggiorna = () => {
      const durata = audio.duration || 0;
      letto.textContent = `${formattaOrologio(audio.currentTime)} / ${formattaOrologio(durata)}`;
      if (durata && document.activeElement !== scala) scala.value = String(Math.round((audio.currentTime / durata) * 1000));
    };
    const statoPlay = () => {
      const fermo = audio.paused;
      tastoPlay.replaceChildren(icona(fermo ? "play" : "pausa"));
      tastoPlay.setAttribute("aria-label", fermo ? "Riproduci" : "Pausa");
    };
    // Proprietà, non listener: lo stesso <audio> viene riusato tra un ridisegno e l'altro.
    audio.ontimeupdate = aggiorna;
    audio.onloadedmetadata = aggiorna;
    audio.onplay = statoPlay;
    audio.onpause = statoPlay;
    tastoPlay.addEventListener("click", () => (audio.paused ? audio.play().catch(() => {}) : audio.pause()));
    scala.addEventListener("input", () => {
      if (audio.duration) audio.currentTime = (Number(scala.value) / 1000) * audio.duration;
    });
    statoPlay();
    aggiorna();
    return h("div", { class: "trasporto", role: "group", "aria-label": "Registrazione" },
      audio, tastoPlay, salto(-15, "indietro", "Indietro di 15 secondi"), salto(15, "avanti", "Avanti di 15 secondi"), scala, letto);
  }

  function mostraDettaglio({ conservaAudio = false } = {}) {
    stato.vista = "lezione";
    const d = stato.dettaglio;
    const l = d.lezione;
    const precedente = $("#lettore-audio");
    const audioPrecedente = conservaAudio && precedente && precedente.dataset.lezione === l.id ? precedente : null;

    const piastra = $("#contenuto");
    const elementi = [...avvisiConfigurazione()];

    elementi.push(h("header", { class: "intestazione" },
      h("h1", {}, l.titolo),
      h("ul", { class: "legende" },
        h("li", {}, icona("glossario"), l.corso),
        l.data ? h("li", {}, icona("calendario"), formattaData(l.data)) : null,
        l.durata_secondi ? h("li", {}, icona("orologio"), h("span", { class: "dati" }, formattaDurata(l.durata_secondi))) : null,
        l.materiali.length ? h("li", {}, icona("graffetta"), `${l.materiali.length} ${l.materiali.length === 1 ? "materiale" : "materiali"}`) : null)));

    if (ATTIVI.has(l.stato) || l.stato === "errore") elementi.push(consoleElaborazione(l));

    if (l.da_approfondire && l.da_approfondire.length && ATTIVI.has(l.stato)) {
      elementi.push(h("div", { class: "avviso" }, icona("onda"),
        h("strong", {}, "Da approfondire"),
        h("ul", { style: "margin:4px 0 0;padding-left:18px" }, l.da_approfondire.map((a) => h("li", {}, a)))));
    }
    if (l.avvisi && l.avvisi.length) {
      elementi.push(h("div", { class: "avviso" }, icona("avviso"),
        h("strong", {}, "Da controllare"),
        h("ul", { style: "margin:4px 0 0;padding-left:18px" }, l.avvisi.map((a) => h("li", {}, a)))));
    }

    if (d.audio) elementi.push(trasporto(l, audioPrecedente));

    const problemi = d.verifica ? d.verifica.problemi.length : null;
    const commutatore = h("div", { class: "commutatore", role: "tablist", "aria-label": "Cosa vuoi vedere" });
    const schede = [["appunti", "Appunti", null], ["approfondimento", "Approfondimento", null], ["trascrizione", "Trascrizione", null], ["verifica", "Verifica", problemi]];
    for (const [chiave, etichetta, conteggio] of schede) {
      commutatore.append(h("button", {
        type: "button",
        role: "tab",
        id: `scheda-${chiave}`,
        "aria-selected": stato.scheda === chiave ? "true" : "false",
        "aria-controls": "corpo-scheda",
        onclick: () => { stato.scheda = chiave; mostraDettaglio({ conservaAudio: true }); },
      }, etichetta, conteggio !== null ? h("span", { class: "conteggio", "aria-label": `${conteggio} correzioni` }, conteggio) : null));
    }
    elementi.push(commutatore);

    const foglio = h("section", { class: "foglio", id: "corpo-scheda", role: "tabpanel", "aria-labelledby": `scheda-${stato.scheda}` });
    if (stato.scheda === "appunti") mostraAppunti(foglio, d);
    else if (stato.scheda === "approfondimento") mostraApprofondimento(foglio, d);
    else if (stato.scheda === "trascrizione") mostraTrascrizione(foglio, d);
    else mostraVerifica(foglio, d);
    elementi.push(foglio);
    if (stato.scheda === "approfondimento" && d.approfondimento && l.stato === "completata") elementi.push(pannelloEspansione(d));

    elementi.push(tastiera(d));
    const piede = [];
    if (l.motori && l.motori.length) piede.push(`Trascrizione: ${l.motori.join(" + ")}`);
    if (d.costo !== null && d.costo !== undefined) piede.push(`Costo stimato di Claude: $${d.costo.toFixed(2)}`);
    if (piede.length) elementi.push(h("p", { class: "piede" }, piede.join(" · ")));

    piastra.replaceChildren(...elementi);
  }

  function nota(testo) {
    return h("p", { class: "nota" }, icona("info"), h("span", {}, testo));
  }

  function mostraAppunti(foglio, d) {
    if (!d.appunti) {
      foglio.append(h("p", { class: "segnaposto" }, "Gli appunti compaiono qui quando il selettore arriva ad Appunti."));
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
  async function scaricaPdf(tasto, l) {
    const etichetta = [...tasto.childNodes];
    tasto.disabled = true;
    tasto.replaceChildren(icona("orologio"), "Preparo il PDF…");
    try {
      const risposta = await fetch(`/api/lezioni/${l.id}/scarica/pdf`);
      if (!risposta.ok) {
        let messaggio = `Errore ${risposta.status}`;
        try { messaggio = (await risposta.json()).detail || messaggio; } catch (e) { /* non JSON */ }
        throw new Error(messaggio);
      }
      const url = URL.createObjectURL(await risposta.blob());
      const collegamento = h("a", { href: url, download: `${l.corso} - ${l.titolo}.pdf` });
      document.body.append(collegamento);
      collegamento.click();
      collegamento.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
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
    foglio.append(nota("Fedele a ciò che è stato detto, con i termini corretti. [incerto] e [incomprensibile] segnano i punti da riascoltare."));
    const articolo = h("article", { class: "appunti" });
    foglio.append(articolo);
    window.Sbobina.render(articolo, d.trascrizione, { onTempo: d.audio ? vaiA : null });
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
      const tastoPdf = h("button", { class: "tasto grande", type: "button" }, icona("scarica"), "Scarica il PDF");
      tastoPdf.addEventListener("click", () => scaricaPdf(tastoPdf, l));
      barra.append(
        tastoPdf,
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

  function mostraNuova() {
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
    materiali.vano.style.padding = "22px";
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

    $("#contenuto").replaceChildren(
      ...avvisiConfigurazione(),
      h("section", { class: "pannello", "aria-labelledby": "titolo-nuova" },
        h("h2", { id: "titolo-nuova" }, "Nuova lezione"),
        h("p", {}, "Scegli l'audio e il corso. Al resto pensa Sbobina, sul tuo computer."),
        form));
    window.scrollTo({ top: 0 });
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
    $("#contenuto").replaceChildren(h("section", { class: "pannello", "aria-labelledby": "titolo-glossario" },
      h("h2", { id: "titolo-glossario" }, `Glossario di ${corso}`),
      h("p", { id: "spiega-glossario" },
        "Questi termini aiutano il riconoscimento vocale e l'AI a scriverli giusti. Il glossario cresce da solo dopo ogni lezione: aggiungi il nome del docente o correggi una grafia sbagliata."),
      form));
    area.focus();
  }

  // --- avvio --------------------------------------------------------------

  function collegaEventi() {
    $("#btn-nuova").addEventListener("click", mostraNuova);
    $("#marchio").addEventListener("click", (e) => {
      e.preventDefault();
      stato.selezionata = null;
      history.replaceState(null, "", location.pathname);
      mostraElenco();
      mostraBenvenuto();
    });
    $("#cerca").addEventListener("input", (e) => { stato.filtro = e.target.value; mostraElenco(); });
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
    if (daHash && stato.lezioni.some((l) => l.id === daHash)) await apriLezione(daHash);
    else mostraBenvenuto();
  }

  avvia();
})();
