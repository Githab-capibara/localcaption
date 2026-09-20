"""Transcript serialisation: text, SRT, WebVTT, and JSON.

The ASR runner emits timed segments; these writers turn them into the
artefacts users expect next to a downloaded video.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .chapters import Segment


def _clock(seconds: float, *, vtt: bool = False) -> str:
    ms = int(round(max(seconds, 0.0) * 1000.0))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    sep = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{ms:03d}"


def write_txt(path: Path, text: str) -> Path:
    body = text.rstrip()
    path.write_text(body + ("\n" if body else ""), encoding="utf-8")
    return path


def write_md(path: Path, text: str, segments: Iterable[Segment] | None = None) -> Path:
    """Write a single Markdown file holding the transcript.

    The transcript text is the body. When timed *segments* are supplied and
    differ from the flat text, they are appended as a timestamped section so
    the file stays one document while keeping chaptered timing available.
    """
    body = (text or "").rstrip()
    lines: list[str] = []
    if body:
        lines.append(body)
        lines.append("")
    if segments:
        timed = [s for s in segments if s.text.strip()]
        if timed:
            lines.append("## Timestamps")
            lines.append("")
            for s in timed:
                lines.append(f"- `{_clock(s.start)}` — {s.text.strip()}")
            lines.append("")
    path.write_text("\n".join(lines).rstrip() + ("\n" if lines else ""), encoding="utf-8")
    return path


def write_srt(path: Path, segments: Iterable[Segment]) -> Path:
    lines: list[str] = []
    for idx, seg in enumerate((s for s in segments if s.text.strip()), start=1):
        lines.append(str(idx))
        lines.append(f"{_clock(seg.start)} --> {_clock(seg.end)}")
        lines.append(seg.text.strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_vtt(path: Path, segments: Iterable[Segment]) -> Path:
    lines = ["WEBVTT", ""]
    for seg in (s for s in segments if s.text.strip()):
        lines.append(f"{_clock(seg.start, vtt=True)} --> {_clock(seg.end, vtt=True)}")
        lines.append(seg.text.strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
