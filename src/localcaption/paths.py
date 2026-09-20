"""Filesystem layout: where models and per-model runtimes live.

Two roots, both overridable by environment variables:

``models/``
    The 4 model checkpoints (language ID + 3 ASR models), one directory
    per model. ``$LOCALCAPTION_MODELS_DIR`` overrides.

``runtime/``
    One isolated Python environment per model family, because the ASR
    stacks pin incompatible ``transformers`` versions.
    ``$LOCALCAPTION_RUNTIME_DIR`` overrides.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def repo_root() -> Path:
    """Root of the localcaption checkout (the directory holding ``src/``)."""
    return Path(__file__).resolve().parents[2]


def models_root() -> Path:
    env = os.environ.get("LOCALCAPTION_MODELS_DIR")
    if env:
        return Path(env).expanduser()
    return repo_root() / "models"


def runtime_root() -> Path:
    env = os.environ.get("LOCALCAPTION_RUNTIME_DIR")
    if env:
        return Path(env).expanduser()
    return repo_root() / "runtime"


def model_dir(key: str) -> Path:
    """Local directory holding the checkpoint files for *key*."""
    return models_root() / key


def venv_dir(env_name: str) -> Path:
    return runtime_root() / env_name


def venv_python(env_name: str) -> Path:
    """Interpreter of a per-model environment (POSIX layout preferred)."""
    root = venv_dir(env_name)
    posix = root / "bin" / "python"
    if posix.exists():
        return posix
    windows = root / "Scripts" / "python.exe"
    return windows


def runners_dir() -> Path:
    return Path(__file__).resolve().parent / "runners"


def runner_script(name: str) -> Path:
    return runners_dir() / f"{name}.py"


def current_python() -> str:
    return sys.executable
