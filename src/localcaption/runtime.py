"""The isolated Python environments that host the ASR / language-ID models.

Three environments are needed because the model stacks pin incompatible
``transformers`` versions (``qwen-asr`` wants 4.x, the NeMo models want
``transformers>=5.13``). Each is created by ``scripts/setup_runtime.sh``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from . import paths

# env name -> import names that must succeed inside it
ENV_IMPORTS: dict[str, tuple[str, ...]] = {
    "langid": ("torch", "speechbrain"),
    "qwen": ("torch", "qwen_asr"),
    "nvidia": ("torch", "transformers"),
}


@dataclass(frozen=True)
class EnvStatus:
    name: str
    exists: bool
    ready: bool
    detail: str


def check_env(name: str) -> EnvStatus:
    python = paths.venv_python(name)
    if not python.exists():
        return EnvStatus(name, exists=False, ready=False, detail=f"no venv at {python}")
    imports = ", ".join(ENV_IMPORTS.get(name, ()))
    code = f"import {', '.join(ENV_IMPORTS.get(name, ()))}" if imports else "pass"
    try:
        proc = subprocess.run(
            [str(python), "-c", code],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return EnvStatus(name, exists=True, ready=False, detail=str(exc))
    if proc.returncode == 0:
        return EnvStatus(name, exists=True, ready=True, detail=imports or "ok")
    err = (proc.stderr or "").strip().splitlines()
    detail = err[-1] if err else f"exit {proc.returncode}"
    return EnvStatus(name, exists=True, ready=False, detail=detail)


def check_all() -> dict[str, EnvStatus]:
    return {name: check_env(name) for name in ENV_IMPORTS}


def missing_envs() -> list[str]:
    return [name for name, status in check_all().items() if not status.ready]


def setup_command() -> str:
    return f"bash {paths.repo_root() / 'scripts' / 'setup_runtime.sh'}"
