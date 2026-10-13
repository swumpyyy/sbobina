"""Il computer dello studente (Mac o PC Windows): chip, memoria e spazio libero, e quale modello AI ci gira bene."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"
# Modelli e impostazioni dell'app: Application Support su Mac, %LOCALAPPDATA% su Windows.
CARTELLA_APP = (
    Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "Sbobina"
    if WINDOWS
    else Path.home() / "Library/Application Support/Sbobina"
)

# Modelli che scrivono gli appunti (famiglia Gemma 4: ottimo italiano, licenza aperta): MLX per la GPU del Mac,
# GGUF (repo/file) per llama.cpp sulla GPU del PC Windows.
# "tag" è il nome breve salvato nelle impostazioni (lo stesso delle versioni con Ollama, per non perdere le scelte).
# "ram" è la memoria minima per usarli senza rallentare tutto il Mac; "gb" lo spazio su disco.
MODELLI = (
    {
        "tag": "gemma4:e2b",
        "mlx": "mlx-community/gemma-4-e2b-it-4bit",
        "gguf": "unsloth/gemma-4-E2B-it-GGUF/gemma-4-E2B-it-Q4_K_M.gguf",  # Windows: llama.cpp
        "nome": "Leggero",
        "gb": 3.6,
        "ram": 8,
        "qualita": 2,
        "velocita": 5,
        "descrizione": "Per Mac con 8 GB. Appunti corretti ma più essenziali; meglio con lezioni fino a un'ora.",
    },
    {
        "tag": "gemma4:e4b",
        "mlx": "mlx-community/gemma-4-e4b-it-4bit",
        "gguf": "unsloth/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf",  # Windows: llama.cpp
        "nome": "Equilibrato",
        "gb": 5.2,
        "ram": 16,
        "qualita": 3,
        "velocita": 4,
        "descrizione": "Per Mac con 16 GB. Buona qualità senza appesantire il computer.",
    },
    {
        "tag": "gemma4:12b",
        "mlx": "mlx-community/gemma-4-12B-it-4bit",
        "gguf": "unsloth/gemma-4-12b-it-GGUF/gemma-4-12b-it-Q4_K_M.gguf",  # Windows: llama.cpp
        "nome": "Accurato",
        "gb": 6.8,
        "ram": 24,
        "qualita": 4,
        "velocita": 3,
        "descrizione": "Appunti completi e precisi. Il punto di partenza ideale da 24 GB in su.",
    },
    {
        "tag": "gemma4:26b",
        "mlx": "mlx-community/gemma-4-26b-a4b-it-4bit",
        "gguf": "unsloth/gemma-4-26B-A4B-it-GGUF/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",  # Windows: llama.cpp
        "nome": "Massima qualità",
        "gb": 15.4,
        "ram": 32,
        "qualita": 5,
        "velocita": 4,
        "descrizione": "Il migliore da 32 GB in su: 26 miliardi di parametri ma ne usa 4 alla volta, quindi è più veloce dell'Accurato.",
    },
    {
        "tag": "gemma4:31b",
        "mlx": "mlx-community/gemma-4-31b-it-4bit",
        "gguf": "unsloth/gemma-4-31B-it-GGUF/gemma-4-31B-it-Q4_K_M.gguf",  # Windows: llama.cpp
        "nome": "Studio",
        "gb": 18.4,
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


def _windows() -> tuple[int, str]:
    """RAM (GB) e nome del processore su Windows, dove non ci sono sysctl né sysconf."""
    import ctypes
    import winreg

    class Stato(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    stato = Stato(dwLength=ctypes.sizeof(Stato))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stato))
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as chiave:
            chip = str(winreg.QueryValueEx(chiave, "ProcessorNameString")[0]).strip()
    except OSError:
        chip = ""
    return round(stato.ullTotalPhys / 2**30), chip


def scheda_nvidia() -> tuple[str, int]:
    """Nome e memoria (GB) della scheda video NVIDIA, se c'è: su Windows è lei a far girare l'AI."""
    try:
        uscita = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip().splitlines()
        nome, mib = uscita[0].rsplit(",", 1)
        return nome.strip(), round(int(mib) / 1024)
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return "", 0


def info_mac() -> dict:
    """Caratteristiche del computer, per consigliare i modelli."""
    ram, chip = 0, ""
    if WINDOWS:
        ram, chip = _windows()
    else:
        try:
            ram = round(int(_sysctl("hw.memsize") or 0) / 2**30)
        except ValueError:
            pass
    if not ram and hasattr(os, "sysconf"):
        try:
            ram = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30)
        except (ValueError, OSError):
            ram = 0
    chip = chip or _sysctl("machdep.cpu.brand_string") or platform.processor() or "Sconosciuto"
    libero = shutil.disk_usage(Path.home()).free / 1e9
    gpu, vram = scheda_nvidia() if WINDOWS else ("", 0)
    apple = sys.platform == "darwin" and platform.machine() == "arm64"
    return {
        "chip": chip + (f" · {gpu} {vram} GB" if gpu else ""),
        "apple_silicon": apple,
        "windows": WINDOWS,
        "ai_locale": apple or WINDOWS,  # MLX sui chip Apple, llama.cpp su Windows
        "ram_gb": ram,
        # Su Windows il modello sta nella memoria della scheda video (con un po' di RAM come appoggio):
        # 8 GB di VRAM reggono quanto un Mac da 16 GB. shortcut: stima a occhio, da tarare con prove reali.
        "memoria_ai_gb": vram * 2 if vram else ram,
        "disco_libero_gb": round(libero, 1),
        "macos": platform.mac_ver()[0] if sys.platform == "darwin" else platform.platform(),
        "core": os.cpu_count() or 0,
    }


def modello_consigliato(ram_gb: int) -> str:
    if ram_gb >= 32:  # 26B-A4B (MoE): più preciso del 12B e, con 4B attivi, anche più veloce
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
    memoria = info["memoria_ai_gb"]
    consigliato = modello_consigliato(memoria)
    modelli = [
        {
            **m,
            "consigliato": m["tag"] == consigliato,
            "adatto": not memoria or memoria >= m["ram"],
            "installato": m["tag"] in installati,
            "spazio_ok": m["tag"] in installati or info["disco_libero_gb"] >= m["gb"] + 2,
        }
        for m in MODELLI
    ]
    whisper = [
        {**w, "consigliato": w["id"] == "large-v3-turbo", "adatto": not memoria or memoria >= w["ram"]}
        for w in WHISPER
    ]
    return {"mac": info, "modelli": modelli, "whisper": whisper, "consigliato": consigliato}
