"""Elaborazione di una lezione.

audio → termini dai materiali → trascrizione (uno o più motori) → revisione a blocchi
→ appunti → verifica → correzione → esportazione.

Ogni fase salva il proprio risultato su file: se qualcosa si interrompe, la lezione
riparte dall'ultimo passo completato senza ripagare quelli già fatti.
"""

from __future__ import annotations

import logging
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sbobina import audio, prompt
from sbobina.archivio import Archivio, Lezione, leggi_json, scrivi_atomico, scrivi_json, unisci_termini
from sbobina.config import Config
from sbobina.esporta import esporta_html
from sbobina import impostazioni
from sbobina.llm import FERMA, ErroreClaude, ErroreRipetizione, Fermata, ModelloLinguistico, Utilizzo
from sbobina.materiali import Materiali, carica_materiali
from sbobina.trascrizione.base import (
    Blocco,
    ErroreTrascrizione,
    MotoreTrascrizione,
    Trascrizione,
    estrai_testo,
    in_blocchi,
    in_righe,
    tempo,
)

log = logging.getLogger(__name__)

# fase: (etichetta, inizio, fine) della barra di avanzamento
FASI = {
    "audio": ("Preparazione dell'audio", 0.00, 0.04),
    "termini": ("Analisi dei materiali", 0.04, 0.07),
    "trascrizione": ("Trascrizione", 0.07, 0.55),
    "revisione": ("Revisione della trascrizione", 0.55, 0.75),
    "appunti": ("Scrittura degli appunti", 0.75, 0.85),
    "verifica": ("Verifica dell'accuratezza", 0.85, 0.90),
    "correzione": ("Correzione finale", 0.90, 0.93),
    "approfondimento": ("Approfondimento", 0.93, 0.99),
}

# "riprendi" continua dall'ultimo passo salvato; le altre cancellano i risultati da quella fase in poi.
RIPARTENZE = ("riprendi", "appunti", "revisione", "tutto")


class File:
    """Percorsi dei file di una lezione. Ogni file è anche un punto di ripresa."""

    def __init__(self, cartella: Path):
        self.cartella = cartella
        self.lavoro = cartella / "lavoro"
        self.audio_trascrizione = self.lavoro / "audio.flac"
        self.termini = self.lavoro / "termini.json"
        self.revisione = self.lavoro / "revisione"
        self.materiali = cartella / "materiali"
        self.ascolto = cartella / "ascolto.mp3"
        self.trascrizione = cartella / "trascrizione.md"
        self.bozza = cartella / "appunti_bozza.md"
        self.verifica = cartella / "verifica.json"
        self.appunti = cartella / "appunti.md"
        self.html = cartella / "appunti.html"
        self.approfondimento = cartella / "approfondimento.md"
        self.pdf = cartella / "appunti.pdf"

    def trascrizione_motore(self, motore: str) -> Path:
        return self.cartella / f"trascrizione_{motore}.json"

    def blocco(self, indice: int) -> Path:
        return self.revisione / f"blocco_{indice:03d}.md"


def pulisci_markdown(testo: str) -> str:
    """Toglie un eventuale blocco ```markdown che racchiude l'intera risposta."""
    testo = testo.strip()
    racchiuso = re.fullmatch(r"```(?:markdown|md)\s*\n(.*)\n```", testo, re.S)
    return (racchiuso.group(1) if racchiuso else testo).strip()


def numero_parole(testo: str) -> int:
    return len(re.sub(r"\[\d{1,2}:\d{2}(?::\d{2})?\]", " ", testo).split())


def prepara_rielaborazione(archivio: Archivio, id_lezione: str, da: str) -> Lezione:
    """Cancella i risultati dalla fase indicata in poi e rimette la lezione in coda."""
    if da not in RIPARTENZE:
        raise ValueError(f"Fase di ripartenza non valida: {da} (ammesse: {', '.join(RIPARTENZE)})")
    f = File(archivio.cartella(id_lezione))
    da_togliere = [] if da == "riprendi" else [f.bozza, f.verifica, f.appunti, f.html, f.approfondimento, f.pdf]
    if da in ("revisione", "tutto"):
        da_togliere.append(f.trascrizione)
        shutil.rmtree(f.revisione, ignore_errors=True)
    if da == "tutto":
        da_togliere += [*f.cartella.glob("trascrizione_*.json"), f.termini]
    for percorso in da_togliere:
        percorso.unlink(missing_ok=True)
    return archivio.aggiorna(
        id_lezione, stato="in_coda", fase="In coda", progresso=0.0, errore="", messaggio="", avvisi=[]
    )


class Elaborazione:
    def __init__(
        self, config: Config, archivio: Archivio, llm: ModelloLinguistico, motori: list[MotoreTrascrizione]
    ):
        self.config = config
        self.archivio = archivio
        self.llm = llm
        self.motori = motori
        self.imp = impostazioni.Impostazioni()
        self._lock = threading.Lock()
        self._ultimo_aggiornamento: tuple[float, str, str] = (0.0, "", "")

    # --- stato e avanzamento ----------------------------------------------

    def _avanza(self, id_lezione: str, fase: str, frazione: float, messaggio: str = "") -> None:
        if FERMA.is_set():
            raise Fermata()
        etichetta, inizio, fine = FASI[fase]
        progresso = round(inizio + (fine - inizio) * max(0.0, min(1.0, frazione)), 3)
        with self._lock:
            istante, ultima_fase, ultimo_messaggio = self._ultimo_aggiornamento
            if (
                time.monotonic() - istante < 1.0
                and etichetta == ultima_fase
                and messaggio == ultimo_messaggio
                and frazione < 1.0
            ):
                return
            self._ultimo_aggiornamento = (time.monotonic(), etichetta, messaggio)
        self.archivio.aggiorna(id_lezione, fase=etichetta, progresso=progresso, messaggio=messaggio)

    def _avviso(self, id_lezione: str, testo: str) -> None:
        log.warning("[%s] %s", id_lezione, testo)
        self.archivio.modifica(id_lezione, lambda lez: lez.avvisi.append(testo))

    def _registra(self, id_lezione: str, fase: str, utilizzo: Utilizzo) -> None:
        def somma(lezione: Lezione) -> None:
            lezione.utilizzo[fase] = (Utilizzo.da_dict(lezione.utilizzo.get(fase)) + utilizzo).a_dict()

        self.archivio.modifica(id_lezione, somma)

    # --- esecuzione -------------------------------------------------------

    def esegui(self, id_lezione: str) -> Lezione:
        FERMA.clear()
        self.imp = impostazioni.carica(self.config.cartella_dati)
        self.archivio.aggiorna(id_lezione, stato="in_elaborazione", errore="", messaggio="", avvisi=[])
        inizio = time.monotonic()

        def conta(lez: Lezione) -> None:
            lez.secondi_elaborazione = round(lez.secondi_elaborazione + time.monotonic() - inizio, 1)

        try:
            self._esegui(id_lezione)
        except Fermata:
            # I blocchi già salvati restano: "Riprendi" riparte da lì.
            self.archivio.modifica(id_lezione, conta)
            return self.archivio.aggiorna(id_lezione, stato="fermata", messaggio="")
        except Exception as e:  # noqa: BLE001 - l'errore va mostrato all'utente, non perso
            log.exception("Elaborazione di %s non riuscita", id_lezione)
            return self.archivio.aggiorna(
                id_lezione, stato="errore", errore=str(e) or type(e).__name__, messaggio=""
            )
        self.archivio.modifica(id_lezione, conta)
        return self.archivio.aggiorna(
            id_lezione, stato="completata", fase="Completata", progresso=1.0, messaggio=""
        )

    def _esegui(self, id_lezione: str) -> None:
        lezione = self.archivio.carica(id_lezione)
        f = File(self.archivio.cartella(id_lezione))

        self._fase_audio(lezione, f)
        materiali = carica_materiali(f.materiali, lezione.materiali, f.lavoro)
        for avviso in materiali.avvisi:
            self._avviso(lezione.id, avviso)
        termini = self._fase_termini(lezione, f, materiali)
        trascrizioni = self._fase_trascrizione(lezione, f, termini)
        trascrizione = self._fase_revisione(lezione, f, trascrizioni, termini, materiali)

        base = prompt.contenuto_lezione(
            corso=lezione.corso,
            titolo=lezione.titolo,
            data=lezione.data,
            note=lezione.note,
            blocchi_materiali=materiali.blocchi,
            trascrizione=trascrizione,
        )
        bozza = self._fase_appunti(lezione, f, base)
        verifica = self._fase_verifica(lezione, f, base, bozza)
        appunti = self._fase_correzione(lezione, f, base, bozza, verifica)
        self._fase_approfondimento(lezione, f, base, appunti)

        if verifica:
            # Il glossario del corso cresce lezione dopo lezione e migliora le trascrizioni successive.
            self.archivio.aggiungi_al_glossario(lezione.corso, verifica.get("termini_chiave", []))
        scrivi_atomico(
            f.html,
            esporta_html(titolo=lezione.titolo, corso=lezione.corso, data=lezione.data, appunti=appunti),
        )

    # --- fasi -------------------------------------------------------------

    def _fase_audio(self, lezione: Lezione, f: File) -> None:
        originale = f.cartella / lezione.file_audio
        serve_flac = not f.trascrizione.is_file() and any(
            not f.trascrizione_motore(m.nome).is_file() for m in self.motori
        )
        if lezione.durata_secondi and f.ascolto.is_file() and (f.audio_trascrizione.is_file() or not serve_flac):
            return
        self._avanza(lezione.id, "audio", 0.0, "Conversione e normalizzazione del volume")
        if not lezione.durata_secondi:
            self.archivio.aggiorna(lezione.id, durata_secondi=audio.durata(originale))
        if not f.ascolto.is_file():
            audio.prepara_per_ascolto(originale, f.ascolto)
        if serve_flac and not f.audio_trascrizione.is_file():
            audio.prepara_per_trascrizione(originale, f.audio_trascrizione)
        self._avanza(lezione.id, "audio", 1.0)

    def _fase_termini(self, lezione: Lezione, f: File, materiali: Materiali) -> list[str]:
        corso = self.archivio.carica_corso(lezione.corso)
        glossario = corso.glossario if corso else []
        estratti: list[str] = []
        if f.termini.is_file():
            estratti = leggi_json(f.termini).get("termini", [])
        elif materiali.presenti and not f.trascrizione.is_file():
            self._avanza(lezione.id, "termini", 0.1, "Lettura dei materiali per i termini tecnici")
            try:
                dati, uso = self.llm.json(
                    system=prompt.SYSTEM_TERMINI,
                    contenuto=prompt.contenuto_termini(lezione.corso, lezione.titolo, materiali.blocchi),
                    schema=prompt.SCHEMA_TERMINI,
                    sforzo="medium",
                    max_tokens=16000,
                )
                self._registra(lezione.id, "termini", uso)
                estratti = [t for t in dati.get("termini", []) if isinstance(t, str)]
                scrivi_json(f.termini, {"termini": estratti})
            except ErroreClaude as e:
                self._avviso(lezione.id, f"Termini dai materiali non estratti: {e}")
        # Prima i termini di questa lezione, poi quelli accumulati dal corso.
        return unisci_termini(estratti, glossario)

    def _fase_trascrizione(self, lezione: Lezione, f: File, termini: list[str]) -> list[Trascrizione]:
        if f.trascrizione.is_file():
            return []  # revisione già completata: le trascrizioni grezze non servono più
        risultati: dict[str, Trascrizione] = {}
        da_fare: list[MotoreTrascrizione] = []
        for motore in self.motori:
            percorso = f.trascrizione_motore(motore.nome)
            if percorso.is_file():
                risultati[motore.nome] = Trascrizione.da_dict(leggi_json(percorso))
            else:
                da_fare.append(motore)

        errori: dict[str, str] = {}
        if da_fare:
            contesto = f"Lezione universitaria di {lezione.corso}: {lezione.titolo}."
            avanzamenti = {m.nome: 0.0 for m in da_fare}
            nomi = ", ".join(m.nome for m in da_fare)

            def avanzamento(nome: str, frazione: float) -> None:
                with self._lock:
                    avanzamenti[nome] = frazione
                    media = sum(avanzamenti.values()) / len(avanzamenti)
                self._avanza(lezione.id, "trascrizione", media, f"Riconoscimento vocale ({nomi})")

            def trascrivi(motore: MotoreTrascrizione) -> Trascrizione:
                risultato = motore.trascrivi(
                    f.audio_trascrizione,
                    lingua=self.config.lingua,
                    termini=termini,
                    contesto=contesto,
                    avanzamento=lambda x: avanzamento(motore.nome, x),
                )
                scrivi_json(f.trascrizione_motore(motore.nome), risultato.a_dict())
                return risultato

            avanzamento(da_fare[0].nome, 0.0)
            with ThreadPoolExecutor(max_workers=len(da_fare)) as pool:
                futuri = {m.nome: pool.submit(trascrivi, m) for m in da_fare}
                for nome, futuro in futuri.items():
                    try:
                        risultati[nome] = futuro.result()
                    except Fermata:
                        raise  # pausa dello studente, non un errore del motore
                    except Exception as e:  # noqa: BLE001 - con più motori, uno può fallire
                        log.exception("Motore %s non riuscito", nome)
                        errori[nome] = str(e) or type(e).__name__

        ordinate = [risultati[m.nome] for m in self.motori if m.nome in risultati and risultati[m.nome].parole]
        if not ordinate:
            if errori:
                raise ErroreTrascrizione(
                    "Trascrizione non riuscita. " + " ".join(f"{n}: {e}" for n, e in errori.items())
                )
            raise ErroreTrascrizione("Nessuna parola riconosciuta: l'audio sembra vuoto o in un'altra lingua.")
        for nome, errore in errori.items():
            self._avviso(lezione.id, f"Il motore {nome} non è riuscito ({errore}); usati gli altri.")
        if not errori:
            f.audio_trascrizione.unlink(missing_ok=True)
        self.archivio.aggiorna(lezione.id, motori=[t.motore for t in ordinate])
        self._avanza(lezione.id, "trascrizione", 1.0)
        return ordinate

    def _fase_revisione(
        self,
        lezione: Lezione,
        f: File,
        trascrizioni: list[Trascrizione],
        termini: list[str],
        materiali: Materiali,
    ) -> str:
        if f.trascrizione.is_file():
            return f.trascrizione.read_text(encoding="utf-8")
        principale, *alternative = trascrizioni
        blocchi = in_blocchi(in_righe(principale.parole), self.config.minuti_per_blocco * 60)
        system = prompt.system_revisione(lezione.corso, lezione.titolo, lezione.note, termini, materiali.testo)
        totale = len(blocchi)
        completati = [sum(1 for b in blocchi if f.blocco(b.indice).is_file())]

        def rivedi(blocco: Blocco) -> None:
            precedenti = blocchi[blocco.indice - 1].righe[-2:] if blocco.indice else []
            contesto = "\n".join(f"[{tempo(r.inizio)}] {r.testo}" for r in precedenti)
            altre = [(t.motore, estrai_testo(t.parole, blocco.inizio, blocco.fine)) for t in alternative]
            testo = self._rivedi_blocco(lezione.id, system, blocco, totale, contesto, altre)
            scrivi_atomico(f.blocco(blocco.indice), testo + "\n")
            with self._lock:
                completati[0] += 1
                fatti = completati[0]
            self._avanza(lezione.id, "revisione", fatti / totale, f"Blocco {fatti} di {totale}")

        da_fare = [b for b in blocchi if not f.blocco(b.indice).is_file()]
        self._avanza(lezione.id, "revisione", completati[0] / totale, f"Blocco {completati[0]} di {totale}")
        if da_fare:
            # Il primo blocco da solo scrive la cache del contesto (istruzioni, glossario, slide)
            # che i blocchi successivi, in parallelo, rileggono a costo ridotto.
            rivedi(da_fare[0])
            with ThreadPoolExecutor(max_workers=self.config.richieste_parallele) as pool:
                list(pool.map(rivedi, da_fare[1:]))

        testo = "\n\n".join(f.blocco(b.indice).read_text(encoding="utf-8").strip() for b in blocchi)
        scrivi_atomico(f.trascrizione, testo + "\n")
        return testo

    def _rivedi_blocco(
        self,
        id_lezione: str,
        system: list[dict],
        blocco: Blocco,
        totale: int,
        contesto: str,
        alternative: list[tuple[str, str]],
    ) -> str:
        migliore = ""
        for insisti in (False, True):
            messaggio = prompt.messaggio_revisione(blocco, totale, contesto, alternative, insisti=insisti)
            try:
                testo, uso = self.llm.testo(
                    system=system,
                    contenuto=[{"type": "text", "text": messaggio}],
                    sforzo=self.config.sforzo_revisione,
                    # La revisione è lunga quanto il blocco (~2 token a parola): un tetto basso ferma
                    # in pochi minuti un modello entrato in loop invece di lasciarlo girare per mezz'ora.
                    max_tokens=max(2048, blocco.numero_parole * 4),
                )
            except ErroreRipetizione:
                if not insisti:
                    continue
                self._avviso(
                    id_lezione,
                    f"Il blocco {tempo(blocco.inizio)} non è stato rivisto (il modello si ripeteva): resta la trascrizione originale.",
                )
                return migliore or blocco.testo
            self._registra(id_lezione, "revisione", uso)
            testo = pulisci_markdown(testo)
            if not re.match(r"\[\d{1,2}:\d{2}", testo):
                testo = f"[{tempo(blocco.inizio)}] {testo}"
            if numero_parole(testo) > numero_parole(migliore):
                migliore = testo
            # Una revisione molto più corta dell'originale vuol dire che il blocco è stato
            # riassunto: si riprova una volta chiedendo esplicitamente di non tagliare.
            if blocco.numero_parole < 80 or numero_parole(testo) >= 0.6 * blocco.numero_parole:
                return testo
        self._avviso(
            id_lezione,
            f"Il blocco {tempo(blocco.inizio)} risulta più corto dell'audio originale: controlla quel tratto.",
        )
        return migliore

    def _fase_appunti(self, lezione: Lezione, f: File, base: list[dict]) -> str:
        if f.bozza.is_file():
            return f.bozza.read_text(encoding="utf-8")
        self._avanza(lezione.id, "appunti", 0.05, "Sto scrivendo gli appunti (qualche minuto)")
        testo, uso = self.llm.testo(
            system=prompt.SYSTEM_APPUNTI,
            contenuto=[*base, {"type": "text", "text": prompt.istruzioni_appunti(self.imp)}],
            sforzo=self.config.sforzo_appunti,
            max_tokens=96000,
        )
        self._registra(lezione.id, "appunti", uso)
        bozza = pulisci_markdown(testo)
        scrivi_atomico(f.bozza, bozza + "\n")
        self._avanza(lezione.id, "appunti", 1.0)
        return bozza

    def _fase_approfondimento(self, lezione: Lezione, f: File, base: list[dict], appunti: str) -> None:
        voluto = self.imp.sezione("approfondimento") or self.archivio.carica(lezione.id).approfondimento_richiesto
        if not f.approfondimento.is_file() and voluto:
            self._avanza(lezione.id, "approfondimento", 0.05, "Sto scrivendo l'approfondimento (qualche minuto)")
            testo, uso = self.llm.testo(
                system=prompt.SYSTEM_APPUNTI,
                contenuto=[*base, {"type": "text", "text": prompt.istruzioni_approfondimento(appunti)}],
                sforzo=self.config.sforzo_appunti,
                max_tokens=96000,
            )
            self._registra(lezione.id, "approfondimento", uso)
            scrivi_atomico(f.approfondimento, pulisci_markdown(testo) + "\n")
            f.pdf.unlink(missing_ok=True)
        richieste = self.archivio.carica(lezione.id).da_approfondire
        for i, argomento in enumerate(richieste):
            self._avanza(lezione.id, "approfondimento", (i + 0.5) / len(richieste), f"Approfondisco: {argomento}")
            attuale = f.approfondimento.read_text(encoding="utf-8")
            testo, uso = self.llm.testo(
                system=prompt.SYSTEM_APPUNTI,
                contenuto=[*base, {"type": "text", "text": prompt.istruzioni_espansione(argomento, attuale)}],
                sforzo=self.config.sforzo_appunti,
                max_tokens=64000,
            )
            self._registra(lezione.id, "approfondimento", uso)
            scrivi_atomico(f.approfondimento, attuale.rstrip() + "\n\n" + pulisci_markdown(testo) + "\n")
            f.pdf.unlink(missing_ok=True)

            def togli(lez: Lezione, a: str = argomento) -> None:
                if a in lez.da_approfondire:
                    lez.da_approfondire.remove(a)

            self.archivio.modifica(lezione.id, togli)
        self._avanza(lezione.id, "approfondimento", 1.0)

    def _fase_verifica(self, lezione: Lezione, f: File, base: list[dict], bozza: str) -> dict | None:
        if not self.config.verifica:
            return None
        if f.verifica.is_file():
            return leggi_json(f.verifica)
        self._avanza(lezione.id, "verifica", 0.05, "Confronto degli appunti con la trascrizione")
        dati, uso = self.llm.json(
            system=prompt.SYSTEM_APPUNTI,
            contenuto=[*base, {"type": "text", "text": prompt.istruzioni_verifica(bozza, self.imp)}],
            schema=prompt.SCHEMA_VERIFICA,
            sforzo=self.config.sforzo_appunti,
            max_tokens=48000,
        )
        self._registra(lezione.id, "verifica", uso)
        scrivi_json(f.verifica, dati)
        return dati

    def _fase_correzione(
        self, lezione: Lezione, f: File, base: list[dict], bozza: str, verifica: dict | None
    ) -> str:
        if f.appunti.is_file():
            return f.appunti.read_text(encoding="utf-8")
        problemi = (verifica or {}).get("problemi", [])
        appunti = bozza
        if problemi:
            self._avanza(lezione.id, "correzione", 0.05, f"Correzione di {len(problemi)} punti segnalati")
            testo, uso = self.llm.testo(
                system=prompt.SYSTEM_APPUNTI,
                contenuto=[*base, {"type": "text", "text": prompt.istruzioni_correzione(bozza, problemi, self.imp)}],
                sforzo=self.config.sforzo_appunti,
                max_tokens=96000,
            )
            self._registra(lezione.id, "correzione", uso)
            corretti = pulisci_markdown(testo)
            if len(corretti) >= 0.6 * len(bozza):
                appunti = corretti
            else:
                self._avviso(
                    lezione.id,
                    "La versione corretta degli appunti era molto più corta della bozza: "
                    "è stata mantenuta la bozza (vedi la scheda Verifica per i punti segnalati).",
                )
        scrivi_atomico(f.appunti, appunti + "\n")
        self._avanza(lezione.id, "correzione", 1.0)
        return appunti
