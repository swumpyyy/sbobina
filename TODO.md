# Sbobina: da fare (12/10/2026)

GIVE ME IDEAS PLEASEEEEEE 

## Windows 1.4 (le novità della 1.4 per ora escono solo per Mac)
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
