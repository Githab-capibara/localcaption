"""Tests for the `localcaption model {list,download,rm,info}` CLI plumbing.

These tests exercise the dispatcher and exit codes — the actual download
machinery is tested in test_models_download.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from localcaption import cli, models


def _run(argv: list[str]) -> int:
    return cli.main(argv)


def _install(key: str) -> None:
    spec = models.get_model(key)
    for rel in spec.files:
        target = spec.local_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\0" * (2_000_000 if rel == "model.safetensors" else 8))


# ──────────────────────────────────────────────────────────────────────
# Dispatch
# ──────────────────────────────────────────────────────────────────────


def test_bare_model_prints_usage(capsys):
    rc = _run(["model"])
    out = capsys.readouterr().out
    assert "subcommands" in out
    assert "list" in out and "download" in out and "rm" in out
    assert rc == 2


def test_model_help_exits_zero(capsys):
    rc = _run(["model", "--help"])
    out = capsys.readouterr().out
    assert "subcommands" in out
    assert rc == 0


def test_unknown_subcommand_is_rejected(capsys):
    rc = _run(["model", "frobnicate"])
    err = capsys.readouterr().err
    assert "unknown subcommand" in err
    assert rc == 2


# ──────────────────────────────────────────────────────────────────────
# `model list`
# ──────────────────────────────────────────────────────────────────────


def test_list_includes_all_known_models(capsys):
    rc = _run(["model", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    for spec in models.known_models():
        assert spec.key in out
    assert "not installed" in out


def test_list_marks_installed_models(capsys):
    _install("langid-ecapa")
    rc = _run(["model", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    line = next(ln for ln in out.splitlines() if ln.lstrip().startswith("langid-ecapa"))
    assert "installed" in line


# ──────────────────────────────────────────────────────────────────────
# `model info`
# ──────────────────────────────────────────────────────────────────────


def test_info_shows_metadata_for_known_model(capsys):
    rc = _run(["model", "info", "parakeet-tdt-0.6b-v3"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "parakeet-tdt-0.6b-v3" in out
    assert "english" in out
    assert "huggingface.co" in out
    assert "Installed:    no" in out


def test_info_shows_installed_status_when_present(capsys):
    _install("qwen3-asr-0.6b")
    rc = _run(["model", "info", "qwen3-asr-0.6b"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Installed:    yes" in out


def test_info_unknown_model_returns_error(capsys):
    rc = _run(["model", "info", "totally-fake"])
    err = capsys.readouterr().err
    assert "Unknown model" in err
    assert rc == 2


# ──────────────────────────────────────────────────────────────────────
# `model download`
# ──────────────────────────────────────────────────────────────────────


def test_download_invokes_registry(monkeypatch, capsys):
    called: list[str] = []
    monkeypatch.setattr(models, "download_model", lambda key, force=False: called.append(key) or Path("/x"))
    rc = _run(["model", "download", "qwen3-asr-0.6b"])
    assert rc == 0
    assert called == ["qwen3-asr-0.6b"]


def test_download_all(monkeypatch, capsys):
    called: list[str] = []
    monkeypatch.setattr(models, "download_model", lambda key, force=False: called.append(key) or Path("/x"))
    rc = _run(["model", "download", "--all"])
    assert rc == 0
    assert len(called) == len(models.known_models())


def test_download_requires_key_or_all(capsys):
    with pytest.raises(SystemExit) as excinfo:
        _run(["model", "download"])
    assert excinfo.value.code == 2


# ──────────────────────────────────────────────────────────────────────
# `model rm`
# ──────────────────────────────────────────────────────────────────────


def test_rm_with_yes_flag_removes(capsys):
    _install("langid-ecapa")
    target = models.get_model("langid-ecapa").local_dir
    assert target.is_dir()
    rc = _run(["model", "rm", "langid-ecapa", "-y"])
    out = capsys.readouterr().out
    assert rc == 0
    assert not target.exists()
    assert "Removed" in out


def test_rm_missing_model_returns_error(capsys):
    rc = _run(["model", "rm", "langid-ecapa", "-y"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not installed" in err


def test_rm_aliases():
    for alias in ("rm", "remove", "delete"):
        _install("parakeet-tdt-0.6b-v3")
        rc = _run(["model", alias, "parakeet-tdt-0.6b-v3", "-y"])
        assert rc == 0, f"alias {alias!r} failed"
