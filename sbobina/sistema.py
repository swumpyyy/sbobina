"""Il Mac dello studente: chip, memoria e spazio libero, e quale modello AI ci gira bene."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Modelli che scrivono gli appunti (Ollama, famiglia Gemma 4: buon italiano, licenza aperta).
# "ram" è la memoria minima per usarli senza rallentare tutto il Mac; "gb" lo spazio su disco.
MODELLI = (
    {
        "tag": "gemma4:e2b",
        "nome": "Leggero",
        "gb": 4.6,
        "ram": 8,
        "qualita": 2,
        "velocita": 5,
        "descrizione": "Per Mac con 8 GB. Appunti corretti ma più essenziali; meglio con lezioni fino a un'ora.",
    },
    {
        "tag": "gemma4:e4b",
        "nome": "Equilibrato",
        "gb": 6.6,
        "ram": 16,
        "qualita": 3,
        "velocita": 4,
        "descrizione": "Per Mac con 16 GB. Buona qualità senza appesantire il computer.",
    },
    {
        "tag": "gemma4:12b",
        "nome": "Accurato",
        "gb": 7.7,
        "ram": 24,
        "qualita": 4,
        "velocita": 3,
        "descrizione": "Appunti completi e precisi. Il punto di partenza ideale da 24 GB in su.",
    },
    {
        "tag": "gemma4:26b",
        "nome": "Massima qualità",
        "gb": 16.0,
        "ram": 32,
        "qualita": 5,
        "velocita": 4,
        "descrizione": "Il più accurato tra i modelli veloci: lavora come un modello piccolo ma ragiona come uno grande.",
    },
    {
        "tag": "gemma4:31b",
        "nome": "Studio",
        "gb": 19.0,
        "ram": 64,
        "qualita": 5,
        "velocita": 2,
        "descrizione": "Per workstation con 64 GB o più: il più lento, per chi vuole il massimo dettaglio.",
    },
)

# Riconoscimento vocale (Whisper su GPU Apple con MLX).
WHISPER = (
    {
        "id": "large-v3-turbo",
        "nome": "Turbo",
        "gb": 1.6,
        "ram": 8,
        "descrizione": "Quasi preciso come il modello grande, molte volte più veloce. Consigliato.",
    },
    {
        "id": "large-v3",
        "nome": "Grande",
        "gb": 3.1,
        "ram": 16,
        "descrizione": "Il più accurato su audio difficili (aula rumorosa, docente lontano). Più lento.",
    },
    {
        "id": "small",
        "nome": "Piccolo",
        "gb": 0.5,
        "ram": 8,
        "descrizione": "Per dischi quasi pieni. Sbaglia più spesso i termini tecnici.",
    },
)


def _sysctl(chiave: str) -> str:
    try:
        return subprocess.run(["sysctl", "-n", chiave], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def info_mac() -> dict:
    """Caratteristiche del computer, per consigliare i modelli."""
    ram = 0
    try:
        ram = round(int(_sysctl("hw.memsize") or 0) / 2**30)
    except ValueError:
        pass
    if not ram and hasattr(os, "sysconf"):
        try:
            ram = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30)
        except (ValueError, OSError):
            ram = 0
    chip = _sysctl("machdep.cpu.brand_string") or platform.processor() or "Sconosciuto"
    libero = shutil.disk_usage(Path.home()).free / 1e9
    return {
        "chip": chip,
        "apple_silicon": sys.platform == "darwin" and platform.machine() == "arm64",
        "ram_gb": ram,
        "disco_libero_gb": round(libero, 1),
        "macos": platform.mac_ver()[0] if sys.platform == "darwin" else platform.platform(),
        "core": os.cpu_count() or 0,
    }


def modello_consigliato(ram_gb: int) -> str:
    if ram_gb >= 48:
        return "gemma4:26b"
    if ram_gb >= 24:
        return "gemma4:12b"
    if ram_gb >= 16:
        return "gemma4:e4b"
    return "gemma4:e2b"


def contesto_massimo(ram_gb: int) -> int:
    """Quanta lezione (in token) il modello può leggere insieme senza esaurire la memoria del Mac."""
    if ram_gb and ram_gb < 12:
        return 16384
    if ram_gb and ram_gb < 20:
        return 32768
    return 65536


def proposte(installati: set[str] | None = None) -> dict:
    """Informazioni sul Mac + elenco dei modelli con quello consigliato e quelli adatti."""
    info = info_mac()
    installati = installati or set()
    consigliato = modello_consigliato(info["ram_gb"])
    modelli = [
        {
            **m,
            "consigliato": m["tag"] == consigliato,
            "adatto": not info["ram_gb"] or info["ram_gb"] >= m["ram"],
            "installato": m["tag"] in installati,
            "spazio_ok": m["tag"] in installati or info["disco_libero_gb"] >= m["gb"] + 2,
        }
        for m in MODELLI
    ]
    whisper = [
        {**w, "consigliato": w["id"] == "large-v3-turbo", "adatto": not info["ram_gb"] or info["ram_gb"] >= w["ram"]}
        for w in WHISPER
    ]
    return {"mac": info, "modelli": modelli, "whisper": whisper, "consigliato": consigliato}
