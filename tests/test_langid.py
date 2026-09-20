"""Tests for the language-ID result wrapper."""

from __future__ import annotations

from pathlib import Path

from localcaption import langid
from localcaption.langid import LANGID_CONFIDENCE_THRESHOLD, LangIdResult


def test_confident_above_threshold() -> None:
    result = LangIdResult("ru", "Russian", 0.9, {"Russian": 0.9})
    assert result.confident


def test_not_confident_below_threshold() -> None:
    result = LangIdResult("de", "German", LANGID_CONFIDENCE_THRESHOLD - 0.01, {"German": 0.5})
    assert not result.confident


def test_threshold_is_inclusive() -> None:
    result = LangIdResult("en", "English", LANGID_CONFIDENCE_THRESHOLD, {})
    assert result.confident


def test_detect_maps_runner_name_to_code(monkeypatch) -> None:
    def fake_runner(spec, wav, language, **kwargs):
        return {"name": "Russian", "score": 0.9, "scores": {"Russian": 0.9}}

    monkeypatch.setattr(langid, "run_runner", fake_runner)
    result = langid.detect_language(Path("whatever.wav"))
    assert result.code == "ru"
    assert result.name == "Russian"
    assert result.confident


def test_detect_keeps_explicit_code(monkeypatch) -> None:
    monkeypatch.setattr(
        langid, "run_runner",
        lambda *a, **k: {"code": "de", "name": "German", "score": 0.8},
    )
    assert langid.detect_language(Path("x.wav")).code == "de"
