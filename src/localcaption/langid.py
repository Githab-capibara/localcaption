"""Language identification with speechbrain's ECAPA-TDNN classifier.

The model (``speechbrain/lang-id-commonlanguage_ecapa``) is tiny and runs
on CPU in well under a second per 6 s window. We classify a handful of
windows, average the posteriors, and report the winner with a confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import models
from .asr import run_runner
from .languages import code_for_name

#: Below this max posterior the language is treated as undetermined and the
#: multilingual model takes over.
LANGID_CONFIDENCE_THRESHOLD = 0.6

#: Detector window in seconds (the model is trained on short utterances).
LANGID_WINDOW_SECONDS = 6.0

#: Upper bound on windows sampled across the file (keeps long videos quick).
LANGID_MAX_WINDOWS = 16


@dataclass(frozen=True)
class LangIdResult:
    code: str
    name: str
    score: float
    scores: dict[str, float]

    @property
    def confident(self) -> bool:
        return self.score >= LANGID_CONFIDENCE_THRESHOLD


def detect_language(wav: str | Path) -> LangIdResult:
    """Classify the dominant language of *wav*."""
    spec = models.get_model(models.MODEL_LANGID)
    payload = run_runner(
        spec,
        Path(wav),
        "auto",
        window=LANGID_WINDOW_SECONDS,
        extra={"max-windows": LANGID_MAX_WINDOWS},
    )
    name = str(payload.get("name") or "Undetermined")
    return LangIdResult(
        code=str(payload.get("code") or code_for_name(name)),
        name=name,
        score=float(payload.get("score") or 0.0),
        scores=dict(payload.get("scores") or {}),
    )
