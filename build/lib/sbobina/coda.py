"""Coda di elaborazione: una lezione alla volta, in un thread in background."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

from sbobina.archivio import Archivio
from sbobina.pipeline import Elaborazione

log = logging.getLogger(__name__)

ATTIVI = ("in_coda", "in_elaborazione")


class Coda:
    def __init__(self, archivio: Archivio, crea_elaborazione: Callable[[], Elaborazione]):
        self.archivio = archivio
        self.crea_elaborazione = crea_elaborazione
        self._coda: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None

    def avvia(self) -> None:
        if self._thread:
            return
        # Riprende le lezioni lasciate a metà (es. computer spento durante l'elaborazione).
        for lezione in sorted(self.archivio.elenco(), key=lambda lez: lez.creata):
            if lezione.stato in ATTIVI:
                self._coda.put(lezione.id)
        self._thread = threading.Thread(target=self._ciclo, name="sbobina-coda", daemon=True)
        self._thread.start()

    def accoda(self, id_lezione: str) -> None:
        self._coda.put(id_lezione)

    def _ciclo(self) -> None:
        while True:
            id_lezione = self._coda.get()
            try:
                lezione = self.archivio.carica(id_lezione)
            except KeyError:
                continue  # eliminata mentre era in coda
            if lezione.stato not in ATTIVI:
                continue
            try:
                self.crea_elaborazione().esegui(id_lezione)
            except Exception as e:  # noqa: BLE001 - il thread della coda non deve morire
                log.exception("Errore nell'elaborazione di %s", id_lezione)
                try:
                    self.archivio.aggiorna(id_lezione, stato="errore", errore=str(e) or type(e).__name__)
                except KeyError:
                    pass
