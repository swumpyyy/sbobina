"""Trascrizione locale con Whisper: gratuita e offline (mlx-whisper su Mac, faster-whisper con CUDA su Windows)."""

from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

from sbobina.sistema import CARTELLA_APP
from sbobina.trascrizione.base import Avanzamento, ErroreTrascrizione, Parola, Trascrizione

log = logging.getLogger(__name__)
_modelli: dict[tuple[str, str], object] = {}
_blocco = threading.Lock()


def prompt_iniziale(contesto: str, termini: list[str], limite: int = 600) -> str:
    """Testo di innesco nello stile della lezione: aiuta Whisper con grafia e punteggiatura."""
    prompt = contesto.strip()
    if termini:
        prompt += (" " if prompt else "") + "Termini: " + ", ".join(termini) + "."
    return prompt[:limite].rsplit(" ", 1)[0] if len(prompt) > limite else prompt


def parole_suggerite(termini: list[str], limite: int = 300) -> str:
    """Termini ripetuti in ogni finestra di 30 s (a differenza del prompt iniziale)."""
    testo = ""
    for termine in termini:
        candidato = f"{testo}, {termine}" if testo else termine
        if len(candidato) > limite:
            break
        testo = candidato
    return testo


def campioni_16k(audio: Path):
    """Decodifica con ffmpeg in campioni float32 mono a 16 kHz, il formato che Whisper si aspetta.

    Evita il decoder interno di faster-whisper (PyAV), che si rompe con alcune versioni di `av`.
    """
    import numpy as np

    risultato = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(audio), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True,
    )
    if risultato.returncode != 0:
        dettaglio = risultato.stderr.decode(errors="replace").strip()[-300:]
        raise ErroreTrascrizione(f"Audio non leggibile per Whisper: {dettaglio}")
    return np.frombuffer(risultato.stdout, dtype=np.float32)


class MotoreWhisper:
    nome = "whisper"

    def __init__(self, modello: str = "large-v3-turbo", dispositivo: str = "auto"):
        self.modello = modello
        self.dispositivo = dispositivo

    def _carica(self, dispositivo: str):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise ErroreTrascrizione(
                "Per la trascrizione locale installa faster-whisper: pip install -e '.[locale]'"
            ) from e
        _dll_cuda()
        percorso = assicura_fw(self.modello)
        chiave = (self.modello, dispositivo)
        with _blocco:
            if chiave not in _modelli:
                _modelli[chiave] = WhisperModel(percorso, device=dispositivo, compute_type="auto")
            return _modelli[chiave]

    def trascrivi(
        self, audio: Path, *, lingua: str, termini: list[str], contesto: str, avanzamento: Avanzamento
    ) -> Trascrizione:
        if mlx_disponibile():
            return self._trascrivi_mlx(audio, lingua=lingua, termini=termini, contesto=contesto, avanzamento=avanzamento)
        try:
            return self._trascrivi_fw(self.dispositivo, audio, lingua, termini, contesto, avanzamento)
        except RuntimeError as e:
            if self.dispositivo == "cpu":
                raise
            # CUDA assente o incompleta (DLL cuBLAS/cuDNN, scheda troppo nuova): più lento ma funziona.
            log.warning("Whisper su GPU non riuscito (%s): passo al processore", e)
            return self._trascrivi_fw("cpu", audio, lingua, termini, contesto, avanzamento)

    def _trascrivi_fw(
        self, dispositivo: str, audio: Path, lingua: str, termini: list[str], contesto: str, avanzamento: Avanzamento
    ) -> Trascrizione:
        from sbobina.llm import ferma_llama, in_diretta, inizia_diretta

        ferma_llama()  # 8 GB di VRAM non bastano per Whisper e il modello degli appunti insieme
        modello = self._carica(dispositivo)
        inizia_diretta(motore=f"faster-whisper ({dispositivo})", modello=self.modello)
        segmenti, info = modello.transcribe(
            campioni_16k(audio),
            language=lingua,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 700},
            word_timestamps=True,
            # Evita i "loop" di frasi ripetute tipici di Whisper su audio lunghi.
            condition_on_previous_text=False,
            initial_prompt=prompt_iniziale(contesto, termini) or None,
            hotwords=parole_suggerite(termini) or None,
        )
        parole: list[Parola] = []
        for segmento in segmenti:
            in_diretta(segmento.text.strip() + "\n")
            for w in segmento.words or []:
                testo = w.word.strip()
                if testo:
                    parole.append(Parola(float(w.start), float(w.end), testo, float(w.probability)))
            if info.duration:
                avanzamento(min(1.0, segmento.end / info.duration))
        avanzamento(1.0)
        _modelli.clear()  # libera la scheda video per il modello degli appunti (ricaricarlo costa pochi secondi)
        return Trascrizione(self.nome, parole, float(info.duration))

    def _trascrivi_mlx(
        self, audio: Path, *, lingua: str, termini: list[str], contesto: str, avanzamento: Avanzamento
    ) -> Trascrizione:
        """Whisper su GPU Apple (Metal): molto più veloce di faster-whisper, che su Mac gira solo su CPU."""
        import importlib

        import mlx_whisper

        # mlx_whisper.transcribe è anche il nome della funzione: serve il modulo.
        modulo = importlib.import_module("mlx_whisper.transcribe")

        campioni = campioni_16k(audio)
        durata = len(campioni) / 16000

        class _Barra:  # mlx-whisper riporta l'avanzamento solo via tqdm: lo intercettiamo
            def __init__(self, total=0, **_):
                self.totale, self.fatto = total or 1, 0

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def update(self, n):
                self.fatto += n
                avanzamento(min(1.0, self.fatto / self.totale))

        from sbobina.llm import in_diretta, inizia_diretta

        percorso = modello_pronto(self.modello)
        if percorso == repo_hf(self.modello):  # nessun modello sul disco: download con barra e tentativi
            from sbobina.llm import PREPARAZIONE, _SCARICO, scarica_hf

            with _SCARICO:
                PREPARAZIONE.update(attiva=True, errore="")
                try:
                    scarica_hf(percorso, MODELLI_LOCALI / percorso.split("/")[1], "il riconoscimento vocale", fermabile=True)
                finally:
                    PREPARAZIONE["attiva"] = False
            percorso = modello_pronto(self.modello)

        inizia_diretta(motore="mlx-whisper", modello=self.modello)
        originale = modulo.tqdm
        modulo.tqdm = type("tqdm", (), {"tqdm": _Barra})
        # Con verbose=True mlx-whisper stampa ogni frase riconosciuta: la mandiamo alla vista in diretta.
        modulo.print = lambda *parti, **_: in_diretta(" ".join(map(str, parti)) + "\n")
        try:
            risultato = mlx_whisper.transcribe(
                campioni,
                path_or_hf_repo=percorso,
                language=lingua,
                word_timestamps=True,
                condition_on_previous_text=False,
                # Nei silenzi (inizio lezione, pause) Whisper inventa frasi tipo "Grazie a tutti": salta quei tratti.
                hallucination_silence_threshold=2.0,
                initial_prompt=prompt_iniziale(contesto, termini) or None,
                verbose=True,
            )
        finally:
            modulo.tqdm = originale
            del modulo.print
        parole = [
            Parola(float(w["start"]), float(w["end"]), w["word"].strip(), float(w.get("probability", 0) or 0))
            for s in risultato["segments"]
            for w in s.get("words", [])
            if w["word"].strip()
        ]
        avanzamento(1.0)
        return Trascrizione(self.nome, parole, durata)


# large-v3-turbo: qualità quasi uguale a large-v3, circa 6 volte più veloce (il predefinito).
REPO_MLX = {"large-v3-turbo": "mlx-community/whisper-large-v3-turbo"}


def repo_hf(modello: str) -> str:
    return REPO_MLX.get(modello, f"mlx-community/whisper-{modello}-mlx")
MODELLI_LOCALI = CARTELLA_APP / "modelli"


def assicura_fw(modello: str) -> str:
    """La cartella del modello faster-whisper sul disco: lo scarica (con barra e tentativi) se manca."""
    from faster_whisper.utils import _MODELS

    from sbobina.llm import _SCARICO, PREPARAZIONE, scarica_hf

    repo = _MODELS.get(modello, modello)
    cartella = MODELLI_LOCALI / ("fw-" + repo.split("/")[-1])
    with _SCARICO:
        if not (cartella / ".completo").is_file():
            gia_attiva = PREPARAZIONE["attiva"]
            PREPARAZIONE.update(attiva=True, errore="")
            try:
                scarica_hf(repo, cartella, "il riconoscimento vocale", fermabile=True)
            finally:
                if not gia_attiva:
                    PREPARAZIONE["attiva"] = False
    return str(cartella)


def _dll_cuda() -> None:
    """Su Windows le DLL di CUDA (pacchetti pip nvidia-cublas-cu12 e nvidia-cudnn-cu12) vanno rese visibili."""
    import os
    import sys

    if sys.platform != "win32":
        return
    import importlib.util

    for pacchetto in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(pacchetto)
        except ModuleNotFoundError:
            continue
        for radice in (spec.submodule_search_locations or []) if spec else []:
            cartella = Path(radice) / "bin"
            if cartella.is_dir():
                os.add_dll_directory(str(cartella))
                os.environ["PATH"] = f"{cartella}{os.pathsep}{os.environ.get('PATH', '')}"


def repo_mlx(modello: str) -> str:
    """Cartella del modello già scaricato (verificato) se c'è, altrimenti il repo Hugging Face."""
    repo = repo_hf(modello)
    cartella = MODELLI_LOCALI / repo.split("/")[1]
    pesi = (cartella / "weights.safetensors").exists() or (cartella / "weights.npz").exists()
    return str(cartella) if pesi and (cartella / "config.json").exists() else repo


def modello_pronto(modello: str) -> str:
    """Il modello scelto se è già sul disco, altrimenti un altro già scaricato.

    Scaricare GB a metà trascrizione si blocca senza avanzamento né modo di fermarlo:
    il download vero lo fa la preparazione in Impostazioni, con barra e tentativi.
    """
    for candidato in (modello, "large-v3-turbo", "large-v3", "small"):
        percorso = repo_mlx(candidato)
        if percorso != repo_hf(candidato):
            return percorso
    return repo_hf(modello)  # nessun modello locale: unica strada è scaricarlo


def mlx_disponibile() -> bool:
    import importlib.util
    import platform

    return platform.machine() == "arm64" and importlib.util.find_spec("mlx_whisper") is not None
