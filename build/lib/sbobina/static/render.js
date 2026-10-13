/* Rendering degli appunti: Markdown + formule (KaTeX) + schemi (Mermaid) + mappe concettuali (SVG proprio)
   + tempi cliccabili. Usato sia dall'app sia dalle pagine HTML esportate. */
(function () {
  "use strict";

  const RE_TEMPO = /(⏱️?\s?)(\d{1,2}:\d{2}(?::\d{2})?)|\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g;
  const RE_SOLO_TEMPO = /^\s*⏱️?\s?(\d{1,2}:\d{2}(?::\d{2})?)\s*$/;
  let mermaidPronto = false;
  let contatoreSchemi = 0;

  function secondi(testo) {
    return testo.split(":").map(Number).reduce((totale, parte) => totale * 60 + parte, 0);
  }

  function escapeHtml(testo) {
    return testo.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }

  // Le formule vanno tolte prima del Markdown, altrimenti _ e * dentro il LaTeX diventano corsivi.
  function proteggiFormule(md) {
    const formule = [];
    const segnaposto = (tex, display) => {
      formule.push({ tex, display });
      return `@@FORMULA${formule.length - 1}@@`;
    };
    // Gli indici pari sono testo normale, quelli dispari blocchi o frammenti di codice.
    const parti = md.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
    for (let i = 0; i < parti.length; i += 2) {
      parti[i] = parti[i]
        .replace(/\$\$([\s\S]+?)\$\$/g, (_, tex) => segnaposto(tex, true))
        .replace(/\\\[([\s\S]+?)\\\]/g, (_, tex) => segnaposto(tex, true))
        .replace(/\\\(([\s\S]+?)\\\)/g, (_, tex) => segnaposto(tex, false))
        .replace(/(^|[^\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\d)/g, (_, prima, tex) => prima + segnaposto(tex, false));
    }
    return { md: parti.join(""), formule };
  }

  function rendiFormule(html, formule) {
    return html.replace(/@@FORMULA(\d+)@@/g, (_, i) => {
      const f = formule[Number(i)];
      if (!f || !window.katex) return f ? escapeHtml(f.tex) : "";
      try {
        return window.katex.renderToString(f.tex, { displayMode: f.display, throwOnError: false, strict: "ignore" });
      } catch (e) {
        return `<code>${escapeHtml(f.tex)}</code>`;
      }
    });
  }

  function creaTempo(etichetta, valore, onTempo) {
    const el = document.createElement(onTempo ? "a" : "span");
    el.className = "tempo";
    el.textContent = etichetta;
    el.dataset.t = String(secondi(valore));
    if (onTempo) {
      el.href = "#";
      el.title = "Ascolta da qui";
      el.addEventListener("click", (evento) => {
        evento.preventDefault();
        onTempo(secondi(valore));
      });
    }
    return el;
  }

  function collegaTempi(radice, onTempo) {
    // `⏱ 12:34` scritto come codice inline
    radice.querySelectorAll("code").forEach((code) => {
      if (code.closest("pre")) return;
      const m = code.textContent.match(RE_SOLO_TEMPO);
      if (m) code.replaceWith(creaTempo(m[1], m[1], onTempo));
    });
    const walker = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT, {
      acceptNode(nodo) {
        return nodo.parentElement.closest("pre, code, a, svg, .katex, .mappa, .schema, .tempo")
          ? NodeFilter.FILTER_REJECT
          : NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodi = [];
    while (walker.nextNode()) nodi.push(walker.currentNode);
    for (const nodo of nodi) {
      const testo = nodo.nodeValue;
      RE_TEMPO.lastIndex = 0;
      if (!RE_TEMPO.test(testo)) continue;
      RE_TEMPO.lastIndex = 0;
      const frammento = document.createDocumentFragment();
      let ultimo = 0;
      let m;
      while ((m = RE_TEMPO.exec(testo)) !== null) {
        frammento.append(testo.slice(ultimo, m.index));
        const valore = m[2] || m[3];
        frammento.append(creaTempo(valore, valore, onTempo));
        ultimo = m.index + m[0].length;
      }
      frammento.append(testo.slice(ultimo));
      nodo.replaceWith(frammento);
    }
  }

  // Riquadri colorati: distinguono definizioni, teoremi e integrazioni non dette a lezione.
  function classificaRiquadri(radice) {
    const tipi = [
      [/^(definizion)/i, "riquadro-definizione"],
      [/^(teorema|lemma|corollario|proposizione|legge|propriet|regola|principio|formula)/i, "riquadro-teorema"],
      [/^integrazion/i, "riquadro-integrazione"],
      [/^in sintesi/i, "riquadro-sintesi"],
      [/^(attenzione|importante|nota)/i, "riquadro-attenzione"],
    ];
    radice.querySelectorAll("blockquote").forEach((bq) => {
      const primo = bq.querySelector("strong");
      if (!primo) return;
      const testo = primo.textContent.trim();
      for (const [re, classe] of tipi) {
        if (re.test(testo)) {
          bq.classList.add("riquadro", classe);
          break;
        }
      }
    });
  }

  function temaScuro() {
    const tema = document.documentElement.dataset.tema;
    if (tema) return tema === "scuro";
    return Boolean(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  // Gli schemi Mermaid prendono i colori del pannello invece della tavolozza predefinita.
  function variabiliMermaid() {
    const scuro = temaScuro();
    return {
      fontFamily: '"Geist", system-ui, sans-serif',
      fontSize: "15px",
      background: "transparent",
      primaryColor: scuro ? "#2a303c" : "#eef1f6",
      primaryTextColor: scuro ? "#e8ebf1" : "#1d2330",
      primaryBorderColor: scuro ? "#8792a6" : "#1d2330",
      secondaryColor: scuro ? "#323947" : "#fbe6d8",
      secondaryBorderColor: scuro ? "#94bbff" : "#0c4bcc",
      tertiaryColor: scuro ? "#20252f" : "#f6f8fb",
      lineColor: scuro ? "#aab3c3" : "#4f596d",
      textColor: scuro ? "#e8ebf1" : "#1d2330",
      edgeLabelBackground: scuro ? "#20252f" : "#fbfcfe",
      clusterBkg: scuro ? "#232833" : "#f3f5f9",
      clusterBorder: scuro ? "#4f596d" : "#c4ccd9",
      noteBkgColor: scuro ? "#3a2a1f" : "#fff4ea",
      noteBorderColor: scuro ? "#94bbff" : "#0c4bcc",
      actorBkg: scuro ? "#2a303c" : "#eef1f6",
      actorBorder: scuro ? "#8792a6" : "#1d2330",
      signalColor: scuro ? "#aab3c3" : "#4f596d",
    };
  }

  async function rendiSchemi(radice) {
    const blocchi = radice.querySelectorAll("pre > code.language-mermaid");
    if (!blocchi.length || !window.mermaid) return;
    const tema = temaScuro() ? "scuro" : "chiaro";
    if (mermaidPronto !== tema) {
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "base",
        themeVariables: variabiliMermaid(),
        flowchart: { curve: "basis", padding: 14 },
      });
      mermaidPronto = tema;
    }
    for (const code of blocchi) {
      const pre = code.parentElement;
      const id = `schema-${Date.now()}-${contatoreSchemi++}`;
      try {
        const { svg } = await window.mermaid.render(id, code.textContent);
        const div = document.createElement("div");
        div.className = "schema";
        div.innerHTML = svg;
        pre.replaceWith(div);
      } catch (e) {
        document.getElementById(id)?.remove();
        document.getElementById(`d${id}`)?.remove();
        pre.classList.add("schema-errore");
        pre.dataset.avviso = "Schema non visualizzabile (sintassi non valida): ecco il testo dello schema.";
      }
    }
  }

  // --- Mappa concettuale: albero orizzontale disegnato in SVG, senza librerie esterne ---------

  const SVG = "http://www.w3.org/2000/svg";
  let righello = null;

  /** Elenco puntato annidato ("- voce", due spazi per livello) → albero { testo, figli }. */
  function leggiAlbero(testo) {
    const radici = [];
    const pila = [];
    for (const riga of testo.split("\n")) {
      const m = riga.match(/^(\s*)[-*+]\s+(.+?)\s*$/);
      if (!m) continue;
      const livello = Math.floor(m[1].replace(/\t/g, "  ").length / 2);
      const nodo = { testo: m[2].replace(/[*_`#]/g, "").trim(), figli: [] };
      while (pila.length && pila[pila.length - 1].livello >= livello) pila.pop();
      if (pila.length) pila[pila.length - 1].nodo.figli.push(nodo);
      else radici.push(nodo);
      pila.push({ livello, nodo });
    }
    if (!radici.length) return null;
    return radici.length === 1 ? radici[0] : { testo: "Lezione", figli: radici };
  }

  function larghezzaTesto(testo, peso) {
    if (!righello) righello = document.createElement("canvas").getContext("2d");
    righello.font = `${peso} 14px Geist, system-ui, sans-serif`;
    return righello.measureText(testo).width;
  }

  /** Spezza le etichette lunghe su due righe al confine di parola più vicino a metà. */
  function righeEtichetta(testo) {
    if (testo.length <= 26) return [testo];
    const parole = testo.split(" ");
    let migliore = 1;
    let scarto = Infinity;
    for (let i = 1; i < parole.length; i++) {
      const diff = Math.abs(parole.slice(0, i).join(" ").length - parole.slice(i).join(" ").length);
      if (diff < scarto) { scarto = diff; migliore = i; }
    }
    return [parole.slice(0, migliore).join(" "), parole.slice(migliore).join(" ")];
  }

  function disegnaMappa(albero) {
    const RIGA = 18;
    const SPAZIO_V = 14;
    const SPAZIO_O = 56;
    const PAD_O = 16;
    const nodi = [];
    const larghezzePerLivello = [];

    (function misura(nodo, livello) {
      nodo.livello = livello;
      nodo.righe = righeEtichetta(nodo.testo);
      const peso = livello === 0 ? 650 : livello === 1 ? 600 : 450;
      nodo.l = Math.ceil(Math.max(...nodo.righe.map((r) => larghezzaTesto(r, peso)))) + PAD_O * 2;
      nodo.a = nodo.righe.length * RIGA + 16;
      larghezzePerLivello[livello] = Math.max(larghezzePerLivello[livello] || 0, nodo.l);
      nodi.push(nodo);
      nodo.figli.forEach((f) => misura(f, livello + 1));
    })(albero, 0);

    const xLivello = [0];
    for (let i = 1; i < larghezzePerLivello.length; i++) xLivello[i] = xLivello[i - 1] + larghezzePerLivello[i - 1] + SPAZIO_O;

    let cursore = 0;
    (function posiziona(nodo) {
      nodo.x = xLivello[nodo.livello];
      if (!nodo.figli.length) {
        nodo.y = cursore + nodo.a / 2;
        cursore += nodo.a + SPAZIO_V;
        return;
      }
      nodo.figli.forEach(posiziona);
      const primo = nodo.figli[0];
      const ultimo = nodo.figli[nodo.figli.length - 1];
      nodo.y = (primo.y + ultimo.y) / 2;
    })(albero);

    const larghezza = Math.max(...nodi.map((n) => n.x + n.l)) + 4;
    const altezza = Math.max(cursore - SPAZIO_V, albero.a) + 4;
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", `-2 -2 ${larghezza} ${altezza}`);
    svg.setAttribute("width", String(larghezza));
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `Mappa concettuale: ${albero.testo}. ${albero.figli.map((f) => f.testo).join(", ")}.`);

    const collegamenti = document.createElementNS(SVG, "g");
    collegamenti.setAttribute("class", "collegamenti");
    const gruppoNodi = document.createElementNS(SVG, "g");
    let ordine = 0;
    for (const nodo of nodi) {
      for (const figlio of nodo.figli) {
        const x1 = nodo.x + nodo.l;
        const x2 = figlio.x;
        const metà = (x1 + x2) / 2;
        const p = document.createElementNS(SVG, "path");
        p.setAttribute("d", `M${x1},${nodo.y} C${metà},${nodo.y} ${metà},${figlio.y} ${x2},${figlio.y}`);
        p.setAttribute("pathLength", "1");
        p.style.setProperty("--ritardo", `${figlio.livello * 120}ms`);
        collegamenti.append(p);
      }
      const g = document.createElementNS(SVG, "g");
      g.setAttribute("class", `nodo livello-${Math.min(nodo.livello, 2)}`);
      g.style.setProperty("--ritardo", `${nodo.livello * 120 + (ordine++ % 12) * 18}ms`);
      const rect = document.createElementNS(SVG, "rect");
      rect.setAttribute("x", String(nodo.x));
      rect.setAttribute("y", String(nodo.y - nodo.a / 2));
      rect.setAttribute("width", String(nodo.l));
      rect.setAttribute("height", String(nodo.a));
      rect.setAttribute("rx", String(Math.min(nodo.a / 2, 14)));
      g.append(rect);
      nodo.righe.forEach((riga, i) => {
        const t = document.createElementNS(SVG, "text");
        t.setAttribute("x", String(nodo.x + PAD_O));
        t.setAttribute("y", String(nodo.y - ((nodo.righe.length - 1) * RIGA) / 2 + i * RIGA));
        t.setAttribute("dominant-baseline", "central");
        t.textContent = riga;
        g.append(t);
      });
      gruppoNodi.append(g);
    }
    svg.append(collegamenti, gruppoNodi);
    return svg;
  }

  function rendiMappe(radice) {
    for (const code of radice.querySelectorAll("pre > code.language-mappa")) {
      const albero = leggiAlbero(code.textContent);
      if (!albero) continue;
      const div = document.createElement("div");
      div.className = "mappa";
      div.append(disegnaMappa(albero));
      code.parentElement.replaceWith(div);
    }
  }

  async function render(contenitore, markdown, opzioni = {}) {
    const { md, formule } = proteggiFormule(markdown || "");
    const html = window.marked ? window.marked.parse(md, { gfm: true }) : `<pre>${escapeHtml(md)}</pre>`;
    const pulito = window.DOMPurify ? window.DOMPurify.sanitize(html) : escapeHtml(markdown || "");
    contenitore.innerHTML = rendiFormule(pulito, formule);
    contenitore.querySelectorAll("table").forEach((tabella) => {
      if (tabella.parentElement.classList.contains("tabella")) return;
      const involucro = document.createElement("div");
      involucro.className = "tabella";
      tabella.replaceWith(involucro);
      involucro.append(tabella);
    });
    classificaRiquadri(contenitore);
    collegaTempi(contenitore, opzioni.onTempo);
    rendiMappe(contenitore);
    await rendiSchemi(contenitore);
  }

  // La stampa in PDF aspetta che formule, schemi e mappe siano disegnati.
  async function pronto(promesse) {
    try {
      await Promise.all(promesse);
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
    } finally {
      window.__sbobinaPronto = true;
    }
  }

  window.Sbobina = { render, secondi, pronto };
})();
