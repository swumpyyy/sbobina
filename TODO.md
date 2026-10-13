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
