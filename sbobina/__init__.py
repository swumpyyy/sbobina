"""Sbobina: dalle registrazioni delle lezioni ad appunti e schemi accurati."""

import os

# Il protocollo Xet di Hugging Face si blocca a pochi KB su questo Mac: scarica i modelli Whisper via HTTP.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

__version__ = "1.4.0"
