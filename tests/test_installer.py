"""Tests for `localcaption.installer`.

We can't actually install packages or run setup_runtime.sh in unit tests, so
every external command is mocked at the `subprocess.run` boundary. The goal is
to exercise the *orchestration* logic — argument shape, ordering, skip
conditions, error translation — not the underlying tools.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from localcaption import installer
from localcaption.errors import InstallError

# --- Detection ------------------------------------------------------------


def test_detect_platform_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Darwin")
    assert installer.detect_platform() == "macos"


def test_detect_platform_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Linux")
    assert installer.detect_platform() == "linux"


def test_detect_platform_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Windows")
    assert installer.detect_platform() == "unsupported"


def test_detect_package_manager_prefers_brew(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.shutil, "which",
                        lambda name: "/opt/homebrew/bin/brew" if name == "brew" else None)
    assert installer.detect_package_manager() == "brew"


def test_detect_package_manager_falls_back_to_apt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.shutil, "which",
                        lambda name: "/usr/bin/apt-get" if name == "apt-get" else None)
    assert installer.detect_package_manager() == "apt"


def test_detect_package_manager_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    assert installer.detect_package_manager() is None


# --- _run wrapper ---------------------------------------------------------


def test_run_raises_install_error_on_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **_kw: Any) -> None:
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    with pytest.raises(InstallError, match="exit 1"):
        installer._run(["false"], label="boom")


def test_run_raises_install_error_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **_kw: Any) -> None:
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    with pytest.raises(InstallError, match="command not found"):
        installer._run(["nope"], label="missing")


def test_run_passes_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kw: Any) -> None:
        seen["cmd"] = cmd
        seen["cwd"] = kw.get("cwd")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    installer._run(["echo", "hi"], label="echo", cwd=tmp_path)
    assert seen == {"cmd": ["echo", "hi"], "cwd": tmp_path}


# --- install_system_dep ---------------------------------------------------


def test_install_system_dep_skip_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/usr/bin/" + name)
    calls: list[list[str]] = []
    monkeypatch.setattr(installer, "_run", lambda cmd, **_kw: calls.append(cmd))
    installer.install_system_dep("ffmpeg")
    assert calls == []  # nothing to do


def test_install_system_dep_unknown_dep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    with pytest.raises(InstallError, match="Don't know how to install"):
        installer.install_system_dep("nonsense-tool")


def test_install_system_dep_no_package_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    monkeypatch.setattr(installer.platform, "system", lambda: "Darwin")
    with pytest.raises(InstallError, match="No supported package manager"):
        installer.install_system_dep("ffmpeg")


def test_install_system_dep_uses_brew_on_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    def which(name: str) -> str | None:
        return "/opt/homebrew/bin/brew" if name == "brew" else None

    monkeypatch.setattr(installer.shutil, "which", which)
    calls: list[list[str]] = []
    monkeypatch.setattr(installer, "_run", lambda cmd, **_kw: calls.append(cmd))
    installer.install_system_dep("ffmpeg")
    assert calls == [["brew", "install", "ffmpeg"]]


def test_install_system_dep_uses_apt_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    def which(name: str) -> str | None:
        return "/usr/bin/apt-get" if name == "apt-get" else None

    monkeypatch.setattr(installer.shutil, "which", which)
    calls: list[list[str]] = []
    monkeypatch.setattr(installer, "_run", lambda cmd, **_kw: calls.append(cmd))
    installer.install_system_dep("curl")
    assert calls == [
        ["sudo", "apt-get", "update", "-y"],
        ["sudo", "apt-get", "install", "-y", "curl"],
    ]


# --- ensure_runtime -------------------------------------------------------


def test_ensure_runtime_runs_setup_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = tmp_path / "scripts" / "setup_runtime.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\n")

    monkeypatch.setattr(installer.paths, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    calls: list[list[str]] = []
    monkeypatch.setattr(installer, "_run", lambda cmd, **kw: calls.append(cmd))
    installer.ensure_runtime()
    assert calls == [["bash", str(script)]]


def test_ensure_runtime_requires_uv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "setup_runtime.sh").write_text("#!/bin/sh\n")
    monkeypatch.setattr(installer.paths, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    with pytest.raises(InstallError, match="uv"):
        installer.ensure_runtime()


def test_ensure_runtime_missing_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(installer.paths, "repo_root", lambda: tmp_path)
    with pytest.raises(InstallError, match="setup script not found"):
        installer.ensure_runtime()
