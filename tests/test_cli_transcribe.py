"""Tests for the default transcribe subcommand and dispatcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from localcaption.cli import main


@pytest.fixture(autouse=True)
def _skip_model_prompts(monkeypatch) -> None:
    """Never download or prompt for models during CLI unit tests."""
    monkeypatch.setattr("localcaption.cli._ensure_models", lambda *_a, **_k: True)


class TestCliHelpText:
    def test_transcribe_help_mentions_local_file(self, capsys) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--help"])
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        assert "local video/audio file" in out
        assert "--batch" in out
        assert "--language" in out
        assert "--model" in out

    def test_top_level_help_mentions_url_or_file(self, capsys) -> None:
        rc = main([])
        assert rc == 2
        assert "url-or-file" in capsys.readouterr().out

    def test_help_mentions_summary_flags(self, capsys) -> None:
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "--summary" in out
        assert "--summary-model" in out
        assert "--summary-prompt" in out
        assert "llama3.1:8b" in out


class TestCliDispatch:
    def test_local_file_passed_to_pipeline(self, monkeypatch, tmp_path: Path) -> None:
        video = tmp_path / "my_video.mp4"
        video.write_text("fake")
        sentinel: dict[str, object] = {}

        def fake_transcribe_url(url, **kw):
            sentinel["url"] = url
            sentinel.update(kw)
            raise SystemExit(0)

        monkeypatch.setattr("localcaption.cli.transcribe_url", fake_transcribe_url)
        with pytest.raises(SystemExit):
            main([str(video), "--language", "en"])
        assert sentinel["url"] == str(video)
        assert sentinel["language"] == "en"
        assert sentinel["force_model"] is None

    def test_force_model_forwarded(self, monkeypatch) -> None:
        sentinel: dict[str, object] = {}

        def fake_transcribe_url(url, **kw):
            sentinel.update(kw)
            raise SystemExit(0)

        monkeypatch.setattr("localcaption.cli.transcribe_url", fake_transcribe_url)
        with pytest.raises(SystemExit):
            main(["--model", "qwen3-asr-0.6b", "https://example.com/v"])
        assert sentinel["force_model"] == "qwen3-asr-0.6b"

    def test_summary_flags_forwarded(self, monkeypatch, tmp_path: Path) -> None:
        captured: dict = {}
        prompt = tmp_path / "prompt.txt"
        prompt.write_text("hi")

        def fake_transcribe_url(url, **kw):
            captured.update(kw)
            raise SystemExit(0)

        monkeypatch.setattr("localcaption.cli.transcribe_url", fake_transcribe_url)
        with pytest.raises(SystemExit):
            main([
                "https://example.com/v",
                "--summary",
                "--summary-model", "mistral",
                "--summary-prompt", str(prompt),
            ])
        assert captured["summary"] is True
        assert captured["summary_model"] == "mistral"
        assert captured["summary_prompt"] == prompt


class TestCliBatch:
    def test_batch_flag_dispatches_parsed_urls(self, monkeypatch, tmp_path: Path, capsys) -> None:
        listing = tmp_path / "urls.txt"
        listing.write_text(
            "# queue\n"
            "https://www.youtube.com/watch?v=aircAruvnKk\n"
            "\n"
            "https://youtu.be/PSRJfaAYkW4\n",
            encoding="utf-8",
        )
        sentinel: dict[str, object] = {}

        def fake_transcribe_urls(urls, **kw):
            sentinel["urls"] = urls
            sentinel["out_dir"] = kw["out_dir"]
            sentinel["language"] = kw["language"]
            sentinel["force_model"] = kw.get("force_model")
            from localcaption.batch import BatchResult

            return BatchResult(items=[], wall_clock_s=0.0)

        monkeypatch.setattr("localcaption.cli.transcribe_urls", fake_transcribe_urls)
        out = tmp_path / "transcripts"
        rc = main([
            "--batch", str(listing),
            "-o", str(out),
            "--language", "ru",
            "--model", "qwen3-asr-0.6b",
        ])
        assert rc == 0
        assert sentinel["urls"] == [
            "https://www.youtube.com/watch?v=aircAruvnKk",
            "https://youtu.be/PSRJfaAYkW4",
        ]
        assert sentinel["out_dir"] == out
        assert sentinel["language"] == "ru"
        assert sentinel["force_model"] == "qwen3-asr-0.6b"
        assert "total: 0" in capsys.readouterr().out

    def test_batch_missing_file_exits_1(self, tmp_path: Path) -> None:
        rc = main(["--batch", str(tmp_path / "nope.txt")])
        assert rc == 1

    def test_batch_and_url_rejected(self, tmp_path: Path) -> None:
        listing = tmp_path / "urls.txt"
        listing.write_text("https://youtu.be/PSRJfaAYkW4\n", encoding="utf-8")
        with pytest.raises(SystemExit) as excinfo:
            main(["https://youtu.be/PSRJfaAYkW4", "--batch", str(listing)])
        assert excinfo.value.code == 2

    def test_neither_url_nor_batch_exits_2(self, capsys) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--language", "en"])
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "provide a URL/file or --batch FILE" in err

    def test_batch_nonzero_when_items_fail(self, monkeypatch, tmp_path: Path) -> None:
        listing = tmp_path / "urls.txt"
        listing.write_text("https://youtu.be/PSRJfaAYkW4\n", encoding="utf-8")

        def fake_transcribe_urls(urls, **kw):
            from localcaption.batch import BatchItem, BatchResult

            return BatchResult(
                items=[
                    BatchItem(
                        source=urls[0],
                        video_id="PSRJfaAYkW4",
                        status="failed",
                        duration_s=None,
                        elapsed_s=0.0,
                        error="DownloadError: HTTP 403",
                    )
                ],
                wall_clock_s=1.0,
            )

        monkeypatch.setattr("localcaption.cli.transcribe_urls", fake_transcribe_urls)
        rc = main(["--batch", str(listing)])
        assert rc == 1
