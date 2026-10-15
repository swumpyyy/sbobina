"""Prompt per Claude, in italiano.

Il flusso è pensato per l'accuratezza:
1. revisione della trascrizione a blocchi (correzione dei termini, riconciliazione tra motori);
2. scrittura degli appunti dalla trascrizione revisionata + materiali;
3. verifica degli appunti contro la trascrizione (errori, omissioni, invenzioni);
4. correzione finale.
Le fasi 2-4 condividono lo stesso prefisso (system + materiali + trascrizione) così la cache
del prompt evita di ripagare la trascrizione a ogni passaggio.
"""

from __future__ import annotations

import re

from sbobina.trascrizione.base import Blocco, tempo

# --------------------------------------------------------------------------
# Estrazione dei termini dai materiali (prima della trascrizione)
# --------------------------------------------------------------------------

SYSTEM_TERMINI = (
    "Prepari il riconoscimento vocale di una lezione universitaria. Dai materiali del corso estrai "
    "i termini che un sistema di trascrizione automatica potrebbe sbagliare: termini tecnici, nomi "
    "propri (autori, scienziati, luoghi), sigle, nomi di teoremi, leggi, farmaci, composti, "
    "algoritmi, parole straniere. Scrivili nella grafia esatta usata nei materiali. "
    "Escludi parole comuni dell'italiano e frasi lunghe: ogni termine al massimo 5 parole."
)

SCHEMA_TERMINI = {
    "type": "object",
    "properties": {"termini": {"type": "array", "items": {"type": "string"}}},
    "required": ["termini"],
    "additionalProperties": False,
}


def contenuto_termini(corso: str, titolo: str, blocchi_materiali: list[dict]) -> list[dict]:
    return [
        *blocchi_materiali,
        {
            "type": "text",
            "text": f"Corso: {corso}\nLezione: {titolo}\n\n"
            "Elenca fino a 300 termini, dai più specifici ai più generici.",
        },
    ]


# --------------------------------------------------------------------------
# 1. Revisione della trascrizione
# --------------------------------------------------------------------------

ISTRUZIONI_REVISIONE = """\
Sei un revisore esperto di trascrizioni di lezioni universitarie in italiano. Ricevi un blocco della \
trascrizione automatica di una lezione e restituisci lo stesso blocco corretto. Non stai scrivendo \
appunti né un riassunto: lo scopo è avere un testo fedele parola per parola a ciò che è stato detto, \
ma leggibile. Da questo testo verranno poi scritti gli appunti, quindi ogni contenuto perso o \
inventato qui diventa un errore negli appunti.

Cosa correggere:
- parole riconosciute male, soprattutto termini tecnici, nomi propri, sigle, numeri e formule lette \
ad alta voce: usa il contesto della frase, il glossario e i materiali del corso per ricostruire la \
parola giusta e la grafia esatta;
- punteggiatura, maiuscole e divisione in frasi;
- formule e simboli dettati a voce: scrivili in LaTeX inline ($...$) quando è inequivocabile cosa \
il docente sta dicendo (es. "x al quadrato più uno" → $x^2 + 1$).

Cosa togliere: solo intercalari e disfluenze senza contenuto (ehm, allora allora, false partenze), \
e ripetizioni identiche dovute a errori del riconoscimento.

Cosa non fare:
- non aggiungere spiegazioni, esempi o informazioni che non sono nell'audio;
- non riassumere e non omettere nulla di ciò che ha contenuto: digressioni, domande degli studenti, \
avvisi su esami, date e scadenze vanno mantenuti;
- non correggere affermazioni del docente che ti sembrano sbagliate nel merito: trascrivile come \
sono state dette.

Passaggi dubbi: se il testo non è ricostruibile con sicurezza scrivi la versione più probabile \
seguita da [incerto]; se è del tutto incomprensibile scrivi [incomprensibile].

Più trascrizioni: a volte ricevi anche la trascrizione dello stesso audio fatta da un altro motore. \
Confrontale: dove divergono scegli la versione più plausibile in base al contesto, al glossario e ai \
materiali (spesso un motore sbaglia un termine che l'altro ha riconosciuto). La trascrizione \
principale è quella con i marcatori di tempo.

Formato della risposta:
- solo il testo corretto, senza commenti, titoli o blocchi di codice;
- paragrafi separati da una riga vuota, uno per idea;
- ogni paragrafo inizia con il marcatore di tempo della prima riga di input da cui proviene, \
copiato esattamente (es. [12:34] oppure [1:02:03]);
- quando parla qualcuno diverso dal docente (es. la domanda di uno studente) il paragrafo inizia \
con il marcatore seguito da **Studente:**."""


def system_revisione(corso: str, titolo: str, note: str, glossario: list[str], testo_materiali: str) -> list[dict]:
    contesto = [f"<corso>{corso}</corso>", f"<lezione>{titolo}</lezione>"]
    if note:
        contesto.append(f"<indicazioni_dello_studente>\n{note}\n</indicazioni_dello_studente>")
    if glossario:
        contesto.append("<glossario>\n" + "; ".join(glossario) + "\n</glossario>")
    if testo_materiali:
        contesto.append(f"<materiali_del_corso>\n{testo_materiali}\n</materiali_del_corso>")
    return [
        {"type": "text", "text": ISTRUZIONI_REVISIONE},
        {"type": "text", "text": "\n\n".join(contesto), "cache_control": {"type": "ephemeral"}},
    ]


def messaggio_revisione(
    blocco: Blocco,
    totale: int,
    contesto_precedente: str,
    alternative: list[tuple[str, str]],
    insisti: bool = False,
) -> str:
    fine = tempo(blocco.fine) if blocco.fine is not None else "fine"
    parti = [f"Blocco {blocco.indice + 1} di {totale} (da {tempo(blocco.inizio)} a {fine})."]
    if contesto_precedente:
        parti.append(
            "<fine_blocco_precedente>\n" + contesto_precedente + "\n</fine_blocco_precedente>\n"
            "(Solo contesto: non includerlo nella risposta.)"
        )
    parti.append(f"<trascrizione_principale>\n{blocco.testo}\n</trascrizione_principale>")
    for motore, testo in alternative:
        if testo.strip():
            parti.append(f"<trascrizione_alternativa motore=\"{motore}\">\n{testo}\n</trascrizione_alternativa>")
    richiesta = "Restituisci il blocco corretto."
    if insisti:
        richiesta += (
            " Attenzione: la risposta precedente era molto più corta dell'originale. Non riassumere: "
            "mantieni tutto ciò che il docente dice, togliendo solo intercalari e ripetizioni."
        )
    parti.append(richiesta)
    return "\n\n".join(parti)


# --------------------------------------------------------------------------
# 2-4. Appunti, verifica, correzione (prefisso condiviso e in cache)
# --------------------------------------------------------------------------

SYSTEM_APPUNTI = """\
Trasformi lezioni universitarie in appunti di studio in italiano. Scrivi come lo studente più bravo \
del corso: completo, preciso, ordinato, chiaro. La priorità assoluta è l'accuratezza: chi studia su \
questi appunti deve potersi fidare di ogni definizione, formula, numero e passaggio, perché ci \
preparerà l'esame. Le fonti sono la trascrizione revisionata della lezione e gli eventuali materiali \
del corso (slide, dispense, foto della lavagna) forniti con essa."""


SENZA_AUDIO = """\
Questa lezione non ha una registrazione: le uniche fonti sono i materiali qui sopra (appunti dello \
studente, PDF, foto). Dove le regole parlano di trascrizione intendi i materiali; non scrivere tempi \
⏱, né "Indicazioni del docente" che non compaiono nei materiali. Gli appunti dello studente possono \
essere disordinati o abbreviati: riscrivili completi e chiari senza aggiungere contenuti, e ciò che \
spieghi oltre i materiali va nei riquadri Integrazione."""


def contenuto_lezione(
    *, corso: str, titolo: str, data: str, note: str, blocchi_materiali: list[dict], trascrizione: str
) -> list[dict]:
    """Prefisso comune alle fasi 2-4: materiali + trascrizione, con breakpoint di cache alla fine."""
    intestazione = [f"Corso: {corso}", f"Lezione: {titolo}", f"Data: {data}"]
    if note:
        intestazione.append(f"Indicazioni dello studente: {note}")
    materiali = (
        "I materiali del corso sono allegati qui sopra." if blocchi_materiali else "Nessun materiale allegato."
    )
    fonte = f"<trascrizione>\n{trascrizione}\n</trascrizione>" if trascrizione else SENZA_AUDIO
    return [
        *blocchi_materiali,
        {
            "type": "text",
            "text": "\n".join(intestazione) + f"\n{materiali}\n\n{fonte}",
            "cache_control": {"type": "ephemeral"},
        },
    ]


REGOLE_APPUNTI = """\
Fonti e fedeltà
- La fonte principale è la trascrizione. Usa i materiali per la grafia corretta, le formule esatte, \
la struttura e per riportare ciò che il docente mostra sulle slide ("come vedete qui").
- Non inventare nulla. Se un chiarimento non detto a lezione aiuta davvero a capire (es. una \
definizione data per scontata), mettilo in un riquadro separato che inizia con \
"> **Integrazione:**", breve, e solo se sei certo che sia corretto. Tutto ciò che non è in un \
riquadro Integrazione deve venire dalla lezione o dai materiali.
- Le parti [incerto] o [incomprensibile] della trascrizione non vanno indovinate: se sono rilevanti \
segnalale nella sezione "Punti da verificare".

Completezza
- Gli appunti devono permettere di studiare senza riascoltare la lezione: tutte le definizioni, i \
teoremi e le proprietà con ipotesi e tesi, i passaggi delle dimostrazioni e degli esercizi svolti, \
gli esempi, i casi particolari, i dati numerici, i collegamenti con altre lezioni.
- Riorganizza per argomenti (se il docente torna su un concetto, unisci le parti), elimina \
ripetizioni e chiacchiere non didattiche, ma non perdere contenuto.
- Quando il docente dice che qualcosa è importante o che lo chiederà all'esame, segnalalo con ⭐ nel \
punto in cui compare e riportalo anche in "Indicazioni del docente".

Struttura (titoli esattamente così, in quest'ordine)
# <titolo descrittivo della lezione>
> **In sintesi:** 3-6 righe sugli argomenti principali.

## Mappa concettuale
Uno schema ad albero che lo studente ricopia a mano sul quaderno: deve far capire la lezione a colpo \
d'occhio. Regole:
- Apri il blocco con esattamente ```mappa e chiudilo con ```. Dentro solo un elenco puntato annidato \
(due spazi per livello), niente altro testo.
- Una sola radice: l'argomento della lezione. Se la lezione tratta più argomenti, la radice è il \
titolo della lezione e gli argomenti sono i suoi figli.
- Primo livello: 3-6 temi principali, nell'ordine della lezione. Sotto, al massimo 2 livelli. In tutto \
15-25 nodi.
- Ogni nodo è un concetto concreto che insegna qualcosa, non un'etichetta generica. Sbagliato: \
"Definizione formale", "Proprietà", "Esempi". Giusto: "Immagine = valori assunti da f", \
"Iniettiva: x diversi, y diverse".
- Classificazioni: il padre dice cosa si divide ("Soggetto giuridico: 2 tipi"), ogni figlio è un tipo \
con la sua differenza tra parentesi o dopo →, es. "Persona fisica → ditta individuale".
- Contrapposizioni (A vs B): due figli separati, uno per lato, ciascuno con il tratto distintivo.
- Articoli di legge e numeri esattamente come negli appunti (es. "Art. 2555 c.c."), mai inventati.
- ⭐ davanti ai nodi che il docente ha indicato come importanti o da esame.
- Etichette di massimo 6 parole, termini chiave in MAIUSCOLO come negli schemi da copiare; niente \
formule, grassetto o altri simboli Markdown.
Esempio:
```mappa
- L'IMPRESA E IL SOGGETTO GIURIDICO
  - ⭐ SOGGETTO GIURIDICO: 2 tipi
    - PERSONA FISICA → ditta individuale
    - PERSONA GIURIDICA → società
  - Registro delle imprese = anagrafe imprese
    - Iscrizione alla nascita
    - Cancellazione alla cessazione
  - Norme: Libro V Codice civile
```

## Appunti
Il corpo degli appunti, diviso in sezioni ### e sottosezioni ####. Dopo ogni titolo ### scrivi il \
tempo d'inizio nell'audio nel formato `⏱ mm:ss` preso dai marcatori della trascrizione \
(es. "### Il teorema di Rolle ⏱ 23:15").
- Definizioni: > **Definizione (nome):** testo.
- Teoremi, leggi, proprietà: > **Teorema (nome):** ipotesi e tesi; poi la dimostrazione, se svolta, \
con tutti i passaggi.
- Formule in LaTeX: $...$ nel testo, $$...$$ su righe proprie. Mai formule dentro blocchi di codice.
- Tabelle Markdown per confronti, classificazioni, vantaggi e svantaggi.
- Esempi ed esercizi: #### Esempio oppure #### Esercizio svolto, con tutti i passaggi.
- Schemi: quando la lezione descrive un processo, un algoritmo, una sequenza di cause ed effetti, \
una classificazione o relazioni tra concetti, aggiungi uno schema Mermaid in un blocco ```mermaid \
(flowchart TD o LR, sequenceDiagram, stateDiagram-v2, classDiagram). Regole per Mermaid: etichette \
sempre tra virgolette doppie, es. A["Testo (anche con parentesi)"] e A -->|"etichetta"| B; nessuna \
virgoletta doppia dentro le etichette; niente LaTeX negli schemi; ID dei nodi solo lettere e numeri; \
al massimo circa 15 nodi per schema. Uno schema deve aggiungere chiarezza, non ripetere un elenco.

## Indicazioni del docente
Esame, scadenze, cosa studiare, cose segnalate come importanti, avvisi. Se non ce ne sono scrivi \
"Nessuna indicazione particolare."

## Glossario
Tabella | Termine | Significato | con i termini tecnici introdotti nella lezione.

## Domande di ripasso
8-15 domande, dalle più semplici alle più impegnative. Ogni domanda è un paragrafo che inizia con \
il numero in grassetto, seguito sulla riga successiva dalla risposta in questo formato (una riga \
vuota tra una domanda e l'altra):
**1.** Testo della domanda?
<details><summary>Risposta</summary>testo della risposta</details>

## Punti da verificare
Elenco dei passaggi incerti o incomprensibili rilevanti, ciascuno con `⏱ mm:ss`, oppure "Nessuno."

Stile: italiano chiaro e preciso, frasi complete nei concetti chiave, elenchi puntati dove aiutano. \
Rispondi solo con il Markdown degli appunti, senza premesse."""

ISTRUZIONI_APPUNTI = "Scrivi gli appunti completi di questa lezione in Markdown.\n\n" + REGOLE_APPUNTI

_TITOLI_SEZIONI = {
    "mappa": "## Mappa concettuale",
    "indicazioni": "## Indicazioni del docente",
    "glossario": "## Glossario",
    "domande": "## Domande di ripasso",
}
_LUNGHEZZE = {
    "essenziale": "Lunghezza: appunti essenziali, solo i concetti chiave, definizioni e formule; niente dettagli secondari.",
    "normale": "",
    "dettagliata": "Lunghezza: appunti molto dettagliati, quasi una dispensa: ogni passaggio, esempio e osservazione della lezione.",
}
_STILI = {
    "discorsivo": "",
    "schematico": "Stile: schematico, con elenchi puntati brevi e frasi nominali; paragrafi discorsivi solo dove servono.",
}


def sezioni_escluse(imp) -> list[str]:
    return [t.removeprefix("## ") for s, t in _TITOLI_SEZIONI.items() if imp is not None and not imp.sezione(s)]


def regole_appunti(imp=None) -> str:
    """Le regole degli appunti adattate alle impostazioni dello studente (sezioni, lunghezza, stile, area)."""
    if imp is None:
        return REGOLE_APPUNTI
    from sbobina.impostazioni import AREE

    testo = REGOLE_APPUNTI
    for sezione, titolo in _TITOLI_SEZIONI.items():
        if not imp.sezione(sezione):
            testo = re.sub(rf"\n{re.escape(titolo)}\n.*?(?=\n## |\nStile:)", "", testo, flags=re.S)
    if not imp.sezione("schemi"):
        testo = re.sub(r"\n- Schemi:.*?(?=\n\n## )", "", testo, flags=re.S)
    preferenze = [_LUNGHEZZE.get(imp.lunghezza, ""), _STILI.get(imp.stile, ""), AREE.get(imp.area, "")]
    if imp.anno or imp.corso_di_laurea:
        preferenze.append(f"Lo studente è iscritto a {imp.corso_di_laurea or 'un corso di laurea'}"
                          + (f", anno {imp.anno}" if imp.anno else "") + ".")
    if imp.prompt_extra:
        preferenze.append("Indicazioni personali dello studente (seguile se non contraddicono le regole di fedeltà): "
                          + imp.prompt_extra)
    preferenze = [p for p in preferenze if p]
    if preferenze:
        testo += "\n\nPreferenze dello studente\n" + "\n".join(f"- {p}" for p in preferenze)
    return testo


def istruzioni_appunti(imp=None) -> str:
    return "Scrivi gli appunti completi di questa lezione in Markdown.\n\n" + regole_appunti(imp)

ISTRUZIONI_VERIFICA = """\
Ora fai da revisore. Confronta la bozza di appunti qui sotto con la trascrizione e i materiali, \
sezione per sezione, e trova i problemi di accuratezza:
- "non_supportato": affermazioni, formule, numeri o esempi che non compaiono nella trascrizione né \
nei materiali e non sono in un riquadro Integrazione;
- "errato": contenuti che contraddicono la trascrizione o i materiali (formule, segni, ipotesi \
mancanti, nomi, date, attribuzioni, passaggi saltati o sbagliati);
- "omesso": contenuti didatticamente rilevanti della lezione assenti dagli appunti (definizioni, \
passaggi, esempi, indicazioni d'esame);
- "integrazione_errata": riquadri Integrazione con contenuti scorretti o fuorvianti;
- "schema": schemi Mermaid o mappa concettuale che rappresentano male i concetti o non rispettano \
le regole di sintassi (etichette tra virgolette, ID alfanumerici, niente LaTeX);
- "formato": sezioni obbligatorie mancanti, formule non in LaTeX, tempi ⏱ assenti o sbagliati.
Ignora le scelte di stile. Per ogni problema indica dove si trova negli appunti, l'evidenza nella \
trascrizione (con il tempo) e la correzione precisa da applicare. Se gli appunti sono corretti, \
restituisci un elenco di problemi vuoto.

Infine elenca in termini_chiave i termini tecnici, i nomi propri e le sigle di questa lezione nella \
grafia corretta (massimo 80): serviranno a riconoscere meglio le prossime lezioni dello stesso corso."""

SCHEMA_VERIFICA = {
    "type": "object",
    "properties": {
        "giudizio": {"type": "string"},
        "problemi": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": [
                            "non_supportato", "errato", "omesso", "integrazione_errata", "schema", "formato",
                        ],
                    },
                    "gravita": {"type": "string", "enum": ["alta", "media", "bassa"]},
                    "posizione": {"type": "string"},
                    "evidenza": {"type": "string"},
                    "correzione": {"type": "string"},
                },
                "required": ["tipo", "gravita", "posizione", "evidenza", "correzione"],
                "additionalProperties": False,
            },
        },
        "termini_chiave": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["giudizio", "problemi", "termini_chiave"],
    "additionalProperties": False,
}


def istruzioni_verifica(bozza: str, imp=None, senza_audio: bool = False) -> str:
    escluse = sezioni_escluse(imp)
    nota = (f"\nLo studente ha escluso queste sezioni: {', '.join(escluse)}. Non segnalarle come mancanti."
            if escluse else "")
    if senza_audio:
        nota += ("\nQuesta lezione non ha registrazione: confronta gli appunti con i materiali, e non segnalare "
                 "come problemi i tempi ⏱ assenti o le Indicazioni del docente mancanti.")
    return f"{ISTRUZIONI_VERIFICA}{nota}\n\n<bozza_appunti>\n{bozza}\n</bozza_appunti>"


def istruzioni_correzione(bozza: str, problemi: list[dict], imp=None) -> str:
    elenco = "\n".join(
        # I modelli locali non rispettano sempre lo schema (es. "correzzione"): niente chiavi obbligatorie.
        f"{i}. [{p.get('tipo', '')}, gravità {p.get('gravita', '')}] {p.get('posizione', '')}\n"
        f"   Evidenza: {p.get('evidenza', '')}\n   Correzione: {p.get('correzione') or p.get('correzzione', '')}"
        for i, p in enumerate(problemi, 1)
    )
    return (
        "Qui sotto ci sono la bozza degli appunti e i problemi trovati dal revisore. Riscrivi gli "
        "appunti completi applicando le correzioni. Controlla ogni segnalazione sulla trascrizione: "
        "se una è infondata, ignorala. Lascia invariato tutto ciò che è corretto (struttura, titoli, "
        "formulazioni) e rispetta le stesse regole della bozza:\n\n"
        f"<regole>\n{regole_appunti(imp)}\n</regole>\n\n"
        f"<bozza_appunti>\n{bozza}\n</bozza_appunti>\n\n"
        f"<problemi>\n{elenco}\n</problemi>\n\n"
        "Rispondi solo con il Markdown completo degli appunti corretti."
    )


# --------------------------------------------------------------------------
# 5. Approfondimento: oltre il riassunto, per studiare l'argomento a fondo
# --------------------------------------------------------------------------

REGOLE_APPROFONDIMENTO = """\
Non è un riassunto: gli appunti della lezione esistono già (sono qui sotto). Il tuo compito è far \
capire l'argomento a fondo, come un buon tutor che prepara lo studente all'esame.

Fedeltà
- Puoi andare oltre la lezione, ma ogni contenuto che non viene dalla trascrizione o dai materiali va \
dentro un riquadro che inizia con "> **Integrazione:**". Fuori dai riquadri Integrazione scrivi solo \
ciò che è stato detto a lezione o è nei materiali, spiegato meglio.
- Non inventare articoli di legge, sentenze, autori, date, numeri o formule di cui non sei certo: se \
un dettaglio ti serve ma non ne sei sicuro, scrivilo comunque seguito da [da verificare].

Struttura (titoli esattamente così)
# Approfondimento: <argomento della lezione>
## Il quadro generale
Perché l'argomento conta, dove si colloca nel corso, quali concetti lo reggono.
## <una sezione ## per ciascun argomento principale della lezione>
Per ognuna: spiegazione più ampia e ragionata (il perché, non solo il cosa); almeno un esempio \
concreto nuovo; collegamenti con altri concetti del corso; errori tipici e come evitarli. Usa tabelle \
per i confronti e > **Definizione (nome):** per le definizioni.
## Esercizi e casi pratici
3-5 casi o esercizi con soluzione ragionata dentro <details><summary>Soluzione</summary>...</details>.
## Domande d'esame probabili
5-8 domande, ciascuna come paragrafo che inizia con il numero in grassetto, con la risposta dentro \
<details><summary>Risposta</summary>...</details>.
## Per approfondire ancora
3-6 voci di elenco puntato, ciascuna un argomento preciso (massimo 8 parole) su cui ha senso andare \
ancora più a fondo.

Formule in LaTeX ($...$ e $$...$$). Italiano chiaro. Rispondi solo con il Markdown, senza premesse."""


def istruzioni_approfondimento(appunti: str) -> str:
    return (
        "Scrivi l'approfondimento di studio di questa lezione in Markdown.\n\n"
        f"{REGOLE_APPROFONDIMENTO}\n\n<appunti>\n{appunti}\n</appunti>"
    )


def istruzioni_espansione(argomento: str, approfondimento: str) -> str:
    return (
        f"Lo studente vuole andare più a fondo su: {argomento}\n\n"
        "Scrivi una nuova sezione da aggiungere all'approfondimento qui sotto. Inizia esattamente con "
        f'"## Approfondimento: {argomento}", poi 3-6 sottosezioni ### con spiegazione ragionata, esempi '
        "concreti, collegamenti e almeno un esercizio con soluzione dentro <details>. Non ripetere ciò che "
        "c'è già. Stesse regole di fedeltà: ciò che non viene dalla lezione o dai materiali va nei riquadri "
        '"> **Integrazione:**" e i dettagli incerti si segnano con [da verificare]. '
        "Rispondi solo con il Markdown della nuova sezione.\n\n"
        f"<approfondimento>\n{approfondimento}\n</approfondimento>"
    )
