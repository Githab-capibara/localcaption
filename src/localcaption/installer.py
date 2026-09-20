"""Self-healing installer for localcaption's external dependencies.

This module exists so ``localcaption doctor --fix`` can put a broken or
missing install back together without shelling out to ``install.sh``. The
shell script remains the bootstrap for first-time users (it's the thing
``curl | bash`` invokes), but the *logic* lives here so we have one place
to test it from and one place to evolve it.

Two concerns, two entry points:

* :func:`install_system_dep` — install ffmpeg/git/curl via brew/apt.
* :func:`ensure_runtime` — run ``scripts/setup_runtime.sh`` to create the
  per-model virtualenvs (the ones hosting the four checkpoints).

:func:`detect_platform` / :func:`detect_package_manager` are used by both
callers and tests to decide what's even possible on this host.

All failures raise :class:`~localcaption.errors.InstallError` with an
actionable, copy-pasteable message — never a bare ``CalledProcessError``.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from . import _logging as log
from . import paths
from .errors import InstallError

Platform = Literal["macos", "linux", "unsupported"]
PackageManager = Literal["brew", "apt"]

# System dependencies we know how to install. Map: dep name → package name
# under each package manager.
_SYSTEM_DEP_PACKAGES: dict[str, dict[PackageManager, str]] = {
    "ffmpeg": {"brew": "ffmpeg", "apt": "ffmpeg"},
    "git": {"brew": "git", "apt": "git"},
    "curl": {"brew": "curl", "apt": "curl"},
}


# --- Detection helpers ----------------------------------------------------


def detect_platform() -> Platform:
    """Return ``"macos"``, ``"linux"``, or ``"unsupported"``."""
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Linux":
        return "linux"
    return "unsupported"


def detect_package_manager() -> PackageManager | None:
    """Return the first package manager we can drive on this host, if any.

    macOS prefers Homebrew, Linux prefers apt. Everything else returns
    ``None`` and the caller is expected to print a manual-install hint.
    """
    if shutil.which("brew"):
        return "brew"
    if shutil.which("apt-get"):
        return "apt"
    return None


# --- Subprocess wrapper ---------------------------------------------------


def _run(cmd: list[str], *, label: str, cwd: Path | None = None) -> None:
    """Run *cmd*, streaming output to the user's terminal.

    On non-zero exit raises :class:`InstallError` with an actionable message
    that includes the failed command and the working directory. We
    deliberately do **not** capture stdout/stderr — for long-running steps
    the live progress is the UX.
    """
    pretty = " ".join(cmd)
    log.info(f"{label}: {pretty}")
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise InstallError(
            f"{label} failed: command not found ({cmd[0]}). "
            f"Install it first, then re-run."
        ) from exc
    except subprocess.CalledProcessError as exc:
        loc = f" (in {cwd})" if cwd else ""
        raise InstallError(
            f"{label} failed (exit {exc.returncode}){loc}:\n    {pretty}"
        ) from exc


# --- System deps ----------------------------------------------------------


def install_system_dep(name: str) -> None:
    """Install a system tool (``ffmpeg``, ``git``, ``curl``) via the host's
    package manager. No-op if the tool is already on ``PATH``.

    Raises :class:`InstallError` if the dependency is unknown to us, the
    platform is unsupported, or no package manager is available.
    """
    if shutil.which(name):
        log.info(f"{name}: already installed")
        return

    if name not in _SYSTEM_DEP_PACKAGES:
        raise InstallError(
            f"Don't know how to install '{name}' automatically. "
            f"Please install it manually and re-run."
        )

    pm = detect_package_manager()
    if pm is None:
        plat = detect_platform()
        hint = (
            "brew install ffmpeg git curl" if plat == "macos"
            else "sudo apt-get install -y ffmpeg git curl"
        )
        raise InstallError(
            f"No supported package manager found (need brew or apt-get) "
            f"to install '{name}'.\n"
            f"Install it manually:\n    {hint}"
        )

    pkg = _SYSTEM_DEP_PACKAGES[name][pm]
    if pm == "brew":
        _run(["brew", "install", pkg], label=f"install {name}")
    else:  # apt
        _run(["sudo", "apt-get", "update", "-y"], label="apt update")
        _run(["sudo", "apt-get", "install", "-y", pkg], label=f"install {name}")


# --- per-model runtimes ---------------------------------------------------


def ensure_runtime() -> None:
    """Create/repair the per-model virtualenvs via ``setup_runtime.sh``.

    Requires ``uv`` on ``PATH`` (the script uses it as the Python installer).
    """
    script = paths.repo_root() / "scripts" / "setup_runtime.sh"
    if not script.is_file():
        raise InstallError(f"setup script not found: {script}")
    if shutil.which("uv") is None:
        raise InstallError(
            "uv is required to create the model environments but isn't installed.\n"
            "    curl -LsSf https://astral.sh/uv/install.sh | sh"
        )
    _run(["bash", str(script)], label="setup runtime envs")
