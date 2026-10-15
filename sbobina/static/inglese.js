// Versione inglese dell'interfaccia: app.js scrive in italiano, qui i testi visibili passano al dizionario.
// shortcut: traduzione per corrispondenza esatta del testo; una frase nuova in app.js resta italiana finché non la si aggiunge qui.
(function () {
  "use strict";

  const EN = {
    // Fasi, stati, schede
    "Non detto a lezione": "Not said in class", "Errato": "Wrong", "Mancante": "Missing",
    "Integrazione errata": "Wrong integration", "Schema": "Diagram", "Formato": "Format",
    "Preparazione": "Preparation", "Trascrizione": "Transcript", "Revisione": "Revision", "Appunti": "Notes",
    "Verifica": "Check", "Approfondimento": "Deep dive", "Pronta": "Ready", "Interrotta da un errore": "Stopped by an error",
    "In coda": "Queued", "In elaborazione": "Processing", "Fermata": "Stopped", "Pronta, non ancora aperta": "Ready, not opened yet",
    "Ripasso": "Review", "Chiedi": "Ask", "Registra": "Record", "Nuova": "New", "lezione": "lecture",
    "Preparazione dell'audio": "Preparing the audio", "Analisi dei materiali": "Reading the materials",
    "Revisione della trascrizione": "Revising the transcript", "Scrittura degli appunti": "Writing the notes",
    "Verifica dell'accuratezza": "Checking accuracy", "Correzione finale": "Final correction",
    "Conversione e normalizzazione del volume": "Converting and normalising the volume",
    "Lettura dei materiali per i termini tecnici": "Reading the materials for technical terms",
    "Sto scrivendo gli appunti (qualche minuto)": "Writing the notes (a few minutes)",
    "Sto scrivendo l'approfondimento (qualche minuto)": "Writing the deep dive (a few minutes)",
    "Confronto degli appunti con la trascrizione": "Comparing the notes with the transcript",
    "Confronto degli appunti con i materiali": "Comparing the notes with the materials",
    "Carico il modello sulla scheda video…": "Loading the model on the graphics card…",

    // Testata e stato dell'AI
    "AI integrata": "Built-in AI", "· gratuita": "· free", "AI non pronta": "AI not ready", "· a pagamento": "· paid",
    "Manca la chiave di Claude": "Claude key missing", "Manca ffmpeg, che serve per leggere l'audio.": "ffmpeg is missing; it is needed to read audio.",
    "Installalo e riavvia Sbobina.": "Install it and restart Sbobina.", "Riprova": "Try again", "Prepara l'AI": "Set up the AI",
    "L'AI che scrive gli appunti non è ancora pronta.": "The AI that writes the notes is not ready yet.",
    "Manca la chiave di Claude.": "Claude key missing.",
    "Aggiungi ANTHROPIC_API_KEY al file .env, oppure torna al modello locale gratuito.": "Add ANTHROPIC_API_KEY to the .env file, or go back to the free local model.",
    "Scarico i modelli": "Downloading the models", "· meno di un minuto": "· less than a minute",
    "· connessione ferma, riprovo": "· connection stalled, retrying",
    "Registra una lezione dal microfono": "Record a lecture from the microphone",
    "Fai una domanda su tutte le tue lezioni": "Ask a question about all your lectures", "Impostazioni": "Settings",
    "Le tue lezioni": "Your lectures", "Cerca tra le lezioni": "Search lectures", "Cerca per titolo o corso": "Search by title or course",
    "Lezioni 1.1": "Lectures 1.1",

    // Elenco e benvenuto
    "Ancora nessuna lezione.": "No lectures yet.", "Tempo stimato": "Estimated time", "· da riprovare": "· to retry", "· fermata": "· stopped",
    "PDF di tutto il corso": "PDF of the whole course", "Tutte le lezioni pronte, con indice.": "All ready lectures, with a table of contents.",
    "Azioni sul corso": "Course actions", "Esporta per Obsidian": "Export for Obsidian",
    "Una nota Markdown per lezione, con collegamenti.": "One Markdown note per lecture, with links.",
    "Glossario": "Glossary", "I termini che aiutano a riconoscere la voce.": "The terms that help recognise speech.",
    "Trascina qui la registrazione": "Drop the recording here",
    "oppure fai clic per sceglierla · audio, oppure appunti, PDF e foto senza audio": "or click to choose it · audio, or notes, PDFs and photos without audio",
    "Riprendi da dove eri,": "Pick up where you left off,", "o aggiungi una lezione.": "or add a lecture.",
    "Dalla registrazione agli appunti,": "From recording to notes,", "sul tuo computer.": "on your computer.",
    "carte da ripassare oggi": "cards to review today", "Come funziona": "How it works", "Carica l'audio": "Upload the audio",
    "Lascia lavorare, anche a finestra chiusa": "Let it work, even with the window closed",
    "Studia, riascolta, stampa il PDF": "Study, listen again, print the PDF", "ore sbobinate": "hours transcribed",

    // Elaborazione e diretta
    "Elaborazione 1.1": "Processing 1.1", "Elaborazione": "Processing", "Testo in diretta": "Live text",
    "Tra poco qui compaiono le parole, man mano che l'AI le scrive.": "Words will appear here as the AI writes them.",
    "In pausa": "Paused", "Aspetto il modello: lo sto scaricando": "Waiting for the model: downloading it",
    "Whisper sta ascoltando la registrazione": "Whisper is listening to the recording", "Gemma sta scrivendo": "Gemma is writing",
    "Errore sconosciuto": "Unknown error", "Il lavoro fatto è salvato: Riprendi riparte da qui.": "Your progress is saved: Resume starts again from here.",
    "Parte quando finiscono le lezioni prima di questa.": "Starts when the lectures before this one are done.",
    "In corso…": "In progress…", "Ferma": "Stop", "Riprova da qui": "Retry from here", "Riprendi": "Resume", "Mi fermo…": "Stopping…",
    "Dietro le quinte": "Behind the scenes",
    "Rimuginando": "Mulling", "Arzigogolando": "Embroidering", "Almanaccando": "Puzzling", "Elucubrando": "Cogitating",
    "Ghiribizzando": "Daydreaming", "Macinando": "Grinding", "Lambiccandosi": "Racking brains", "Fantasticando": "Fantasising",
    "Armeggiando": "Tinkering", "Spignattando": "Cooking up", "Frullando": "Whisking", "Sobbollendo": "Simmering",
    "Cogitando": "Pondering", "Improvvisando": "Improvising", "Scarabocchiando a margine": "Doodling in the margin",
    "Meditando": "Meditating", "Cincischiando": "Dawdling", "Ruminando": "Ruminating", "Pensandoci su": "Thinking it over",
    "Bollendo in pentola": "Bubbling away", "Marinando": "Marinating", "Bighellonando": "Loafing", "Trafficando": "Fiddling",
    "Smanettando": "Hacking away", "Rimestando": "Stirring", "Ingarbugliando e sbrogliando": "Tangling and untangling",
    "Facendo due conti": "Doing the maths", "Spremendo le meningi": "Squeezing the brain", "Tirando le fila": "Pulling threads together",
    "Mettendo in fila i neuroni": "Lining up neurons", "Caricando il cervellone": "Booting the big brain",
    "Sorseggiando un caffè": "Sipping a coffee", "Ronzando": "Buzzing", "Girando la moka": "Stirring the moka",
    "Facendo il ripasso al volo": "Cramming", "Preparando il terreno": "Laying the groundwork", "Accordando gli strumenti": "Tuning up",
    "Scaldando i motori": "Warming up", "Sintonizzandosi": "Tuning in", "Allacciando le cinture": "Buckling up",
    "Origliando": "Eavesdropping", "Sbobinando": "Transcribing", "Tendendo l'orecchio": "Listening closely", "Decifrando": "Deciphering",
    "Drizzando le antenne": "Pricking up ears", "Ascoltando dal primo banco": "Listening from the front row",
    "Ripescando le parole": "Fishing for words", "Prendendo appunti a raffica": "Taking rapid-fire notes", "Rileggendo": "Rereading",
    "Limando": "Polishing", "Ripulendo": "Tidying", "Sgrovigliando": "Untangling", "Lucidando": "Shining",
    "Mettendo in ordine": "Putting in order", "Correggendo con la penna rossa": "Marking in red pen", "Stirando le frasi": "Ironing sentences",
    "Scarabocchiando": "Scribbling", "Abbozzando": "Sketching", "Impaginando": "Laying out", "Sferruzzando": "Knitting",
    "Scrivendo in bella": "Writing it neatly", "Evidenziando": "Highlighting", "Ricopiando in bella": "Copying out neatly",
    "Disegnando frecce e schemi": "Drawing arrows and diagrams", "Spulciando": "Combing through", "Scrutinando": "Scrutinising",
    "Setacciando": "Sifting", "Facendo le pulci": "Nitpicking", "Ricontrollando": "Double-checking",
    "Mettendo la lente d'ingrandimento": "Getting the magnifying glass", "Interrogando gli appunti": "Quizzing the notes",
    "Approfondendo": "Digging deeper", "Scavando": "Digging", "Rovistando": "Rummaging", "Andando a fondo": "Getting to the bottom",
    "Sbrogliando la matassa": "Unravelling the knot", "Tirando fuori il di più": "Squeezing out extras",

    // Lettore audio e lezione
    "Riproduci": "Play", "Pausa": "Pause", "Posizione nella registrazione": "Position in the recording",
    "Velocità di riproduzione": "Playback speed", "Registrazione": "Recording", "Indietro di 15 secondi": "Back 15 seconds",
    "Avanti di 15 secondi": "Forward 15 seconds", "Da approfondire": "To explore", "Da controllare": "To check",
    "Cosa vuoi vedere": "What do you want to see",
    "Gli appunti compaiono qui quando l'elaborazione arriva ad Appunti.": "The notes appear here when processing reaches Notes.",
    "Bozza: la verifica con la registrazione è in corso e potrebbe correggerla.": "Draft: the check against the recording is running and may correct it.",
    "Modifica": "Edit",
    "Questa lezione non ha ancora un approfondimento: spiegazioni più ampie, esempi, esercizi e domande d'esame.": "This lecture has no deep dive yet: broader explanations, examples, exercises and exam questions.",
    "L'approfondimento compare qui dopo gli appunti: spiegazioni più ampie, esempi, esercizi e domande d'esame.": "The deep dive appears here after the notes: broader explanations, examples, exercises and exam questions.",
    "Crea l'approfondimento": "Create the deep dive",
    "Va oltre il riassunto: spiega il perché, aggiunge esempi ed esercizi. Ciò che non è stato detto a lezione è nei riquadri Integrazione.": "Goes beyond the summary: explains the why, adds examples and exercises. Anything not said in class is in the Integration boxes.",
    "es. la differenza tra imposte e tasse": "e.g. the difference between taxes and duties", "Argomenti suggeriti": "Suggested topics",
    "Oppure scrivi tu cosa approfondire": "Or write what to explore", "Approfondisci": "Explore", "Approfondimento 1.1": "Deep dive 1.1",
    "Approfondisci ancora": "Explore further",
    "Scegli un punto: l'AI aggiunge una nuova sezione all'approfondimento e al PDF. Ci vuole qualche minuto.": "Pick a point: the AI adds a new section to the deep dive and the PDF. It takes a few minutes.",
    "Preparo il PDF…": "Preparing the PDF…",
    "La trascrizione revisionata compare qui dopo la fase di revisione.": "The revised transcript appears here after the revision step.",
    "Fedele a ciò che è stato detto. Clicca un paragrafo per riascoltarlo: mentre l'audio va, il paragrafo in corso si illumina.": "Faithful to what was said. Click a paragraph to hear it again: while the audio plays, the current paragraph lights up.",
    "Fedele a ciò che è stato detto, con i termini corretti. [incerto] e [incomprensibile] segnano i punti da riascoltare.": "Faithful to what was said, with corrected terms. [incerto] and [incomprensibile] mark the spots to listen to again.",
    "La verifica è disattivata (SBOBINA_VERIFICA=0).": "The check is turned off (SBOBINA_VERIFICA=0).",
    "Il controllo degli appunti con la registrazione compare qui alla fine.": "The check of the notes against the recording appears here at the end.",
    "Prima di consegnarti gli appunti, Sbobina li ha confrontati frase per frase con la trascrizione. I problemi qui sotto sono già corretti nella versione finale.": "Before handing you the notes, Sbobina compared them sentence by sentence with the transcript. The issues below are already fixed in the final version.",
    "Giudizio": "Verdict", "Nessun problema trovato": "No issues found", "Dove": "Where", "Evidenza": "Evidence", "Correzione": "Correction",
    "Termini aggiunti al glossario del corso": "Terms added to the course glossary", "Azioni sulla lezione": "Lecture actions",
    "Scarica il PDF": "Download the PDF", "Altri PDF": "More PDFs", "Solo appunti": "Notes only",
    "Il PDF da ricopiare nel quaderno.": "The PDF to copy into your notebook.", "Appunti + approfondimento": "Notes + deep dive",
    "Con spiegazioni, esempi ed esercizi.": "With explanations, examples and exercises.", "Appunti + trascrizione": "Notes + transcript",
    "Con il testo completo della lezione.": "With the full text of the lecture.", "Stampa": "Print", "Rielabora": "Reprocess",
    "Riscrivi gli appunti": "Rewrite the notes",
    "Dalla trascrizione già revisionata, per esempio dopo aver aggiornato il glossario.": "From the already revised transcript, e.g. after updating the glossary.",
    "Di nuovo dai tuoi appunti, PDF e foto.": "Again from your notes, PDFs and photos.", "Rivedi la trascrizione": "Revise the transcript",
    "Ripete la correzione dei termini e poi gli appunti.": "Repeats the term correction, then the notes.", "Ricomincia da capo": "Start over",
    "Ritrascrive anche l'audio: richiede più tempo.": "Transcribes the audio again: takes longer.", "Elimina": "Delete",
    "Riscrivere gli appunti di questa lezione? Quelli attuali verranno sostituiti.": "Rewrite this lecture's notes? The current ones will be replaced.",
    "Rifare la revisione della trascrizione e gli appunti?": "Redo the transcript revision and the notes?",
    "Ricominciare da capo, trascrizione compresa?": "Start over, transcript included?",
    "Schema non visualizzabile (sintassi non valida): ecco il testo dello schema.": "Diagram can't be shown (invalid syntax): here is its text.",

    // Nuova lezione
    "Scegli o trascina la registrazione": "Choose or drop the recording",
    "m4a, mp3, wav e altri formati. Più file diventano più lezioni.": "m4a, mp3, wav and other formats. Several files become several lectures.",
    "Slide, dispense o foto della lavagna": "Slides, handouts or photos of the board",
    "Facoltativi, ma migliorano molto i termini tecnici.": "Optional, but they greatly improve technical terms.",
    "es. Lezione 5, Derivate": "e.g. Lecture 5, Derivatives", "Preso dal nome di ogni file": "Taken from each file name",
    "I tuoi appunti": "Your notes", "(facoltativo se carichi file)": "(optional if you upload files)",
    "Incolla o scrivi qui gli appunti presi a lezione, anche disordinati": "Paste or write the notes you took in class here, even messy ones",
    "Scegli l'audio e il corso. Al resto pensa Sbobina, sul tuo computer.": "Choose the audio and the course. Sbobina does the rest, on your computer.",
    "Appunti, PDF o foto": "Notes, PDFs or photos", "Scegli o trascina appunti, PDF o foto": "Choose or drop notes, PDFs or photos",
    "PDF (anche scansionati), foto di appunti o lavagna, file di testo. Più file diventano una lezione.": "PDFs (scans too), photos of notes or the board, text files. Several files become one lecture.",
    "Carica appunti, PDF o foto della lavagna, o incolla il testo: Sbobina li trasforma in appunti completi.": "Upload notes, PDFs or photos of the board, or paste text: Sbobina turns them into complete notes.",
    "Carica ed elabora": "Upload and process", "Nomi e termini difficili": "Names and tricky terms",
    "Nome del docente, autori, sigle, termini tecnici, separati da virgola": "Lecturer's name, authors, acronyms, technical terms, comma-separated",
    "Indicazioni per gli appunti": "Instructions for the notes",
    "es. argomento della lezione, cose su cui insistere": "e.g. lecture topic, things to focus on", "Corso": "Course",
    "es. Diritto privato": "e.g. Private law", "Data": "Date", "Titolo": "Title", "(facoltativo)": "(optional)",
    "Aggiungi slide, termini difficili o indicazioni": "Add slides, tricky terms or instructions", "Annulla": "Cancel",
    "Nuova lezione 1.1": "New lecture 1.1", "Nuova lezione": "New lecture", "Salvataggio…": "Saving…",
    "Connessione con Sbobina interrotta. Controlla che il server sia ancora acceso e riprova.": "Connection to Sbobina lost. Check that the server is still running and try again.",

    // Glossario
    "Un termine per riga": "One term per line", "Salva il glossario": "Save the glossary", "Glossario 1.1": "Glossary 1.1",
    "Questi termini aiutano il riconoscimento vocale e l'AI a scriverli giusti. Il glossario cresce da solo dopo ogni lezione: aggiungi il nome del docente o correggi una grafia sbagliata.": "These terms help speech recognition and the AI spell them right. The glossary grows by itself after every lecture: add the lecturer's name or fix a wrong spelling.",

    // Statistiche (sezione nerd)
    "Motore": "Engine", "Modello": "Model", "Token letti": "Tokens read", "Lettura": "Reading", "Primo token": "First token",
    "Token scritti": "Tokens written", "Scrittura": "Writing", "Memoria al picco": "Peak memory", "Durata": "Duration",
    "Contesto": "Context", "Limite risposta": "Answer limit", "Temperatura": "Temperature", "Audio ascoltato": "Audio heard",
    "Audio totale": "Total audio", "Velocità": "Speed", "× tempo reale": "× real time", "Lezioni lette": "Lectures read",
    "Caratteri letti": "Characters read", "Token dalla cache": "Cached tokens", "Statistiche": "Statistics",

    // Ripasso: flashcard e quiz
    "Flashcard e quiz si creano quando gli appunti sono pronti.": "Flashcards and quizzes are created when the notes are ready.",
    "Carico…": "Loading…",
    "Domande e risposte brevi da ripassare con il metodo Leitner: le carte che sai tornano sempre più di rado, quelle che sbagli tornano domani.": "Short questions and answers to review with the Leitner method: cards you know come back less and less, the ones you miss come back tomorrow.",
    "Preparo le flashcard dagli appunti (qualche minuto con l'AI locale)…": "Making flashcards from the notes (a few minutes with the local AI)…",
    "Crea le flashcard": "Create flashcards", "Esporta per Anki": "Export for Anki", "Niente da ripassare oggi.": "Nothing to review today.",
    "Le carte sbagliate tornano domani, le altre più avanti.": "Missed cards come back tomorrow, the others later.",
    "Gira la carta": "Flip the card", "Da rivedere": "Review again", "La sapevo": "I knew it", "Quiz di verifica": "Check quiz",
    "Preparo le domande (qualche minuto con l'AI locale)…": "Preparing the questions (a few minutes with the local AI)…",
    "Crea il quiz": "Create the quiz",
    "Dieci domande a scelta multipla come all'esame, con la spiegazione e il minuto della lezione in cui se ne parla.": "Ten multiple-choice questions like in the exam, with the explanation and the minute of the lecture where it's covered.",
    "Perfetto.": "Perfect.", "Riguarda le spiegazioni delle domande sbagliate.": "Go over the explanations of the questions you missed.",
    "Rifai": "Redo", "Nuove domande": "New questions", "Avanti": "Next", "Risultato": "Result", "Risposte": "Answers",
    "Giusto.": "Right.", "Non proprio.": "Not quite.", "Ripasso di oggi": "Today's review",
    "Le flashcard di tutte le lezioni che oggi tocca rivedere.": "The flashcards from all lectures due for review today.",
    "Ripasso 1.1": "Review 1.1", "Hai ripassato tutto": "You've reviewed everything",

    // Chiedi
    "Potrai fare domande alla lezione quando gli appunti sono pronti.": "You can ask the lecture questions once the notes are ready.",
    "Chiedi alla lezione": "Ask the lecture",
    "Chiedi qualcosa su questa lezione: \"che differenza c'è tra…\", \"dove spiega…\", \"fammi un esempio di…\". Ti rispondo solo con ciò che è stato detto, citando il minuto.": "Ask something about this lecture: \"what's the difference between…\", \"where does it explain…\", \"give me an example of…\". I answer only with what was said, citing the minute.",
    "Cerco nella lezione…": "Searching the lecture…", "Dagli appunti di": "From the notes of", "Scrivi la tua domanda…": "Write your question…",
    "Domanda": "Question", "Chiedi (Invio)": "Ask (Enter)", "Nuova conversazione": "New conversation", "invia ·": "send ·",
    "Chiedi 1.1": "Ask 1.1", "Chiedi alle tue lezioni": "Ask your lectures",
    "Rispondo solo con quello che c'è nei tuoi appunti, e ti dico in quale lezione e a che minuto.": "I answer only with what's in your notes, and tell you which lecture and which minute.",
    "Quando una lezione è pronta potrai farle domande qui.": "When a lecture is ready you can ask it questions here.",
    "Cerca nel corso": "Search in course", "Tutti i corsi": "All courses", "La tua conversazione": "Your conversation",
    "Da dove parti? Tocca una domanda o scrivine una tua.": "Where do you start? Tap a question or write your own.",
    "Quali argomenti ha detto che chiederà all'esame?": "Which topics did they say will be in the exam?",
    "Riassumimi i concetti chiave, lezione per lezione": "Summarise the key concepts, lecture by lecture",
    "Quali definizioni devo sapere a memoria?": "Which definitions must I know by heart?", "Sfoglio i tuoi appunti…": "Leafing through your notes…",

    // Modifica appunti
    "Testo degli appunti (Markdown)": "Notes text (Markdown)", "Appunti salvati": "Notes saved",
    "Markdown: # titoli, **grassetto**, - elenchi, $formule$. Il PDF si rifà con le tue modifiche.": "Markdown: # headings, **bold**, - lists, $formulas$. The PDF is rebuilt with your edits.",
    "Tornare agli appunti scritti dall'AI? Le tue modifiche andranno perse.": "Go back to the notes written by the AI? Your edits will be lost.",
    "Versione dell'AI": "AI version", "Salva": "Save", "Salvato": "Saved",

    // Registratore
    "es. Lezione 6, Le obbligazioni": "e.g. Lecture 6, Obligations", "Inizia a registrare": "Start recording",
    "Ferma e crea gli appunti": "Stop and create the notes", "Indica il corso prima di fermare.": "Enter the course before stopping.",
    "Buttare via questa registrazione?": "Throw away this recording?", "Registratore 1.1 · REC": "Recorder 1.1 · REC",
    "Registra la lezione": "Record the lecture", "Nel testo delle lezioni": "In the lecture text", "Nessun passaggio trovato.": "No passages found.",

    // Impostazioni
    "Mappa concettuale": "Concept map", "L'albero dei concetti all'inizio degli appunti": "The concept tree at the start of the notes",
    "Schemi e diagrammi": "Diagrams", "Flussi e classificazioni disegnati quando aiutano": "Flows and classifications drawn when they help",
    "Domande di ripasso": "Review questions", "8-15 domande con risposta a scomparsa": "8-15 questions with hidden answers",
    "I termini tecnici della lezione in tabella": "The lecture's technical terms in a table", "Indicazioni del docente": "Lecturer's remarks",
    "Esame, cose importanti, avvisi": "Exam, important points, announcements", "Approfondimento automatico": "Automatic deep dive",
    "Spiegazioni più ampie, esempi ed esercizi (più tempo)": "Broader explanations, examples and exercises (takes longer)",
    "Verifica con l'audio": "Check against the audio",
    "Ricontrolla gli appunti frase per frase (più tempo, più precisione)": "Rechecks the notes sentence by sentence (longer, more precise)",
    "Economia": "Economics", "Giurisprudenza": "Law", "Ingegneria": "Engineering", "Medicina": "Medicine", "Umanistica": "Humanities",
    "Scienze": "Sciences", "Altro": "Other", "Modello che scrive gli appunti": "Model that writes the notes", "Consigliato": "Recommended",
    "Scaricato": "Downloaded", "Troppo grande per la scheda video di questo PC: sarebbe molto lento.": "Too big for this PC's graphics card: it would be very slow.",
    "Scarica e prepara": "Download and set up", "Preparo…": "Setting up…", "Chi scrive gli appunti": "Who writes the notes",
    "Integrato": "Built-in", "Il modello gira dentro Sbobina, senza altri programmi": "The model runs inside Sbobina, no other programs",
    "API di Anthropic, a pagamento": "Anthropic API, paid", "Chiave API di Claude": "Claude API key",
    "Riconoscimento vocale": "Speech recognition", "Il modello Whisper che trascrive l'audio.": "The Whisper model that transcribes the audio.",
    "es. Usa esempi tratti dal bilancio di aziende italiane. Scrivi le formule anche a parole.": "e.g. Use examples from real company balance sheets. Also write formulas in words.",
    "Jev rosa": "Jev pink", "Menta": "Mint", "Arancio": "Orange", "Cobalto": "Cobalt", "Limone": "Lemon", "Seppia": "Sepia",
    "Tuo colore": "Your colour", "Scegli il colore": "Pick the colour", "Tema colore": "Colour theme", "Sezione nerd": "Nerd section",
    "Per chi vuole vedere i numeri del modello.": "For those who want to see the model's numbers.",
    "Compare il tasto Statistiche: token letti e scritti, velocità, memoria e durata, sotto ogni risposta e mentre elabora una lezione.": "Shows the Statistics button: tokens read and written, speed, memory and duration, under every answer and while processing a lecture.",
    "Sezione nerd sbloccata": "Nerd section unlocked",
    "Ogni modifica si salva subito e vale dalla prossima lezione.": "Every change is saved immediately and applies from the next lecture.",
    "Come vuoi che siano scritti.": "How you want them written.", "Lunghezza": "Length", "Essenziale": "Essential", "Normale": "Normal",
    "Dettagliata": "Detailed", "Stile": "Style", "Discorsivo": "Prose", "Schematico": "Schematic", "Intelligenza artificiale": "Artificial intelligence",
    "Impostazioni avanzate": "Advanced settings", "Creatività": "Creativity",
    "Bassa = più fedele alla lezione. Consigliato 0,3.": "Low = more faithful to the lecture. Recommended 0.3.",
    "Memoria per lezione": "Memory per lecture", "Auto": "Auto", "Istruzioni personali per gli appunti": "Personal instructions for the notes",
    "Si aggiungono alle regole di Sbobina; la fedeltà alla lezione resta prioritaria.": "Added to Sbobina's rules; faithfulness to the lecture still comes first.",
    "Il tuo profilo": "Your profile", "Aiuta l'AI a scrivere nel modo giusto per la tua materia.": "Helps the AI write the right way for your subject.",
    "Nome": "Name", "Università": "University", "es. Università di Firenze": "e.g. University of Florence", "Corso di laurea": "Degree course",
    "es. Economia aziendale": "e.g. Business economics", "Area di studio": "Field of study", "Anno": "Year", "fuori corso": "beyond normal duration",
    "magistrale": "master's", "Cosa mettere nel PDF quando premi Scarica.": "What to put in the PDF when you press Download.",
    "Con la trascrizione": "With the transcript", "Aspetto": "Appearance", "Tema": "Theme", "Chiaro": "Light", "Scuro": "Dark", "Colore": "Colour",
    "L'accento e il rosa del desktop mentre registri.": "The accent, and the desktop tint while you record.",
    "Scegli un accento qualsiasi: vale per il tema «Tuo colore».": "Pick any accent: it applies to the «Your colour» theme.",
    "Griglia a puntini": "Dot grid", "Lo sfondo a quadretti di Lectio.": "Lectio's grid background.", "Vetro": "Glass",
    "Trasparenze sulla barra, i download e i comandi. Spento: carta piena.": "Translucency on the bar, downloads and controls. Off: solid paper.",
    "Riduci le animazioni": "Reduce motion", "Utile se il movimento ti distrae.": "Useful if motion distracts you.",
    "Dimensione del testo": "Text size", "Vale per appunti e trascrizioni.": "Applies to notes and transcripts.",
    "Quando una lezione è pronta": "When a lecture is ready", "Notifica": "Notification",
    "Anche se Sbobina è in secondo piano.": "Even when Sbobina is in the background.", "Suono": "Sound", "Un breve accordo.": "A short chord.",
    "I tuoi dati": "Your data", "Mostra nel Finder": "Show in Finder", "Apri in Esplora file": "Open in File Explorer",
    "Appunti pronti": "Notes ready", "Lingua": "Language",
    "Dell'app, delle lezioni e degli appunti. Cambiando lingua l'app si ricarica.": "Of the app, the lectures and the notes. Changing it reloads the app.",

    // Primo avvio
    "Indietro": "Back", "Ciao, sono": "Hi, I'm",
    "Ti faccio tre domande e preparo l'AI. Ci vogliono un paio di minuti più il download.": "I'll ask you three questions and set up the AI. It takes a couple of minutes plus the download.",
    "Iniziamo": "Let's start", "Come ti chiami?": "What's your name?", "Parlami dei tuoi studi": "Tell me about your studies",
    "Così gli appunti usano il linguaggio giusto per la tua materia.": "So the notes use the right language for your subject.",
    "L'AI gratuita gira sui Mac con chip Apple (M1 o più recenti) e sui PC Windows: su questo computer serve Claude, a pagamento.": "The free AI runs on Macs with Apple chips (M1 or newer) and on Windows PCs: this computer needs Claude, which is paid.",
    "Inizia a usare Sbobina": "Start using Sbobina", "Preparo l'AI": "Setting up the AI",
    "Scarico il modello che scrive gli appunti e quello che riconosce la voce. Succede una volta sola.": "Downloading the model that writes the notes and the one that recognises speech. This happens only once.",
    "Lo faccio dopo": "I'll do it later", "Benvenuto 1.1": "Welcome 1.1",
    "Non riesco a contattare Sbobina.": "I can't reach Sbobina.", "Tocca per vedere la risposta": "Tap to see the answer",

    // Modelli (sistema.py)
    "Massima qualità": "Best quality",
    "Per Mac con 8 GB. Appunti corretti ma più essenziali; meglio con lezioni fino a un'ora.": "For Macs with 8 GB. Correct but more essential notes; best with lectures up to an hour.",
    "Per Mac con 16 GB. Buona qualità senza appesantire il computer.": "For Macs with 16 GB. Good quality without slowing the computer down.",
    "Appunti completi e precisi. Il punto di partenza ideale da 24 GB in su.": "Complete, precise notes. The ideal starting point from 24 GB up.",
    "Il migliore da 32 GB in su: 26 miliardi di parametri ma ne usa 4 alla volta, quindi è più veloce dell'Accurato.": "The best from 32 GB up: 26 billion parameters but it uses 4 at a time, so it's faster than Accurate.",
    "Per workstation con 64 GB o più: il più lento, per chi vuole il massimo dettaglio.": "For workstations with 64 GB or more: the slowest, for maximum detail.",
    "Quasi preciso come il modello grande, molte volte più veloce. Consigliato.": "Almost as accurate as the large model, many times faster. Recommended.",
    "Il più accurato su audio difficili (aula rumorosa, docente lontano). Più lento.": "The most accurate on difficult audio (noisy room, distant lecturer). Slower.",
    "Per dischi quasi pieni. Sbaglia più spesso i termini tecnici.": "For almost full disks. Gets technical terms wrong more often.",

    "lezioni pronte": "lectures ready", "lezione pronta": "lecture ready", "corsi": "courses", "corso": "course",
    "Leggero": "Light", "Equilibrato": "Balanced", "Accurato": "Accurate", "Grande": "Large", "Piccolo": "Small",
    "in": "in", "tutti i corsi": "all courses", "a capo": "new line", "es. Leonardo": "e.g. Leonardo",

    // Messaggi del server
    "Scegli una registrazione, oppure aggiungi appunti, PDF o foto.": "Choose a recording, or add notes, PDFs or photos.",
    "Indica il corso.": "Enter the course.", "Gli appunti non sono ancora pronti.": "The notes are not ready yet.",
    "Questo corso non ha ancora lezioni pronte.": "This course has no ready lectures yet.", "La lezione è già in elaborazione.": "The lecture is already being processed.",
    "Prima devono essere pronti gli appunti.": "The notes must be ready first.",
    "Attendi la fine dell'elaborazione prima di eliminare la lezione.": "Wait for processing to finish before deleting the lecture.",
    "L'AI non è pronta: preparala dalle Impostazioni.": "The AI is not ready: set it up in Settings.",
    "L'AI sta scrivendo gli appunti di una lezione: riprova quando ha finito.": "The AI is writing a lecture's notes: try again when it's done.",
    "Sto già rispondendo a un'altra richiesta: un attimo.": "Already answering another request: one moment.",
    "Aspetta la fine dell'elaborazione prima di modificare gli appunti.": "Wait for processing to finish before editing the notes.",
    "Il testo degli appunti è vuoto o troppo lungo.": "The notes text is empty or too long.",
    "Gli appunti non sono mai stati modificati.": "The notes were never edited.", "Scrivi una domanda.": "Write a question.",
    "Manca ffmpeg, che serve per registrare.": "ffmpeg is missing; it is needed to record.", "Lezione non trovata": "Lecture not found",
    "La lezione non è in elaborazione.": "The lecture is not being processed.",
    "Gli appunti di questa lezione non sono ancora pronti.": "This lecture's notes are not ready yet.",
    "Il modello non ha prodotto domande valide: riprova.": "The model didn't produce valid questions: try again.",
    "Il modello non ha prodotto flashcard valide: riprova.": "The model didn't produce valid flashcards: try again.",
    "Crea prima le flashcard di questa lezione (scheda Ripasso).": "Create this lecture's flashcards first (Review tab).",
    "Sto già registrando.": "Already recording.", "Non c'è nessuna registrazione in corso.": "No recording in progress.",
    "La registrazione si è interrotta.": "The recording stopped.", "La registrazione è vuota: controlla il permesso del microfono.": "The recording is empty: check the microphone permission.",
    "I materiali di questa lezione non si leggono: niente da cui scrivere gli appunti.": "This lecture's materials can't be read: nothing to write the notes from.",
    "Nessuna parola riconosciuta: l'audio sembra vuoto o in un'altra lingua.": "No words recognised: the audio seems empty or in another language.",
    "Il modello integrato si è bloccato ripetendo la stessa frase.": "The built-in model got stuck repeating the same sentence.",
    "La risposta del modello integrato è stata troncata (limite di lunghezza raggiunto).": "The built-in model's answer was cut off (length limit reached).",
    "Il modello integrato ha restituito una risposta vuota.": "The built-in model returned an empty answer.",
    "La versione corretta degli appunti era molto più corta della bozza: è stata mantenuta la bozza (vedi la scheda Verifica per i punti segnalati).": "The corrected notes were much shorter than the draft: the draft was kept (see the Check tab for the flagged points).",
    "Per creare il PDF serve Google Chrome (o Chromium o Edge). In alternativa apri la versione stampabile e usa Stampa → Salva come PDF.": "Creating the PDF needs Google Chrome (or Chromium or Edge). Alternatively open the printable version and use Print → Save as PDF.",
  };

  // Testi con parti variabili: [espressione, sostituzione].
  const MODELLI = [
    [/^Errore (\d+)$/, "Error $1"],
    [/^· circa (.+)$/, "· about $1"],
    [/^(.+) di (.+) GB$/, "$1 of $2 GB"],
    [/^Nessuna lezione per "(.*)"\.$/, 'No lectures for "$1".'],
    [/^(\d+) lezioni$/, "$1 lectures"],
    [/^Azioni sul corso (.+)$/, "Course actions $1"],
    [/^Una volta sola: Sbobina scarica il modello sul tuo (Mac|PC)\.$/, "Just once: Sbobina downloads the model to your $1."],
    [/^Sbobina trascrive la lezione, .*l'audio non esce dal (Mac|PC)\.$/, "Sbobina transcribes the lecture, fixes terms with your slides, writes notes with diagrams and review questions, and checks them against the audio. No account, no cost, the audio never leaves your $1."],
    [/^Interrotta durante (.+)$/, (_, f) => `Stopped by an error during ${tr(f.charAt(0).toUpperCase() + f.slice(1)).toLowerCase()}`],
    [/^Fermata durante (.+)$/, (_, f) => `Stopped during ${tr(f.charAt(0).toUpperCase() + f.slice(1)).toLowerCase()}`],
    [/^Velocità (.+) per$/, "Speed $1×"],
    [/^(\d+) (materiale|materiali)$/, (_, n) => `${n} ${n === "1" ? "material" : "materials"}`],
    [/^(\d+) correzioni$/, "$1 corrections"],
    [/^Trascrizione: (.+)$/, "Transcript: $1"],
    [/^Costo stimato di Claude: (.+)$/, "Estimated Claude cost: $1"],
    [/^Appunti 1\.1$/, "Notes 1.1"], [/^Approfondimento 1\.1$/, "Deep dive 1.1"], [/^Trascrizione 1\.1$/, "Transcript 1.1"],
    [/^Verifica 1\.1$/, "Check 1.1"], [/^Ripasso 1\.1$/, "Review 1.1"],
    [/^Correzioni fatte \((\d+)\)$/, "Corrections made ($1)"],
    [/^gravità (.+)$/, (_, g) => `severity ${{ alta: "high", media: "medium", bassa: "low" }[g] || g}`],
    [/^Eliminare "(.*)"\? Verranno cancellati audio, trascrizione e appunti\.$/, 'Delete "$1"? Audio, transcript and notes will be erased.'],
    [/^(\d+) file scelti$/, "$1 files chosen"],
    [/^Caricamento (\d+)%$/, "Uploading $1%"],
    [/^Glossario di (.+)$/, "Glossary of $1"],
    [/^(\d+) carte in questa lezione$/, "$1 cards in this lecture"],
    [/^Fatto: (\d+) su (\d+) le sapevi\.$/, "Done: you knew $1 of $2."],
    [/^(.+)\. Torna domani\.$/, (_, c) => `${tr(c)}. Come back tomorrow.`],
    [/^(\d+) mila$/, "$1k"],
    [/^(.+) 1\.1$/, (_, t) => `${tr(t)} 1.1`],
    [/^es\. (.+)$/, "e.g. $1"],
    [/^(\d+) su (\d+)$/, "$1 of $2"],
    [/^Tieni il (Mac|PC) vicino al docente\..*$/, "Keep the $1 close to the lecturer. You can use other apps while recording; at the end Sbobina creates the notes by itself."],
    [/^(.+) GB · da (\d+) GB di memoria$/, "$1 GB · from $2 GB of memory"],
    [/^Serve un Mac con almeno (\d+) GB di memoria\.$/, "Needs a Mac with at least $1 GB of memory."],
    [/^Tutto pronto: i modelli sono sul tuo (Mac|PC)\.$/, "All set: the models are on your $1."],
    [/^Una volta sola: scarico i modelli sul tuo (Mac|PC)\. Puoi continuare a usare il computer\.$/, "Just once: downloading the models to your $1. You can keep using the computer."],
    [/^Integrato è gratuito e resta sul (Mac|PC); Claude è a pagamento\.$/, "Built-in is free and stays on your $1; Claude is paid."],
    [/^Resta solo su questo (Mac|PC), nel file impostazioni\.json\.$/, "Stays only on this $1, in the impostazioni.json file."],
    [/^(.+) · (\d+) GB di memoria · (.+) GB liberi$/, "$1 · $2 GB of memory · $3 GB free"],
    [/^Ancora (\d+) clic…$/, "$1 more clicks…"],
    [/^Quanta lezione il modello legge insieme\. Automatica in base al tuo (Mac|PC)\.$/, "How much of the lecture the model reads at once. Automatic, based on your $1."],
    [/^Come il (Mac|PC)$/, "Like the $1"],
    [/^Audio, trascrizioni e appunti restano in questa cartella, sul tuo (Mac|PC)\.$/, "Audio, transcripts and notes stay in this folder, on your $1."],
    [/^Passo (\d+) di (\d+)$/, "Step $1 of $2"],
    [/^Trasformo le registrazioni delle lezioni .* sul tuo (Mac|PC): .*$/, "I turn lecture recordings into clear notes, with diagrams, glossary and review questions. Everything runs on your $1: free, no account, and the audio never leaves the computer."],
    [/^Scegliamo l'AI per il tuo (Mac|PC)$/, "Let's choose the AI for your $1"],
    [/^Controlla che il server sia acceso \(sbobina server\) e ricarica la pagina\. Dettaglio: (.*)$/, "Check that the server is running (sbobina server) and reload the page. Detail: $1"],
    [/^Scarico (.+): (.+) di (.+) GB$/, "Downloading $1: $2 of $3 GB"],
    [/^Connessione ferma, riprovo a scaricare (.+)…$/, "Connection stalled, retrying the download of $1…"],
    [/^Riconoscimento vocale \((.+)\)$/, "Speech recognition ($1)"],
    [/^Correzione di (\d+) punti segnalati$/, "Correcting $1 flagged points"],
    [/^Formato audio non supportato: (.+)$/, "Unsupported audio format: $1"],
    [/^Non ci sono ancora appunti pronti(.*)\.$/, (_, c) => `There are no ready notes yet${c.replace(" per ", " for ")}.`],
    [/^Il motore (.+) non è riuscito \((.+)\); usati gli altri\.$/, "The $1 engine failed ($2); the others were used."],
    [/^(.+): PDF troppo grande, usato solo il testo \(senza immagini\)\.$/, "$1: PDF too large, only its text was used (no images)."],
    [/^(.+): PDF troppo grande e senza testo estraibile, ignorato\.$/, "$1: PDF too large and without extractable text, skipped."],
    [/^(.+): non utilizzabile \((.+)\)\.$/, "$1: not usable ($2)."],
  ];

  function tr(testo) {
    if (Object.prototype.hasOwnProperty.call(EN, testo)) return EN[testo];
    if (testo.endsWith("…") && EN[testo.slice(0, -1)]) return EN[testo.slice(0, -1)] + "…";
    for (const [espressione, sostituzione] of MODELLI) {
      if (espressione.test(testo)) return testo.replace(espressione, sostituzione);
    }
    return testo;
  }

  // Il contenuto (appunti, trascrizioni, risposte, campi in cui si scrive) non si tocca.
  const ESCLUSI = ".appunti, .trascrizione, textarea, pre, code, [contenteditable]";
  const ATTRIBUTI = ["placeholder", "title", "aria-label", "data-titolo", "data-avviso"];

  function traduciTesto(nodo) {
    const grezzo = nodo.data;
    const testo = grezzo.trim();
    if (!testo || !/[a-zà-ù]/i.test(testo)) return;
    const tradotto = tr(testo);
    if (tradotto !== testo) nodo.data = grezzo.replace(testo, tradotto);
  }

  function traduciElemento(el) {
    for (const nome of ATTRIBUTI) {
      const valore = el.getAttribute(nome);
      if (valore) {
        const tradotto = tr(valore.trim());
        if (tradotto !== valore.trim()) el.setAttribute(nome, tradotto);
      }
    }
  }

  function traduci(radice) {
    if (radice.nodeType === Node.TEXT_NODE) {
      if (!radice.parentElement || !radice.parentElement.closest(ESCLUSI)) traduciTesto(radice);
      return;
    }
    if (radice.nodeType !== Node.ELEMENT_NODE) return;
    if (radice.closest(ESCLUSI)) { if (radice.tagName === "TEXTAREA") traduciElemento(radice); return; }
    traduciElemento(radice);
    const giro = document.createTreeWalker(radice, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => {
        if (n.nodeType !== Node.ELEMENT_NODE || !n.matches(ESCLUSI)) return NodeFilter.FILTER_ACCEPT;
        if (n.tagName === "TEXTAREA") traduciElemento(n);  // il testo scritto no, il segnaposto sì
        return NodeFilter.FILTER_REJECT;
      },
    });
    while (giro.nextNode()) {
      const n = giro.currentNode;
      if (n.nodeType === Node.TEXT_NODE) traduciTesto(n);
      else traduciElemento(n);
    }
  }

  let osservatore = null;
  window.SbobinaLingua = function (lingua) {
    document.documentElement.lang = lingua;
    try { localStorage.setItem("sbobina-lingua", lingua); } catch (e) { /* senza storage resta la scelta del server */ }
    if (lingua !== "en" && osservatore) location.reload();  // i testi già tradotti tornano italiani solo ridisegnando
    if (lingua !== "en" || osservatore) return;
    traduci(document.body);
    document.title = "Sbobina";
    osservatore = new MutationObserver((cambi) => {
      for (const c of cambi) {
        if (c.type === "childList") c.addedNodes.forEach(traduci);
        else if (c.type === "characterData") traduci(c.target);
        else if (c.type === "attributes" && !c.target.closest(ESCLUSI)) traduciElemento(c.target);
      }
    });
    osservatore.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTI });
  };
  window.SbobinaTraduci = tr;
  for (const nome of ["alert", "confirm"]) {
    const originale = window[nome].bind(window);
    window[nome] = (testo) => originale(document.documentElement.lang === "en" ? tr(String(testo)) : testo);
  }

  // Prima del primo disegno: l'ultima lingua scelta, poi /api/stato conferma.
  let salvata = "it";
  try { salvata = localStorage.getItem("sbobina-lingua") || "it"; } catch (e) { /* storage non disponibile */ }
  if (salvata === "en") document.addEventListener("DOMContentLoaded", () => window.SbobinaLingua("en"));
})();
