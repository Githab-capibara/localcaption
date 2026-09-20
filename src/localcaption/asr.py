"""Stage 3: route a 16 kHz mono WAV to the right local ASR model.

Language routing (decided by the language-ID stage, or the ``--language``
flag):

* ``ru`` → Qwen3-ASR 0.6B
* ``en`` → NVIDIA Parakeet TDT 0.6B v3
* anything else (or unclear) → NVIDIA Nemotron 3.5 ASR Streaming 0.6B

Each model runs in its own isolated virtualenv; we drive it as a
subprocess and collect a JSON manifest of timed segments.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _logging as log
from . import models, paths
from .chapters import Segment
from .errors import DependencyError, TranscriptionError
from .formats import write_json, write_md, write_srt, write_txt, write_vtt
from .languages import name_for_code
from .network import runner_env

SUPPORTED_OUTPUT_FORMATS = ("md", "txt", "srt", "vtt", "json", "all")

#: Default output formats for a transcription run.
DEFAULT_OUTPUT_FORMATS = "md"

#: Window length fed to a model at a time. Bounds CPU memory and yields
#: usable subtitle timing without a separate forced-aligner model.
WINDOW_SECONDS = 45.0

#: language code -> model key
ROUTING: dict[str, str] = {
    "ru": models.MODEL_QWEN,
    "en": models.MODEL_PARAKEET,
}
MULTILINGUAL_MODEL = models.MODEL_NEMOTRON

_RUNNER_BY_ENV = {
    "langid": "langid",
    "qwen": "qwen",
    "nvidia": "nvidia",
}


@dataclass(frozen=True)
class TranscriptionResult:
    """Paths to the artefacts emitted by a transcription run."""

    txt: Path
    srt: Path
    vtt: Path
    json: Path
    md: Path
    language: str = "und"
    model: str = ""

    def existing(self) -> dict[str, Path]:
        return {k: v for k, v in vars(self).items() if isinstance(v, Path) and v.exists()}


def output_file(out_basename: Path, suffix: str) -> Path:
    """Append *suffix* without pathlib stripping extra dots in the stem.

    ``Path.with_suffix('.txt')`` turns ``lecture.2024`` into ``lecture.txt``.
    """
    if not suffix.startswith("."):
        suffix = "." + suffix
    return out_basename.parent / f"{out_basename.name}{suffix}"


def model_for_language(language: str) -> str:
    """Pick an ASR model key for an ISO code; unknown → multilingual."""
    return ROUTING.get(language.strip().lower(), MULTILINGUAL_MODEL)


def runner_env_and_python(spec: models.ModelSpec) -> tuple[Path, str]:
    python = paths.venv_python(spec.env)
    if not python.exists():
        raise DependencyError(
            f"The '{spec.env}' runtime is missing (expected {python}).\n"
            "Run:  bash scripts/setup_runtime.sh"
        )
    return python, _RUNNER_BY_ENV.get(spec.env, spec.env)


def _stream(cmd: list[str], env: dict[str, str], prefix: str) -> int:
    """Run *cmd*, forwarding its merged output to our log. Returns the exit code."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
    except FileNotFoundError as exc:
        raise DependencyError(f"Interpreter not found: {cmd[0]}") from exc

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log.info(f"  [{prefix}] {line}")
    return proc.wait()


def run_runner(
    spec: models.ModelSpec,
    wav: Path,
    language: str,
    *,
    window: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the model's runner and return the parsed JSON result."""
    python, runner_name = runner_env_and_python(spec)
    script = paths.runner_script(runner_name)
    if not script.exists():
        raise DependencyError(f"Runner script missing: {script}")

    models.require([spec.key])
    with tempfile.TemporaryDirectory(prefix="localcaption-run-") as tmp:
        out_path = Path(tmp) / "result.json"
        cmd = [
            str(python), str(script),
            "--model", str(spec.local_dir),
            "--model-key", spec.key,
            "--wav", str(wav),
            "--out", str(out_path),
            "--language", language or "auto",
            "--window", str(window if window is not None else WINDOW_SECONDS),
        ]
        for key, value in (extra or {}).items():
            cmd += [f"--{key}", str(value)]

        log.info(f"model: {spec.key} ({spec.role}) via '{spec.env}' env")
        rc = _stream(cmd, runner_env(), spec.env)
        if rc != 0:
            raise TranscriptionError(
                f"Model {spec.key} failed (exit {rc}) on {wav.name}"
            )
        if not out_path.is_file():
            raise TranscriptionError(f"Model {spec.key} produced no result manifest")
        return json.loads(out_path.read_text(encoding="utf-8"))


def transcribe(
    wav: Path,
    out_basename: Path,
    *,
    language: str = "auto",
    model: str | None = None,
    detected_language: str | None = None,
    output_format: str = "md",
) -> TranscriptionResult:
    """Transcribe *wav*, writing output artefacts.

    *output_format* selects what is written: ``md`` (single Markdown file —
    the default), ``txt`` (plain text only), ``srt``, ``vtt``, ``json``, or
    ``all``/``full`` for every supported format. Defaults to ``md`` so a run
    produces exactly one file.

    *model* forces a specific registry key. Otherwise the model is chosen
    from *detected_language* (or *language* when it is a concrete code).
    """
    code = (detected_language or language or "auto").lower()
    if model is None:
        model = model_for_language(code)
    spec = models.get_model(model)

    lang_hint = code if code not in {"auto", ""} else "auto"
    payload = run_runner(spec, Path(wav), lang_hint)

    raw_segments = payload.get("segments") or []
    segments = [
        Segment(
            start=float(seg.get("start", 0.0)),
            end=float(seg.get("end", seg.get("start", 0.0))),
            text=str(seg.get("text", "")).strip(),
        )
        for seg in raw_segments
        if str(seg.get("text", "")).strip()
    ]
    text = str(payload.get("text", "")).strip()
    detected = str(payload.get("language") or detected_language or code)

    artefacts = _write_output_artefacts(
        out_basename, segments, text, spec.key, detected, output_format
    )
    md_path = _dict_val(artefacts, "md")
    return TranscriptionResult(
        txt=md_path if md_path is not None else _dict_val(artefacts, "txt"),
        srt=_dict_val(artefacts, "srt"),
        vtt=_dict_val(artefacts, "vtt"),
        json=_dict_val(artefacts, "json"),
        md=md_path,
        language=detected,
        model=spec.key,
    )


def _dict_val(mapping: dict[str, Path | None], kind: str) -> Path | None:
    """Safe lookup: return the Path for *kind*, else None."""
    return mapping.get(kind)


def _output_label(fmt: str) -> set[str]:
    """Resolve the requested output formats.

    Accepts: ``md``, ``txt``, ``srt``, ``vtt``, ``json``,
    ``all``/``full``/``complete``. Defaults to ``{"md"}`` (a single file).
    """
    fmt = (fmt or "").strip().lower()
    if fmt in {"all", "full", "complete"}:
        return set(SUPPORTED_OUTPUT_FORMATS)
    allowed = {"md", "txt", "srt", "vtt", "json"}
    if fmt in allowed:
        return {fmt}
    return {"md"}


def _write_output_artefacts(
    out_basename: Path,
    segments: list[Segment],
    text: str,
    model: str,
    detected: str,
    output_format: str,
) -> dict[str, Path | None]:
    """Write the requested output artefacts for *out_basename*.

    Returns a dict mapping kind -> path, or None for any kind not selected.
    With the default ``md`` format only a single ``.md`` file is produced.
    """
    out_basename = Path(out_basename)
    out_basename.parent.mkdir(parents=True, exist_ok=True)

    fmt = _output_label(output_format)
    res: dict[str, Path | None] = {}

    def add(kind: str) -> None:
        if kind in fmt:
            res[kind] = _write_one(out_basename, kind, segments, text, model, detected)

    add("md")
    add("txt")
    add("srt")
    add("vtt")
    add("json")
    return res


def _write_one(
    out_basename: Path,
    kind: str,
    segments: list[Segment],
    text: str,
    model: str,
    detected: str,
) -> Path:
    """Write a single artefact kind for *out_basename*."""
    if kind == "md":
        return write_md(output_file(out_basename, ".md"), text, segments)
    if kind == "txt":
        return write_txt(output_file(out_basename, ".txt"), text)
    if kind == "srt":
        return write_srt(output_file(out_basename, ".srt"), segments)
    if kind == "vtt":
        return write_vtt(output_file(out_basename, ".vtt"), segments)
    return write_json(
        output_file(out_basename, ".json"),
        {
            "model": model,
            "role": "",
            "language": detected,
            "language_name": name_for_code(detected),
            "text": text,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text} for s in segments
            ],
        },
    )
