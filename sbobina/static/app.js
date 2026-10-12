/* Sbobina — interfaccia web. */
(function () {
  "use strict";

  const $ = (selettore, radice = document) => radice.querySelector(selettore);
  const ATTIVI = new Set(["in_coda", "in_elaborazione"]);
  const ETICHETTE_STATO = {
    in_coda: "In coda",
    in_elaborazione: "In elaborazione",
    completata: "Pronta",
    errore: "Errore",
  };
  const TIPI_PROBLEMA = {
    non_supportato: "Non detto a lezione",
    errato: "Errato",
    omesso: "Mancante",
    integrazione_errata: "Integrazione errata",
    schema: "Schema",
    formato: "Formato",
  };

  const stato = {
    info: null,
    lezioni: [],
    selezionata: null,
    dettaglio: null,
    scheda: "appunti",
    filtro: "",
    timer: null,
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

  function formattaData(iso) {
    if (!iso) return "";
    const data = new Date(`${iso}T12:00:00`);
    if (Number.isNaN(data.getTime())) return iso;
    return new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "short", year: "numeric" }).format(data);
  }

  function percentuale(valore) {
    return `${Math.round((valore || 0) * 100)}%`;
  }

  // --- avvisi di configurazione -------------------------------------------

  function mostraConfigurazione() {
    const box = $("#avvisi-configurazione");
    box.replaceChildren();
    const info = stato.info;
    if (!info) return;
    if (!info.ffmpeg) {
      box.append(h("div", { class: "avviso errore" },
        "ffmpeg non è installato: serve per leggere l'audio. Installalo e riavvia Sbobina."));
    }
    if (!info.claude) {
      box.append(h("div", { class: "avviso" },
        "Non trovo la chiave di Anthropic. Aggiungi ", h("code", {}, "ANTHROPIC_API_KEY"),
        " al file ", h("code", {}, ".env"), " (oppure accedi con ", h("code", {}, "ant auth login"),
        ") e riavvia: senza Claude le lezioni non possono diventare appunti."));
    }
    if (info.motori.length === 1 && info.motori[0] === "whisper") {
      box.append(h("div", { class: "avviso" },
        "Trascrizione in locale con Whisper: gratuita ma lenta su computer senza GPU. Per la massima accuratezza ",
        "aggiungi ", h("code", {}, "ASSEMBLYAI_API_KEY"), " e/o ", h("code", {}, "ELEVENLABS_API_KEY"),
        " al file .env (con entrambe, le due trascrizioni vengono confrontate tra loro)."));
    }
  }

  // --- elenco lezioni -----------------------------------------------------

  function mostraElenco() {
    const nav = $("#elenco");
    nav.replaceChildren();
    const filtro = stato.filtro.trim().toLowerCase();
    const lezioni = stato.lezioni.filter((l) =>
      !filtro || l.titolo.toLowerCase().includes(filtro) || l.corso.toLowerCase().includes(filtro));
    if (!stato.lezioni.length) {
      nav.append(h("p", { class: "vuoto-elenco" }, "Nessuna lezione: caricane una per iniziare."));
      return;
    }
    if (!lezioni.length) {
      nav.append(h("p", { class: "vuoto-elenco" }, "Nessun risultato."));
      return;
    }
    const perCorso = new Map();
    for (const l of lezioni) {
      if (!perCorso.has(l.corso)) perCorso.set(l.corso, []);
      perCorso.get(l.corso).push(l);
    }
    for (const corso of [...perCorso.keys()].sort((a, b) => a.localeCompare(b, "it"))) {
      const gruppo = h("div", { class: "gruppo-corso" }, h("h3", {}, corso));
      for (const l of perCorso.get(corso)) {
        const sotto = ATTIVI.has(l.stato)
          ? h("span", { class: "sotto" },
              h("span", { class: `stato ${l.stato}` }, ETICHETTE_STATO[l.stato]),
              h("span", { class: "mini-progresso" }, h("div", { style: `width:${percentuale(l.progresso)}` })))
          : h("span", { class: "sotto" },
              h("span", {}, formattaData(l.data)),
              l.durata_secondi ? h("span", {}, `· ${formattaDurata(l.durata_secondi)}`) : null,
              l.stato !== "completata" ? h("span", { class: `stato ${l.stato}` }, ETICHETTE_STATO[l.stato]) : null);
        gruppo.append(h("button", {
          class: `voce${l.id === stato.selezionata ? " attiva" : ""}`,
          type: "button",
          onclick: () => apriLezione(l.id),
        }, h("span", { class: "titolo" }, l.titolo), sotto));
      }
      nav.append(gruppo);
    }
  }

  function mostraBenvenuto() {
    $("#contenuto").replaceChildren(h("div", { class: "benvenuto" },
      h("h1", {}, "Dalle registrazioni agli appunti"),
      h("p", {}, "Carica l'audio di una lezione: Sbobina lo trascrive, corregge i termini tecnici con le slide del corso, " +
        "scrive appunti completi con schemi e mappe concettuali e poi li ricontrolla contro la registrazione."),
      h("div", { class: "passi" },
        h("div", { class: "passo" }, h("b", {}, "1. Carica"), "La registrazione (anche più file) e, se li hai, slide o dispense."),
        h("div", { class: "passo" }, h("b", {}, "2. Attendi"), "Trascrizione, revisione, appunti e verifica: segui l'avanzamento qui."),
        h("div", { class: "passo" }, h("b", {}, "3. Studia"), "Clicca su un tempo ⏱ per riascoltare quel punto della lezione.")),
      h("button", { class: "primario", type: "button", onclick: apriDialogoNuova }, "+ Carica la prima lezione")));
  }

  // --- dettaglio lezione --------------------------------------------------

  async function apriLezione(id, { mantieniScheda = false } = {}) {
    const stessaLezione = stato.selezionata === id;
    stato.selezionata = id;
    if (!mantieniScheda) stato.scheda = "appunti";
    if (location.hash !== `#${id}`) history.replaceState(null, "", `#${id}`);
    mostraElenco();
    try {
      stato.dettaglio = await api(`/api/lezioni/${id}`);
    } catch (e) {
      stato.selezionata = null;
      history.replaceState(null, "", location.pathname);
      mostraBenvenuto();
      return;
    }
    mostraDettaglio({ conservaAudio: stessaLezione });
  }

  function schedaStato(l) {
    if (l.stato === "errore") {
      return h("div", { class: "scheda-stato errore", id: "scheda-stato" },
        h("div", { class: "riga" }, h("span", { class: "fase" }, "Elaborazione interrotta")),
        h("div", { class: "messaggio" }, l.errore || "Errore sconosciuto"),
        h("div", { class: "azioni" },
          h("button", { class: "primario", type: "button", onclick: () => rielabora("riprendi") },
            "Riprova da dove si era fermata")));
    }
    if (!ATTIVI.has(l.stato)) return null;
    return h("div", { class: "scheda-stato", id: "scheda-stato" },
      h("div", { class: "riga" },
        h("span", { class: "fase" }, l.stato === "in_coda" ? "In coda" : (l.fase || "Elaborazione")),
        h("span", { class: "percentuale" }, percentuale(l.progresso))),
      h("div", { class: "progresso" }, h("div", { style: `width:${percentuale(l.progresso)}` })),
      h("div", { class: "messaggio" }, l.messaggio || (l.stato === "in_coda" ? "In attesa che finiscano le lezioni precedenti." : "")));
  }

  function aggiornaSchedaStato(riassunto) {
    const scheda = $("#scheda-stato");
    if (!scheda || !ATTIVI.has(riassunto.stato)) return;
    $(".fase", scheda).textContent = riassunto.stato === "in_coda" ? "In coda" : (riassunto.fase || "Elaborazione");
    $(".percentuale", scheda).textContent = percentuale(riassunto.progresso);
    $(".progresso div", scheda).style.width = percentuale(riassunto.progresso);
    $(".messaggio", scheda).textContent = riassunto.messaggio || "";
  }

  function vaiA(secondi) {
    const audio = $("#lettore-audio");
    if (!audio) return;
    audio.currentTime = secondi;
    audio.play().catch(() => {});
  }

  function mostraDettaglio({ conservaAudio = false } = {}) {
    const d = stato.dettaglio;
    const l = d.lezione;
    // Se si ridisegna la stessa lezione (cambio scheda o nuova fase) si riusa lo stesso <audio>:
    // spostarlo nel DOM nello stesso ciclo non interrompe l'ascolto.
    const precedente = $("#lettore-audio");
    const audioPrecedente = conservaAudio && precedente && precedente.dataset.lezione === l.id ? precedente : null;

    const contenuto = $("#contenuto");
    const centrale = h("div", { class: "centrale" });
    contenuto.replaceChildren(centrale);

    centrale.append(h("div", { class: "intestazione-lezione" },
      h("h1", {}, l.titolo),
      h("div", { class: "meta-lezione" },
        h("span", {}, l.corso),
        h("span", {}, formattaData(l.data)),
        l.durata_secondi ? h("span", {}, formattaDurata(l.durata_secondi)) : null,
        l.materiali.length ? h("span", {}, `${l.materiali.length} materiali`) : null)));

    const scheda = schedaStato(l);
    if (scheda) centrale.append(scheda);
    if (l.avvisi && l.avvisi.length) {
      centrale.append(h("div", { class: "avviso", style: "margin-top:14px" },
        h("strong", {}, "Da controllare: "),
        h("ul", { style: "margin:6px 0 0;padding-left:18px" }, l.avvisi.map((a) => h("li", {}, a)))));
    }

    if (d.audio) {
      const audio = audioPrecedente || h("audio", {
        id: "lettore-audio",
        controls: true,
        preload: "metadata",
        src: `/api/lezioni/${l.id}/audio`,
        "data-lezione": l.id,
      });
      centrale.append(h("div", { class: "lettore" }, audio));
    }

    const problemi = d.verifica ? d.verifica.problemi.length : null;
    const schede = [
      ["appunti", "Appunti", null],
      ["trascrizione", "Trascrizione", null],
      ["verifica", "Verifica", problemi],
    ];
    const barraSchede = h("div", { class: "schede", role: "tablist" });
    for (const [chiave, etichetta, conteggio] of schede) {
      barraSchede.append(h("button", {
        type: "button",
        role: "tab",
        class: stato.scheda === chiave ? "attiva" : "",
        "aria-selected": stato.scheda === chiave ? "true" : "false",
        onclick: () => { stato.scheda = chiave; mostraDettaglio({ conservaAudio: true }); },
      }, etichetta, conteggio !== null ? h("span", { class: "conteggio" }, conteggio) : null));
    }
    centrale.append(barraSchede);

    const corpo = h("div", { class: "corpo-scheda" });
    centrale.append(corpo);
    if (stato.scheda === "appunti") mostraAppunti(corpo, d);
    else if (stato.scheda === "trascrizione") mostraTrascrizione(corpo, d);
    else mostraVerifica(corpo, d);

    centrale.append(barraAzioni(d));
    const piede = [];
    if (l.motori && l.motori.length) piede.push(`Trascrizione: ${l.motori.join(" + ")}`);
    if (d.costo !== null && d.costo !== undefined) piede.push(`Costo Claude stimato: $${d.costo.toFixed(2)}`);
    if (piede.length) centrale.append(h("div", { class: "piede" }, piede.join(" · ")));
  }

  function mostraAppunti(corpo, d) {
    if (!d.appunti) {
      corpo.append(h("p", { class: "segnaposto" }, "Gli appunti compariranno qui al termine dell'elaborazione."));
      return;
    }
    if (d.bozza) {
      corpo.append(h("p", { class: "nota-bozza" },
        "Questa è la bozza: la verifica con la trascrizione è in corso e potrebbe correggerla."));
    }
    const articolo = h("article", { class: "appunti" });
    corpo.append(articolo);
    window.Sbobina.render(articolo, d.appunti, { onTempo: d.audio ? vaiA : null });
  }

  function mostraTrascrizione(corpo, d) {
    if (!d.trascrizione) {
      corpo.append(h("p", { class: "segnaposto" }, "La trascrizione revisionata comparirà qui."));
      return;
    }
    corpo.append(h("p", { class: "nota-bozza" },
      "Trascrizione revisionata da Claude: fedele a ciò che è stato detto, con i termini corretti. " +
      "[incerto] e [incomprensibile] segnano i punti da riascoltare."));
    const articolo = h("article", { class: "appunti" });
    corpo.append(articolo);
    window.Sbobina.render(articolo, d.trascrizione, { onTempo: d.audio ? vaiA : null });
  }

  function mostraVerifica(corpo, d) {
    if (!d.verifica) {
      corpo.append(h("p", { class: "segnaposto" },
        stato.info && !stato.info.verifica
          ? "La verifica è disattivata (SBOBINA_VERIFICA=0)."
          : "Il controllo di accuratezza comparirà qui."));
      return;
    }
    const v = d.verifica;
    const box = h("div", { class: "verifica" });
    corpo.append(box);
    box.append(h("p", { class: "nota-bozza" },
      "Prima di consegnarti gli appunti, Claude li ha confrontati frase per frase con la trascrizione. " +
      "I problemi elencati qui sotto sono stati corretti nella versione finale."));
    box.append(h("h3", {}, "Giudizio del revisore"), h("p", { class: "giudizio" }, v.giudizio));
    box.append(h("h3", {}, v.problemi.length ? `Problemi corretti (${v.problemi.length})` : "Nessun problema trovato"));
    for (const p of v.problemi) {
      box.append(h("div", { class: `problema ${p.gravita}` },
        h("div", { class: "etichette" },
          h("span", { class: "stato" }, TIPI_PROBLEMA[p.tipo] || p.tipo),
          h("span", { class: "stato" }, `gravità ${p.gravita}`)),
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

  function barraAzioni(d) {
    const l = d.lezione;
    const attiva = ATTIVI.has(l.stato);
    const barra = h("div", { class: "azioni-lezione" });
    if (l.stato === "completata") {
      barra.append(
        h("a", { class: "bottone", href: `/api/lezioni/${l.id}/scarica/html`, target: "_blank", rel: "noopener" },
          "Versione stampabile / PDF"),
        h("a", { class: "bottone", href: `/api/lezioni/${l.id}/scarica/md` }, "Scarica Markdown"),
        h("a", { class: "bottone", href: `/api/lezioni/${l.id}/scarica/trascrizione` }, "Scarica trascrizione"));
    }
    if (!attiva) {
      const voce = (da, titolo, spiegazione) => h("button", { type: "button", onclick: () => rielabora(da) },
        titolo, h("small", {}, spiegazione));
      barra.append(h("details", { class: "menu" },
        h("summary", { class: "bottone secondario", role: "button" }, "Rielabora ▾"),
        h("div", { class: "voci-menu" },
          voce("appunti", "Riscrivi gli appunti", "Dalla trascrizione già revisionata (es. dopo aver aggiornato il glossario)."),
          voce("revisione", "Rivedi la trascrizione", "Ripete la correzione dei termini e poi gli appunti."),
          voce("tutto", "Ricomincia da capo", "Ritrascrive anche l'audio (costa come una lezione nuova)."))));
    }
    barra.append(h("button", { class: "secondario", type: "button", onclick: () => apriGlossario(l.corso) },
      "Glossario del corso"));
    if (l.stato !== "in_elaborazione") {
      barra.append(h("button", { class: "pericolo", type: "button", onclick: eliminaLezione }, "Elimina"));
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
    if (attuale && prima && stato.dettaglio) {
      if (attuale.stato !== prima.stato || attuale.fase !== prima.fase) {
        // Nuova fase o fine dell'elaborazione: ricarica (es. compaiono trascrizione e bozza).
        await apriLezione(attuale.id, { mantieniScheda: true });
      } else {
        aggiornaSchedaStato(attuale);
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

  // --- nuova lezione ------------------------------------------------------

  function apriDialogoNuova() {
    const form = $("#form-nuova");
    form.reset();
    form.elements.data.value = new Date().toISOString().slice(0, 10);
    form.elements.titolo.disabled = false;
    $(".errore-modulo", form).hidden = true;
    $(".caricamento", form).hidden = true;
    $("button[type=submit]", form).disabled = false;
    $("#elenco-corsi").replaceChildren(...(stato.info ? stato.info.corsi : []).map((c) => h("option", { value: c.nome })));
    if (stato.dettaglio) form.elements.corso.value = stato.dettaglio.lezione.corso;
    $("#dialogo-nuova").showModal();
  }

  function inviaNuova(evento) {
    evento.preventDefault();
    const form = evento.target;
    const dati = new FormData(form);
    const errore = $(".errore-modulo", form);
    const caricamento = $(".caricamento", form);
    const barra = $(".progresso div", caricamento);
    const testo = $("span", caricamento);
    const invia = $("button[type=submit]", form);
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
      testo.textContent = `Caricamento ${p}%…`;
    };
    xhr.upload.onload = () => { testo.textContent = "Salvataggio…"; };
    xhr.onerror = () => mostraErrore("Connessione con Sbobina interrotta.");
    xhr.onload = async () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const create = JSON.parse(xhr.responseText);
        $("#dialogo-nuova").close();
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

  async function apriGlossario(corso) {
    const form = $("#form-glossario");
    try {
      const dati = await api(`/api/glossario?corso=${encodeURIComponent(corso)}`);
      form.dataset.corso = corso;
      $("h2", form).textContent = `Glossario · ${corso}`;
      form.elements.termini.value = dati.termini.join("\n");
      $("#dialogo-glossario").showModal();
    } catch (e) {
      alert(e.message);
    }
  }

  async function salvaGlossario(evento) {
    evento.preventDefault();
    const form = evento.target;
    const termini = form.elements.termini.value.split("\n").map((t) => t.trim()).filter(Boolean);
    try {
      await api("/api/glossario", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ corso: form.dataset.corso, termini }),
      });
      $("#dialogo-glossario").close();
      stato.info = await api("/api/stato");
    } catch (e) {
      alert(e.message);
    }
  }

  // --- avvio --------------------------------------------------------------

  function collegaEventi() {
    $("#btn-nuova").addEventListener("click", apriDialogoNuova);
    $("#form-nuova").addEventListener("submit", inviaNuova);
    $("#form-glossario").addEventListener("submit", salvaGlossario);
    document.querySelectorAll("dialog [data-chiudi]").forEach((b) =>
      b.addEventListener("click", () => b.closest("dialog").close()));
    $("#cerca").addEventListener("input", (e) => { stato.filtro = e.target.value; mostraElenco(); });
    $("#form-nuova").elements.audio.addEventListener("change", (e) => {
      const titolo = $("#form-nuova").elements.titolo;
      titolo.disabled = e.target.files.length > 1;
      titolo.placeholder = e.target.files.length > 1 ? "Preso dal nome di ogni file" : "es. Lezione 5 – Derivate";
    });
    document.addEventListener("click", (e) => {
      document.querySelectorAll("details.menu[open]").forEach((menu) => {
        if (!menu.contains(e.target)) menu.removeAttribute("open");
      });
    });
  }

  async function avvia() {
    collegaEventi();
    try {
      stato.info = await api("/api/stato");
      mostraConfigurazione();
      await aggiornaElenco();
    } catch (e) {
      $("#avvisi-configurazione").replaceChildren(h("div", { class: "avviso errore" },
        `Impossibile contattare Sbobina: ${e.message}`));
      return;
    }
    const daHash = location.hash.slice(1);
    if (daHash && stato.lezioni.some((l) => l.id === daHash)) await apriLezione(daHash);
    else mostraBenvenuto();
  }

  avvia();
})();
