"""Shared helpers for the standalone runner scripts.

These scripts execute *inside* a model's virtualenv, so they must not import
``localcaption``. Only the standard library plus the env's ML stack.
"""

from __future__ import annotations

import wave
from collections.abc import Iterator
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000


def read_wav16k(path: str | Path) -> np.ndarray:
    """Load a 16 kHz mono PCM WAV as float32 in [-1, 1]."""
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        width = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())
    if width != 2:
        raise ValueError(f"expected 16-bit PCM, got {width * 8}-bit")
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    if rate != SAMPLE_RATE:
        raise ValueError(f"expected {SAMPLE_RATE} Hz, got {rate}")
    return data


def iter_windows(
    samples: np.ndarray,
    window_s: float,
    *,
    max_windows: int | None = None,
) -> Iterator[tuple[float, float, np.ndarray]]:
    """Yield ``(start_s, end_s, chunk)`` covering *samples*.

    When *max_windows* is set and the file would need more, windows are
    sampled evenly across the whole recording instead of truncated.
    """
    step = max(1, int(round(window_s * SAMPLE_RATE)))
    total = len(samples)
    if total == 0:
        yield 0.0, 0.0, np.zeros(step, dtype=np.float32)
        return

    starts = list(range(0, max(total - step + 1, 1), step))
    if total > step and starts[-1] + step < total:
        starts.append(total - step)
    if max_windows is not None and len(starts) > max_windows:
        factor = len(starts) / max_windows
        idxs = sorted({min(len(starts) - 1, int(i * factor)) for i in range(max_windows)})
        starts = [starts[i] for i in idxs]

    for start in starts:
        chunk = samples[start:start + step]
        if len(chunk) < step:
            chunk = np.pad(chunk, (0, step - len(chunk)))
        yield start / SAMPLE_RATE, (start + len(chunk)) / SAMPLE_RATE, chunk
