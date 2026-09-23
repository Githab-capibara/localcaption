"""Tests for the pipeline orchestration layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from localcaption.asr import MULTILINGUAL_MODEL, TranscriptionResult
from localcaption.download import DownloadResult
from localcaption.langid import LangIdResult
from localcaption.pipeline import (
    PipelineResult,
    _is_local_file,
    normalize_language,
    resolve_model,
    transcribe_url,
)


@pytest.fixture(autouse=True)
def _isolate_index(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALCAPTION_INDEX_PATH", str(tmp_path / "index.jsonl"))


def _stub_wav(monkeypatch) -> None:
    def fake_to_wav(src, dst):
        dst.write_text("fake wav")
        return dst

    monkeypatch.setattr("localcaption.pipeline.to_wav", fake_to_wav)


def _fake_transcribe(language="en", model="parakeet-tdt-0.6b-v3"):
    """Return a fake ``asr.transcribe`` writing real artefact files."""
    def fake(wav, out_base, *, language="auto", model=None, detected_language=None,
             output_format="md"):
        base = Path(out_base)
        base.parent.mkdir(parents=True, exist_ok=True)
        md = base.parent / f"{base.name}.md"
        md.write_text("Welcome to the show\nFirst, let's install\nNow the demo begins\n")
        txt = base.parent / f"{base.name}.txt"
        if output_format != "md":
            txt.write_text("Welcome to the show\nFirst, let's install\nNow the demo begins\n")
        srt = base.parent / f"{base.name}.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nWelcome to the show\n")
        vtt = base.parent / f"{base.name}.vtt"
        vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nWelcome\n")
        json_path = base.parent / f"{base.name}.json"
        json_path.write_text(json.dumps({
            "model": model,
            "language": language,
            "text": "Welcome to the show First, let's install Now the demo begins",
            "segments": [
                {"start": 0, "end": 2, "text": "Welcome to the show"},
                {"start": 160, "end": 165, "text": "First, let's install"},
                {"start": 500, "end": 504, "text": "Now the demo begins"},
            ],
        }))
        # In md mode the transcript path points at the single .md file.
        txt_ref = md if output_format == "md" else txt
        return TranscriptionResult(
            txt=txt_ref, srt=srt, vtt=vtt, json=json_path, md=md,
            language=language, model=model,
        )

    return fake


class TestIsLocalFile:
    def test_existing_file_returns_true(self, tmp_path: Path) -> None:
        video = tmp_path / "video.mp4"
        video.write_text("fake")
        assert _is_local_file(str(video)) is True

    def test_url_returns_false(self) -> None:
        assert _is_local_file("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is False
        assert _is_local_file("file:///tmp/x.mp4") is False

    def test_nonexistent_path_returns_false(self, tmp_path: Path) -> None:
        assert _is_local_file(str(tmp_path / "nope.mp4")) is False


class TestLanguageRouting:
    def test_normalize_language(self) -> None:
        assert normalize_language("auto") == "auto"
        assert normalize_language("") == "auto"
        assert normalize_language("ru") == "ru"
        assert normalize_language("Russian") == "ru"
        assert normalize_language("en") == "en"

    def test_resolve_concrete_language(self, tmp_path: Path) -> None:
        assert resolve_model("ru", tmp_path / "x.wav", None) == ("qwen3-asr-0.6b", "ru")
        assert resolve_model("en", tmp_path / "x.wav", None) == ("parakeet-tdt-0.6b-v3", "en")
        assert resolve_model("de", tmp_path / "x.wav", None) == (MULTILINGUAL_MODEL, "de")

    def test_resolve_auto_uses_langid(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "localcaption.pipeline.langid.detect_language",
            lambda wav: LangIdResult("ru", "Russian", 0.95, {}),
        )
        assert resolve_model("auto", tmp_path / "x.wav", None) == ("qwen3-asr-0.6b", "ru")

    def test_low_confidence_falls_back_to_multilingual(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "localcaption.pipeline.langid.detect_language",
            lambda wav: LangIdResult("de", "German", 0.3, {}),
        )
        assert resolve_model("auto", tmp_path / "x.wav", None) == (MULTILINGUAL_MODEL, "de")

    def test_force_model_overrides_routing(self, tmp_path: Path) -> None:
        assert resolve_model("auto", tmp_path / "x.wav", "qwen3-asr-0.6b") == (
            "qwen3-asr-0.6b", "ru",
        )
        assert resolve_model("en", tmp_path / "x.wav", "nemotron-3.5-asr-streaming-0.6b") == (
            "nemotron-3.5-asr-streaming-0.6b", "en",
        )


class TestTranscribeUrlLocalFile:
    def test_local_file_skips_download(self, monkeypatch, tmp_path: Path) -> None:
        video = tmp_path / "my_video.mp4"
        video.write_text("fake video")
        download_called = False

        def fake_download(url, work_dir, **_kwargs):
            nonlocal download_called
            download_called = True
            return work_dir / "downloaded.mp4"

        monkeypatch.setattr("localcaption.pipeline.download_audio", fake_download)
        _stub_wav(monkeypatch)
        monkeypatch.setattr("localcaption.pipeline.asr.transcribe", _fake_transcribe())

        result = transcribe_url(
            str(video), out_dir=tmp_path / "out", language="en", keep_intermediate=True
        )
        assert download_called is False
        assert isinstance(result, PipelineResult)
        assert result.audio_path == video.resolve()

    def test_local_file_uses_correct_stem(self, monkeypatch, tmp_path: Path) -> None:
        video = tmp_path / "interview.mkv"
        video.write_text("fake video")
        captured: dict[str, Path] = {}
        real = _fake_transcribe()

        def spy(wav, out_base, **kw):
            captured["out_base"] = out_base
            return real(wav, out_base, **kw)

        _stub_wav(monkeypatch)
        monkeypatch.setattr("localcaption.pipeline.asr.transcribe", spy)
        transcribe_url(str(video), out_dir=tmp_path / "out", language="en")
        assert captured["out_base"] == tmp_path / "out" / "interview"

    def test_explicit_stem_overrides_filename(self, monkeypatch, tmp_path: Path) -> None:
        video = tmp_path / "interview.mkv"
        video.write_text("fake video")
        captured: dict[str, Path] = {}
        real = _fake_transcribe()

        def spy(wav, out_base, **kw):
            captured["out_base"] = out_base
            return real(wav, out_base, **kw)

        _stub_wav(monkeypatch)
        monkeypatch.setattr("localcaption.pipeline.asr.transcribe", spy)
        transcribe_url(str(video), out_dir=tmp_path / "out", language="en", stem="custom_id")
        assert captured["out_base"] == tmp_path / "out" / "custom_id"

    def test_keep_intermediate_preserves_paths(self, monkeypatch, tmp_path: Path) -> None:
        video = tmp_path / "podcast.mp3"
        video.write_text("fake audio")
        _stub_wav(monkeypatch)
        monkeypatch.setattr("localcaption.pipeline.asr.transcribe", _fake_transcribe())

        result = transcribe_url(
            str(video), out_dir=tmp_path / "out", language="en", keep_intermediate=True
        )
        assert result.audio_path == video.resolve()
        assert result.wav_path is not None
        assert result.wav_path.name == "podcast.16k.wav"

    def test_no_keep_intermediate_clears_paths(self, monkeypatch, tmp_path: Path) -> None:
        video = tmp_path / "podcast.mp3"
        video.write_text("fake audio")
        _stub_wav(monkeypatch)
        monkeypatch.setattr("localcaption.pipeline.asr.transcribe", _fake_transcribe())

        result = transcribe_url(str(video), out_dir=tmp_path / "out", language="en")
        assert result.audio_path is None
        assert result.wav_path is None


class TestTranscribeUrlRemote:
    def test_url_calls_download(self, monkeypatch, tmp_path: Path) -> None:
        def fake_download(url, work_dir, **_kwargs):
            downloaded = work_dir / "yt_video.m4a"
            downloaded.write_text("fake audio")
            return DownloadResult(path=downloaded, info={"id": "yt_video", "title": "YT"})

        monkeypatch.setattr("localcaption.pipeline.download_audio", fake_download)
        _stub_wav(monkeypatch)
        monkeypatch.setattr("localcaption.pipeline.asr.transcribe", _fake_transcribe())

        result = transcribe_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            out_dir=tmp_path / "out",
            language="en",
            output_format="all",
        )
        assert result.source_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert result.transcripts.txt.is_file()


INFO_WITH_CHAPTERS = {
    "id": "vid123",
    "title": "Test Lecture",
    "webpage_url": "https://www.youtube.com/watch?v=vid123",
    "duration": 600,
    "chapters": [
        {"title": "Intro", "start_time": 0, "end_time": 150},
        {"title": "Setup", "start_time": 150, "end_time": 494},
        {"title": "Demo", "start_time": 494, "end_time": 600},
    ],
}


def _remote_stubs(monkeypatch, info=INFO_WITH_CHAPTERS):
    def fake_download(url, work_dir, **_kwargs):
        downloaded = work_dir / f"{info.get('id', 'plain')}.m4a"
        downloaded.write_text("fake audio")
        return DownloadResult(path=downloaded, info=info)

    monkeypatch.setattr("localcaption.pipeline.download_audio", fake_download)
    _stub_wav(monkeypatch)
    monkeypatch.setattr("localcaption.pipeline.asr.transcribe", _fake_transcribe())


class TestChaptersAndIndex:
    def test_writes_chapters_json_and_chaptered_md(self, monkeypatch, tmp_path: Path) -> None:
        _remote_stubs(monkeypatch)
        result = transcribe_url(
            "https://www.youtube.com/watch?v=vid123",
            out_dir=tmp_path / "out",
            language="en",
            output_format="all",
        )
        assert result.chapters_json is not None and result.chapters_json.is_file()
        payload = json.loads(result.chapters_json.read_text())
        assert [c["title"] for c in payload] == ["Intro", "Setup", "Demo"]
        md = result.chaptered_md.read_text()
        assert "## 00:00 Intro" in md
        assert "## 02:30 Setup" in md
        assert "## 08:14 Demo" in md
        raw = (tmp_path / "out" / "vid123.txt").read_text()
        assert "## " not in raw

    def test_default_md_folds_chapters_into_single_md(self, monkeypatch, tmp_path: Path) -> None:
        _remote_stubs(monkeypatch)
        result = transcribe_url(
            "https://www.youtube.com/watch?v=vid123",
            out_dir=tmp_path / "out",
            language="en",
        )
        # Single-file mode: no chapter sidecars, transcript folded into the .md.
        assert result.chapters_json is None
        assert result.chaptered_md is None
        md = (tmp_path / "out" / "vid123.md").read_text()
        assert "## 00:00 Intro" in md
        assert "## 02:30 Setup" in md
        assert "## 08:14 Demo" in md
        assert not (tmp_path / "out" / "vid123.txt").exists()
        assert not (tmp_path / "out" / "vid123.chapters.json").exists()
        assert not (tmp_path / "out" / "vid123.chaptered.md").exists()

    def test_no_chapters_skips_sidecars(self, monkeypatch, tmp_path: Path) -> None:
        _remote_stubs(monkeypatch, info={"id": "plain", "title": "No chapters", "chapters": None})
        result = transcribe_url(
            "https://example.com/plain", out_dir=tmp_path / "out", language="en"
        )
        assert result.chapters_json is None
        assert result.chaptered_md is None

    def test_index_entry_written(self, monkeypatch, tmp_path: Path) -> None:
        index_path = tmp_path / "index.jsonl"
        _remote_stubs(monkeypatch)
        transcribe_url(
            "https://www.youtube.com/watch?v=vid123",
            out_dir=tmp_path / "out",
            language="en",
            output_format="all",
        )
        row = json.loads(index_path.read_text().splitlines()[0])
        assert row["id"] == "vid123"
        assert row["title"] == "Test Lecture"
        assert row["duration"] == 600
        assert row["language"] == "en"
        assert row["model"] == "parakeet-tdt-0.6b-v3"
        assert row["transcript"].endswith("vid123.txt")

    def test_index_entry_points_to_md_in_default_mode(self, monkeypatch, tmp_path: Path) -> None:
        index_path = tmp_path / "index.jsonl"
        _remote_stubs(monkeypatch, info={"id": "plain", "title": "No chapters", "chapters": None})
        transcribe_url("https://example.com/plain", out_dir=tmp_path / "out", language="en")
        row = json.loads(index_path.read_text().splitlines()[0])
        assert row["transcript"].endswith("plain.md")

    def test_dotted_id_keeps_full_stem(self, monkeypatch, tmp_path: Path) -> None:
        info = {**INFO_WITH_CHAPTERS, "id": "ep.12", "webpage_url": "https://example.com/ep.12"}
        _remote_stubs(monkeypatch, info=info)
        result = transcribe_url(
            "https://example.com/ep.12", out_dir=tmp_path / "out", language="en",
            output_format="all",
        )
        assert result.chapters_json == tmp_path / "out" / "ep.12.chapters.json"
        assert (tmp_path / "out" / "ep.12.txt").is_file()
        assert not (tmp_path / "out" / "ep.chapters.json").exists()

    def test_corrupt_index_does_not_fail_run(self, monkeypatch, tmp_path: Path) -> None:
        index_path = tmp_path / "index.jsonl"
        index_path.write_text("[1, 2, 3]\nnot json\n")
        _remote_stubs(monkeypatch, info={"id": "plain", "title": "No chapters", "chapters": None})
        result = transcribe_url("https://example.com/plain", out_dir=tmp_path / "out", language="en")
        assert result.transcripts.md.is_file()
        assert "id" in index_path.read_text()


class TestSummary:
    def test_summary_writes_and_returns_path(self, monkeypatch, tmp_path: Path) -> None:
        video = tmp_path / "interview.mkv"
        video.write_text("fake video")
        _stub_wav(monkeypatch)
        monkeypatch.setattr("localcaption.pipeline.asr.transcribe", _fake_transcribe())
        written: dict[str, object] = {}

        def fake_write_summary(txt, *, model, prompt_path):
            written["txt"] = txt
            written["model"] = model
            written["prompt_path"] = prompt_path
            out = Path(txt).with_name(f"{Path(txt).stem}.summary.md")
            out.write_text("sum")
            return out

        monkeypatch.setattr("localcaption.pipeline.write_summary", fake_write_summary)
        result = transcribe_url(
            str(video), out_dir=tmp_path / "out", language="en",
            summary=True, summary_model="mistral", summary_prompt=tmp_path / "prompt.txt",
            output_format="all",
        )
        assert result.summary == tmp_path / "out" / "interview.summary.md"
        assert written["model"] == "mistral"
        assert Path(written["txt"]).name == "interview.txt"

    def test_summary_off_by_default(self, monkeypatch, tmp_path: Path) -> None:
        video = tmp_path / "interview.mkv"
        video.write_text("fake video")
        _stub_wav(monkeypatch)
        monkeypatch.setattr("localcaption.pipeline.asr.transcribe", _fake_transcribe())
        called = {"n": 0}
        monkeypatch.setattr(
            "localcaption.pipeline.write_summary",
            lambda *a, **k: called.__setitem__("n", called["n"] + 1),
        )
        result = transcribe_url(str(video), out_dir=tmp_path / "out", language="en")
        assert called["n"] == 0
        assert result.summary is None
