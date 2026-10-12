/* Rendering degli appunti: Markdown + formule (KaTeX) + schemi (Mermaid) + mappe concettuali (markmap)
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

  async function rendiSchemi(radice) {
    const blocchi = radice.querySelectorAll("pre > code.language-mermaid");
    if (!blocchi.length || !window.mermaid) return;
    if (!mermaidPronto) {
      const scuro = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: scuro ? "dark" : "default" });
      mermaidPronto = true;
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

  async function rendiMappe(radice) {
    const blocchi = radice.querySelectorAll("pre > code.language-mappa");
    const loader = window.markmap && window.markmap.autoLoader;
    if (!blocchi.length || !loader || !loader.ready) return;
    try {
      await loader.ready;
    } catch (e) {
      return;
    }
    for (const code of blocchi) {
      // Niente classe "markmap" sul contenitore: markmap la assegna al proprio <svg>.
      const div = document.createElement("div");
      div.className = "mappa";
      // markmap interpreta l'HTML nelle etichette: qui servono solo testo e Markdown semplice.
      div.textContent = code.textContent.replace(/[<>]/g, "");
      const pre = code.parentElement;
      pre.replaceWith(div);
      try {
        loader.render(div);
      } catch (e) {
        div.replaceWith(pre);
      }
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
    await rendiSchemi(contenitore);
    await rendiMappe(contenitore);
  }

  window.Sbobina = { render, secondi };
})();
