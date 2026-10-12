# Sbobina

**Dalle registrazioni delle lezioni ad appunti di studio accurati, con schemi e mappe concettuali.**

Sbobina non registra: prende gli audio che hai già (note vocali del telefono, registratore, file
di Teams/Zoom…) e li trasforma in appunti completi, pensati per studiare e preparare l'esame.
L'obiettivo è l'accuratezza: ogni passaggio è progettato per ridurre gli errori di trascrizione e
per non far inventare nulla agli appunti.

## Cosa ottieni per ogni lezione

- **Appunti completi in Markdown**: definizioni, teoremi con ipotesi e tesi, dimostrazioni ed
  esercizi con tutti i passaggi, esempi, formule in LaTeX, tabelle di confronto.
- **Mappa concettuale** interattiva della lezione e **schemi** (flussi, processi, classificazioni).
- **Indicazioni del docente**: tutto ciò che è stato segnalato come importante o "da esame" (⭐).
- **Glossario** dei termini tecnici e **domande di ripasso** con risposta nascosta.
- **Tempi cliccabili** `⏱ 23:15`: un clic e riascolti quel punto della registrazione.
- **Trascrizione revisionata** completa e un **rapporto di verifica** con i problemi trovati e corretti.
- Esportazione in **PDF** (versione stampabile) e **Markdown** (per Obsidian, Notion, ecc.).

## Perché è accurato

Un'app che "registra e scrive" fa una trascrizione e un riassunto. Sbobina fa sei passaggi:

1. **Audio ripulito**: ffmpeg converte qualsiasi formato, toglie i rimbombi e uniforma il volume
   (utile quando il docente si allontana dal microfono).
2. **Termini dalle slide**: se carichi slide o dispense, Claude ne estrae termini tecnici, nomi e
   sigle e li passa al riconoscimento vocale, che così li scrive giusti.
3. **Trascrizione con uno o due motori**: AssemblyAI (Universal-3.5 Pro) ed ElevenLabs (Scribe v2)
   sono tra i più accurati sull'italiano; Whisper large-v3 funziona in locale e gratis. Con due
   motori attivi, l'audio viene trascritto due volte in modo indipendente.
4. **Revisione della trascrizione**: Claude la corregge blocco per blocco (termini, nomi, formule
   dettate a voce, punteggiatura) usando glossario e materiali. Quando i due motori non sono
   d'accordo sceglie la versione giusta. Non riassume e non aggiunge nulla: i punti dubbi restano
   segnati come `[incerto]`.
5. **Appunti**: scritti dalla trascrizione revisionata e dalle slide. Ciò che non è stato detto a
   lezione può comparire solo in un riquadro **Integrazione**, ben distinto.
6. **Verifica e correzione**: una seconda lettura confronta gli appunti con la trascrizione frase per
   frase (affermazioni non supportate, formule o ipotesi sbagliate, contenuti omessi, schemi errati)
   e una terza applica le correzioni.

In più il **glossario del corso cresce da solo**: i termini di ogni lezione vengono usati per
riconoscere meglio le lezioni successive dello stesso corso. Puoi modificarlo dall'app (ad esempio
aggiungendo il nome del docente).

## Installazione

Ti servono **Python 3.10 o più recente** e **ffmpeg**.

```bash
# ffmpeg
brew install ffmpeg            # macOS
sudo apt install ffmpeg        # Ubuntu/Debian
winget install ffmpeg          # Windows

# Sbobina
git clone <questo repository> sbobina && cd sbobina
python -m venv .venv
source .venv/bin/activate      # su Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env           # poi apri .env e inserisci le chiavi
```

Nel file `.env`:

| Chiave | Serve per | Dove si ottiene |
|---|---|---|
| `ANTHROPIC_API_KEY` | **obbligatoria**: revisione, appunti, verifica | console.anthropic.com |
| `ASSEMBLYAI_API_KEY` | trascrizione cloud (consigliata) | assemblyai.com |
| `ELEVENLABS_API_KEY` | seconda trascrizione cloud (massima accuratezza) | elevenlabs.io |

Senza chiavi di trascrizione Sbobina usa **Whisper in locale**: installalo con
`pip install -e ".[locale]"`. È gratuito e l'audio non lascia il tuo computer, ma senza una
scheda video NVIDIA una lezione di 90 minuti può richiedere più di un'ora. Per andare più veloce
puoi impostare `SBOBINA_WHISPER_MODELLO=large-v3-turbo`, un po' meno accurato.

Controlla la configurazione con:

```bash
sbobina stato
```

## Uso

### App web

```bash
sbobina server
```

Si apre il browser su `http://localhost:8000`. Clicca **+ Nuova lezione** e carica:

- **la registrazione** (puoi selezionare più file: ognuno diventa una lezione);
- **il corso** (raggruppa le lezioni e il glossario);
- facoltativi ma molto utili: **slide/dispense** in PDF, **foto della lavagna**, **nomi e termini
  difficili** (es. il nome del docente), **indicazioni** (es. "insistere sulle dimostrazioni").

Segui l'avanzamento in tempo reale. Puoi chiudere il browser: l'elaborazione continua finché il
server è acceso, e se lo spegni a metà riprende dall'ultimo passo completato.

### Tutte le registrazioni insieme, da terminale

```bash
# una cartella intera di registrazioni dello stesso corso
sbobina elabora ~/Registrazioni/Analisi1/ --corso "Analisi 1" --materiali slide/*.pdf

# una singola lezione
sbobina elabora lezione07.m4a --corso "Fisica 1" --titolo "Lezione 7 – Dinamica" \
    --termini "Newton, D'Alembert, quantità di moto"

sbobina elenco                      # tutte le lezioni con il loro stato
sbobina rielabora <id> --da appunti # riscrive gli appunti (es. dopo aver corretto il glossario)
```

Gli appunti finiscono in `dati/lezioni/<id>/appunti.md` e `appunti.html` (aprila e usa
"Stampa → Salva come PDF").

## Costi

- **Claude**: con Claude Opus 5.5 una lezione di 90 minuti costa indicativamente **2-4 $**, perché
  la trascrizione viene letta più volte (revisione, appunti, verifica, correzione). La cache del
  prompt riduce il costo delle letture successive. L'app mostra il costo stimato di ogni lezione.
  Per spendere meno: `SBOBINA_MODELLO=claude-sonnet-5-5` (circa la metà) oppure `SBOBINA_VERIFICA=0`
  (salta verifica e correzione, meno accurato).
- **Trascrizione**: AssemblyAI ed ElevenLabs si pagano a ore di audio; controlla i loro listini.
  ElevenLabs applica un supplemento quando si passano i termini del glossario. Whisper locale è
  gratuito.

## Consigli per registrare (l'accuratezza parte da qui)

- Siediti nelle prime file o appoggia il telefono vicino alla cattedra, con il microfono verso il docente.
- Modalità aereo durante la registrazione: niente vibrazioni o notifiche nell'audio.
- Un file per lezione. Se la registrazione si interrompe, carica i pezzi come lezioni separate.
- Carica le slide della lezione: è il modo più efficace per avere termini, formule e nomi corretti.

## Privacy

L'audio resta sul tuo computer, salvo quando usi i servizi cloud di trascrizione (AssemblyAI,
ElevenLabs), a cui viene inviato l'audio. Trascrizione e materiali vengono inviati a Claude
(Anthropic) per scrivere gli appunti. Tutti i risultati sono salvati in locale nella cartella `dati/`.
Il server ascolta solo su `localhost`.

## Struttura del progetto

```
sbobina/
  audio.py              preparazione dell'audio con ffmpeg
  trascrizione/         motori: AssemblyAI, ElevenLabs, Whisper locale
  materiali.py          slide PDF, immagini, testi → contenuti per Claude
  prompt.py             istruzioni per Claude (revisione, appunti, verifica, correzione)
  llm.py                chiamate a Claude (streaming, ragionamento adattivo, fallback)
  pipeline.py           le fasi dell'elaborazione, con ripresa dai punti salvati
  archivio.py           lezioni e corsi salvati come file JSON
  server.py, static/    app web
  cli.py                comandi da terminale
tests/                  test automatici (pytest)
```

Per ogni lezione, `dati/lezioni/<id>/` contiene `originale.*`, `ascolto.mp3`,
`trascrizione_<motore>.json` (trascrizione grezza con i tempi di ogni parola), `trascrizione.md`
(revisionata), `appunti_bozza.md`, `verifica.json`, `appunti.md` e `appunti.html`.

## Sviluppo

```bash
pip install -e ".[dev,locale]"
pytest
```

I test non usano servizi a pagamento: Claude e i motori di trascrizione sono sostituiti da versioni
finte, mentre ffmpeg, l'SDK di Anthropic (con un trasporto HTTP simulato) e l'app web sono reali.
