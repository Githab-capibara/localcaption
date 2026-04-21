"""Stage 2: re-encode arbitrary audio to 16 kHz mono PCM WAV.

whisper.cpp expects exactly that format, so this stage is a hard requirement
even when the source is already a `.wav` (sample rate / channel count may
not match).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import _logging as log
from .errors import AudioConversionError, DependencyError

WHISPER_SAMPLE_RATE = 16_000
WHISPER_CHANNELS = 1


def to_whisper_wav(src: Path, dst: Path) -> Path:
    """Convert *src* to a 16 kHz mono PCM WAV at *dst* and return *dst*."""
    if shutil.which("ffmpeg") is None:
        raise DependencyError(
            "Required tool 'ffmpeg' was not found on PATH. "
            "On macOS: brew install ffmpeg"
        )

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-ac", str(WHISPER_CHANNELS),
        "-ar", str(WHISPER_SAMPLE_RATE),
        "-vn",                       # drop any video stream
        "-c:a", "pcm_s16le",         # signed 16-bit little-endian PCM
        str(dst),
    ]
    log.info(f"ffmpeg: re-encoding to {WHISPER_SAMPLE_RATE} Hz mono WAV")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise AudioConversionError(
            f"ffmpeg failed (exit {exc.returncode}) while converting {src}"
        ) from exc

    if not dst.is_file():
        raise AudioConversionError(f"ffmpeg ran but {dst} was not created")
    return dst
