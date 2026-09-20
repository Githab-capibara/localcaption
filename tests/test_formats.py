"""Tests for transcript serialisation (txt/srt/vtt/json)."""

from __future__ import annotations

import json
from pathlib import Path

from localcaption.chapters import Segment
from localcaption.formats import write_json, write_srt, write_txt, write_vtt

SEGMENTS = [
    Segment(start=0.0, end=2.5, text="Hello there"),
    Segment(start=62.25, end=65.0, text="Second line"),
    Segment(start=3661.5, end=3663.0, text="Over an hour"),
]


def test_write_txt_strips_trailing_whitespace(tmp_path: Path) -> None:
    path = write_txt(tmp_path / "a.txt", "hello\n\n")
    assert path.read_text() == "hello\n"


def test_write_txt_empty(tmp_path: Path) -> None:
    path = write_txt(tmp_path / "a.txt", "")
    assert path.read_text() == ""


def test_write_srt_formatting(tmp_path: Path) -> None:
    path = write_srt(tmp_path / "a.srt", SEGMENTS)
    body = path.read_text()
    assert "1\n00:00:00,000 --> 00:00:02,500\nHello there" in body
    assert "2\n00:01:02,250 --> 00:01:05,000\nSecond line" in body
    assert "3\n01:01:01,500 --> 01:01:03,000\nOver an hour" in body


def test_write_srt_skips_empty_text(tmp_path: Path) -> None:
    path = write_srt(tmp_path / "a.srt", [Segment(0, 1, "  "), Segment(1, 2, "real")])
    body = path.read_text()
    assert body.startswith("1\n")
    assert "real" in body


def test_write_vtt_uses_dot_millis(tmp_path: Path) -> None:
    path = write_vtt(tmp_path / "a.vtt", SEGMENTS)
    body = path.read_text()
    assert body.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:02.500" in body


def test_write_json_roundtrip(tmp_path: Path) -> None:
    path = write_json(tmp_path / "a.json", {"language": "ru", "text": "привет"})
    assert json.loads(path.read_text()) == {"language": "ru", "text": "привет"}
