# Sbobina: da fare (12/10/2026)

## 0. Da riprendere (lavoro interrotto)
- [x] Finire il test e2e: `sbobina rielabora --da riprendi test-e2e-lezione-5-63488c` (fermo al 75%, appunti)
- [x] Rifare la build: `zsh scripts/crea_app_macos.sh --dmg`, poi aprire il DMG e provarlo
- [x] Commit di tutto il lavoro non salvato (vendor, sistema.py, fix think, repo_mlx, --dmg)

## 1. Stop dell'AI (richiesto)
- [x] Pulsante "Ferma" visibile durante trascrizione, revisione, appunti, verifica
- [x] Backend: `POST /api/lezioni/{id}/ferma`, annullamento cooperativo in `Elaborazione` (controllo tra blocchi + chiusura richiesta Ollama)
- [x] Stato "fermata" (non "errore") + pulsante "Riprendi" che riparte dall'ultimo blocco salvato

## 2. PDF scaricabili (richiesto)
- [x] Pulsante "Scarica PDF" che salva il file direttamente (nell'app nativa: finestra Salva di macOS, non la stampa)
- [x] Scelte PDF: solo appunti / appunti + approfondimento / con trascrizione; copertina con corso, data, durata
- [x] "Esporta tutto il corso" in un unico PDF con indice

## 3. Menu iniziale / onboarding (richiesto)
- [x] Primo avvio guidato: benvenuto → università, corso, area di studio, anno → scelta modello in base alla RAM (`sistema.py`) → download Ollama + modello + Whisper con barra di avanzamento
- [x] Schermata iniziale nuova: zona "inserisci il nastro" per trascinare l'audio + contatori reali (lezioni, ore sbobinate)

## 4. Impostazioni (richiesto)
- [x] Pagina Impostazioni salvata in `impostazioni.json` (Application Support)
- [x] Appunti: lunghezza, stile, sezioni on/off (mappa, schemi, domande, glossario, approfondimento, verifica)
- [x] AI: modello locale o Claude (chiave API), modello Whisper
- [x] AI avanzate: scelta/scaricamento modello LLM, temperatura, lunghezza contesto, prompt personalizzabile per sezione
- [x] Aspetto: tema chiaro/scuro/sistema, animazioni ridotte, dimensione testo, colori/accento
- [x] LLM integrato senza Ollama: generare gli appunti in-process con `mlx-lm` (come già mlx-whisper), modello Gemma MLX scaricato da HF in Application Support. Tenere Ollama come opzione finché non è testato. Niente reverse engineering: Ollama è open source, non serve
- [x] Notifiche e suono a fine lezione; cartella dati

## 5. Animazioni più fluide (richiesto)
- [x] Le schede Appunti/Trascrizione/Verifica non devono ricostruire tutto il DOM: cambiare solo il pannello e far scorrere l'indicatore
- [x] Transizioni tra lezioni, comparsa progressiva degli appunti, avanzamento del VU meter animato
- [x] Rispettare "riduci movimento" di macOS

## 6. Altre funzioni (idee prese da Notion AI, Otter, Notability, Glean, Anki)
- [x] Registrazione dal microfono dentro l'app, con VU meter reale (ffmpeg astats)
- [x] "Chiedi alla lezione": chat sulla lezione con risposte che citano il minuto
- [x] Ripasso: flashcard generate dagli appunti, ripetizione spaziata (Leitner)
- [x] Quiz di verifica a scelta multipla per ogni lezione
- [x] Clic su un timestamp → l'audio salta a quel punto (già parziale: estendere a tutto il testo)
- [x] Ricerca in tutte le lezioni (testo degli appunti e trascrizioni)
- [x] Modifica degli appunti a mano, con salvataggio
- [x] Coda di più audio in fila, con stima del tempo rimanente
- [x] Badge sul Dock e notifica macOS a fine elaborazione
- [x] Esportazione Markdown/Obsidian e Anki (.apkg)
- [x] Velocità di riproduzione audio (1x/1.5x/2x)

## 7. Distribuzione
- [x] Arrestare `ollama serve` quando si chiude l'app (se l'ha avviato Sbobina)
- [x] Spostare i dati della lezione di prova da `dati/` ad Application Support
- [ ] Facoltativo: Apple Developer ID ($99/anno) + notarizzazione, così niente "Apri comunque"
- [x] Aggiornare README, DESIGN.md, screenshot

## 8. Windows 1.4 (le novità della 1.4 per ora escono solo per Mac)
Il codice è già lo stesso (tag `v1.4.0`): per Windows serve solo provarlo su un PC vero e poi pubblicare lo zip.
Pacchetto pronto: `git archive --prefix=Sbobina/ v1.4.0 ':(exclude)docs' ':(exclude)tests' -o dist/Sbobina-Windows.zip`.
- [ ] Versione di WebView2 ≥ 123 (edge://version dentro l'app): i colori del tema usano `oklch(from light-dark(…))`, con ripiego `color-mix`
- [ ] Tutti i temi (Jev, Menta, Arancio, Cobalto, Limone, Seppia, Tuo colore) in chiaro e scuro: barre del titolo, tasti, avviso «Salvato», barra di avanzamento a celle
- [ ] Barra di avanzamento durante il download dei modelli e durante l'elaborazione (il pieno si taglia, non si schiaccia)
- [ ] «Chiedi alle tue lezioni» con llama.cpp su 8 GB di VRAM: contesto automatico (32768) e 16384, più lezioni, nessun errore di contesto
- [ ] Sezione nerd (5 clic su «Impostazioni»): numeri di llama.cpp (token, tok/s, primo token, durata, nome del GGUF) in Chiedi; riga di faster-whisper (audio ascoltato, velocità ×) in «dietro le quinte», con CUDA e con la CPU
- [ ] Chiedi mentre una lezione si trascrive: faster-whisper ferma llama-server; il messaggio d'errore deve essere chiaro
- [ ] Tasti ↵ / ⇧↵ nel piede della chat (font mono) e Maiusc+Invio che va a capo
- [ ] In alto a sinistra «SBOBINA.OS 1.4»; `pip install -e .` riporta 1.4.0
- [ ] Installazione pulita con «Installa Sbobina.bat», poi: togliere la nota «Per ora è la versione 1.2» dal README e caricare lo zip nuovo nella release
