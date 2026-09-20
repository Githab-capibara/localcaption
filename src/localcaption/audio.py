"""Stage 2: re-encode arbitrary audio to 16 kHz mono PCM WAV.

All our ASR models expect 16 kHz mono input, so this stage is a hard
requirement even when the source is already a ``.wav`` (sample rate or
channel count may not match).

``ffmpeg`` is intentionally *not* routed through the proxy: it only touches
local files.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import _logging as log
from .errors import AudioConversionError, DependencyError

TARGET_SAMPLE_RATE = 16_000
TARGET_CHANNELS = 1


def to_wav(src: Path, dst: Path) -> Path:
    """Convert *src* to a 16 kHz mono PCM WAV at *dst* and return *dst*."""
    if shutil.which("ffmpeg") is None:
        raise DependencyError(
            "Required tool 'ffmpeg' was not found on PATH. "
            "On macOS: brew install ffmpeg"
        )

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-ac", str(TARGET_CHANNELS),
        "-ar", str(TARGET_SAMPLE_RATE),
        "-vn",                       # drop any video stream
        "-c:a", "pcm_s16le",         # signed 16-bit little-endian PCM
        str(dst),
    ]
    log.info(f"ffmpeg: re-encoding to {TARGET_SAMPLE_RATE} Hz mono WAV")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise AudioConversionError(
            f"ffmpeg failed (exit {exc.returncode}) while converting {src}"
        ) from exc

    if not dst.is_file():
        raise AudioConversionError(f"ffmpeg ran but {dst} was not created")
    return dst
