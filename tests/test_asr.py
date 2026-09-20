"""Tests for ``localcaption.asr`` (routing + artefact naming)."""

from __future__ import annotations

from pathlib import Path

import pytest

from localcaption import asr, models
from localcaption.errors import DependencyError


def test_output_file_keeps_extra_dots(tmp_path: Path) -> None:
    base = tmp_path / "lecture.2024"
    assert asr.output_file(base, "txt") == tmp_path / "lecture.2024.txt"
    assert asr.output_file(base, ".json") == tmp_path / "lecture.2024.json"


def test_model_for_language_routing() -> None:
    assert asr.model_for_language("ru") == "qwen3-asr-0.6b"
    assert asr.model_for_language("RU") == "qwen3-asr-0.6b"
    assert asr.model_for_language("en") == "parakeet-tdt-0.6b-v3"
    assert asr.model_for_language("de") == asr.MULTILINGUAL_MODEL
    assert asr.model_for_language("und") == asr.MULTILINGUAL_MODEL


def test_runner_env_and_python_requires_venv() -> None:
    spec = models.get_model("qwen3-asr-0.6b")
    # conftest isolates LOCALCAPTION_RUNTIME_DIR to an empty tmp dir.
    with pytest.raises(DependencyError, match="qwen"):
        asr.runner_env_and_python(spec)


def test_transcription_result_existing(tmp_path: Path) -> None:
    txt = tmp_path / "a.txt"
    txt.write_text("hi")
    missing = tmp_path / "a.srt"
    md = tmp_path / "a.md"
    md.write_text("# hi")
    result = asr.TranscriptionResult(
        txt=txt, srt=missing, vtt=missing, json=missing, md=md
    )
    assert result.existing() == {"txt": txt, "md": md}
