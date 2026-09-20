"""Tests for the curl-based model downloader.

We mock the subprocess boundary rather than hit Hugging Face (slow, flaky,
and requires the proxy). The interesting logic is: which files get fetched,
skip-when-present, force, and the atomic ``.part`` → final rename.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from localcaption import models
from localcaption.errors import DependencyError


def _fake_curl(monkeypatch: pytest.MonkeyPatch, *, body: bytes = b"payload") -> list[list[str]]:
    """Make ``subprocess.run`` behave like a successful curl."""
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool) -> None:
        calls.append(cmd)
        out = Path(cmd[cmd.index("-o") + 1])
        out.write_bytes(body)

    monkeypatch.setattr(models.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(models.subprocess, "run", fake_run)
    return calls


def test_run_curl_builds_proxy_command_and_renames(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _fake_curl(monkeypatch)
    dest = tmp_path / "model.safetensors"
    models._run_curl("https://example.com/model.safetensors", dest)

    cmd = calls[0]
    assert cmd[0] == "curl"
    assert "https://example.com/model.safetensors" in cmd
    assert cmd[cmd.index("--proxy") + 1] == models.get_proxy()
    assert dest.read_bytes() == b"payload"
    assert not dest.with_name(dest.name + ".part").exists()


def test_download_model_fetches_only_missing_files(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = models.get_model("langid-ecapa")
    present = spec.local_dir / spec.files[0]
    present.parent.mkdir(parents=True, exist_ok=True)
    present.write_bytes(b"already here")

    fetched: list[str] = []
    monkeypatch.setattr(models, "_run_curl", lambda url, dest: fetched.append(url))

    models.download_model("langid-ecapa")
    assert len(fetched) == len(spec.files) - 1
    assert all(url.startswith(spec.url_base) for url in fetched)
    assert present.read_bytes() == b"already here"


def test_download_model_force_refetches_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = models.get_model("langid-ecapa")
    for rel in spec.files:
        target = spec.local_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x")

    fetched: list[str] = []
    monkeypatch.setattr(models, "_run_curl", lambda url, dest: fetched.append(url))
    models.download_model("langid-ecapa", force=True)
    assert len(fetched) == len(spec.files)


def test_download_all_covers_every_model(monkeypatch: pytest.MonkeyPatch) -> None:
    fetched: list[str] = []
    monkeypatch.setattr(models, "_run_curl", lambda url, dest: fetched.append(url))
    paths = models.download_all()
    assert len(paths) == len(models.known_models())
    total_files = sum(len(m.files) for m in models.known_models())
    assert len(fetched) == total_files


def test_run_curl_requires_curl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(models.shutil, "which", lambda _name: None)
    with pytest.raises(DependencyError, match="curl"):
        models._run_curl("https://example.com/x", tmp_path / "x")
