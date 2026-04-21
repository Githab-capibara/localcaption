"""Tests for the `localcaption doctor` and dispatcher behaviour.

We don't want these to depend on a real whisper.cpp build, so we point the
diagnostic at a fixture directory and assert on the output text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from localcaption.cli import _candidate_whisper_dirs, main


def test_top_level_help_no_args(capsys) -> None:
    rc = main([])
    assert rc == 2  # bare invocation should be a non-zero exit
    out = capsys.readouterr().out
    assert "doctor" in out
    assert "transcribe" in out


def test_help_alias_zero_exit(capsys) -> None:
    rc = main(["help"])
    assert rc == 0
    assert "doctor" in capsys.readouterr().out


def test_doctor_runs_without_install(capsys, tmp_path: Path) -> None:
    """`localcaption doctor` must produce a report even if nothing is installed."""
    rc = main(["doctor", "--whisper-dir", str(tmp_path / "missing")])
    out = capsys.readouterr().out
    assert "localcaption" in out
    assert "System tools" in out
    assert "whisper.cpp" in out
    # Missing whisper.cpp directory → non-zero exit
    assert rc == 1


def test_doctor_recognises_built_install(capsys, tmp_path: Path) -> None:
    """A whisper.cpp directory with a binary + model should pass."""
    whisper_dir = tmp_path / "whisper.cpp"
    bin_path = whisper_dir / "build" / "bin" / "whisper-cli"
    bin_path.parent.mkdir(parents=True)
    bin_path.write_text("#!/bin/sh\nexit 0\n")
    bin_path.chmod(0o755)

    models_dir = whisper_dir / "models"
    models_dir.mkdir()
    (models_dir / "ggml-base.en.bin").write_bytes(b"\x00" * 16)

    rc = main(["doctor", "--whisper-dir", str(whisper_dir)])
    out = capsys.readouterr().out
    assert "binary built" in out
    assert "ggml-base.en.bin" in out
    # ffmpeg / yt-dlp may or may not be present in the test env; the doctor
    # exits non-zero only if anything fails. Just assert the whisper section
    # was happy by checking the binary line shows ✅.
    assert "✅" in out
    # Don't assert on `rc` — depends on host env.
    del rc


def test_candidate_dirs_respects_env(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom-whisper"
    monkeypatch.setenv("LOCALCAPTION_WHISPER_DIR", str(custom))
    candidates = _candidate_whisper_dirs()
    assert candidates[0] == custom
    # Also includes the dev-checkout and XDG paths
    assert any("whisper.cpp" in str(c) for c in candidates[1:])


def test_unknown_subcommand_treated_as_url(monkeypatch) -> None:
    """Anything that isn't a known subcommand should fall through to transcribe.

    We don't want to actually transcribe in a unit test, so we patch
    transcribe_url to raise a known exception and assert it was reached.
    """
    sentinel: dict[str, str] = {}

    def fake(url, **kw):
        sentinel["url"] = url
        raise SystemExit(0)

    monkeypatch.setattr("localcaption.cli.transcribe_url", fake)
    with pytest.raises(SystemExit):
        main(["https://example.com/video"])
    assert sentinel["url"] == "https://example.com/video"
