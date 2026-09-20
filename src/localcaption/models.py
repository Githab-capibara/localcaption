"""Registry of the four local checkpoints localcaption ships and uses.

Each model has a *role* and an *environment*:

===============  ==================  ==============
key              role                runtime env
===============  ==================  ==============
langid-ecapa     language-id         langid
qwen3-asr-0.6b   russian             qwen
parakeet-tdt...  english             nvidia
nemotron-3.5...  multilingual        nvidia
===============  ==================  ==============
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import _logging as log
from . import paths
from .errors import DependencyError, LocalCaptionError
from .network import get_proxy

MODEL_LANGID = "langid-ecapa"
MODEL_QWEN = "qwen3-asr-0.6b"
MODEL_PARAKEET = "parakeet-tdt-0.6b-v3"
MODEL_NEMOTRON = "nemotron-3.5-asr-streaming-0.6b"

ROLE_LANGID = "language-id"
ROLE_RU = "russian"
ROLE_EN = "english"
ROLE_MULTI = "multilingual"

_LARGE_FILES = {"model.safetensors"}


@dataclass(frozen=True)
class ModelSpec:
    """Static metadata about one local checkpoint."""

    key: str
    hf_repo: str
    role: str
    env: str
    description: str
    approx_size_mb: int
    files: tuple[str, ...]

    @property
    def local_dir(self) -> Path:
        return paths.model_dir(self.key)

    @property
    def url_base(self) -> str:
        return f"https://huggingface.co/{self.hf_repo}/resolve/main"


# ``files`` is the exact set we need. For the NeMo-family repos we skip the
# redundant ``.nemo`` bundle and the GGUF quantisation, since we load the
# safetensors via transformers.
_REGISTRY: tuple[ModelSpec, ...] = (
    ModelSpec(
        key=MODEL_LANGID,
        hf_repo="speechbrain/lang-id-commonlanguage_ecapa",
        role=ROLE_LANGID,
        env="langid",
        description="ECAPA-TDNN language identifier, 45 languages (routing)",
        approx_size_mb=84,
        files=(
            "classifier.ckpt",
            "embedding_model.ckpt",
            "hyperparams.yaml",
            "label_encoder.txt",
            "config.json",
        ),
    ),
    ModelSpec(
        key=MODEL_QWEN,
        hf_repo="Qwen/Qwen3-ASR-0.6B",
        role=ROLE_RU,
        env="qwen",
        description="Qwen3-ASR 0.6B — Russian (WER 5.13)",
        approx_size_mb=1900,
        files=(
            "model.safetensors",
            "config.json",
            "generation_config.json",
            "preprocessor_config.json",
            "tokenizer_config.json",
            "chat_template.json",
        ),
    ),
    ModelSpec(
        key=MODEL_PARAKEET,
        hf_repo="nvidia/parakeet-tdt-0.6b-v3",
        role=ROLE_EN,
        env="nvidia",
        description="NVIDIA Parakeet TDT 0.6B v3 — English (Open ASR #1)",
        approx_size_mb=2500,
        files=(
            "model.safetensors",
            "config.json",
            "generation_config.json",
            "processor_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
        ),
    ),
    ModelSpec(
        key=MODEL_NEMOTRON,
        hf_repo="nvidia/nemotron-3.5-asr-streaming-0.6b",
        role=ROLE_MULTI,
        env="nvidia",
        description="NVIDIA Nemotron 3.5 ASR Streaming 0.6B — 40 languages",
        approx_size_mb=2600,
        files=(
            "model.safetensors",
            "config.json",
            "generation_config.json",
            "processor_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
        ),
    ),
)


# ── registry lookups ─────────────────────────────────────────────────────


def known_models() -> tuple[ModelSpec, ...]:
    return _REGISTRY


def get_model(key: str) -> ModelSpec:
    for spec in _REGISTRY:
        if spec.key == key:
            return spec
    valid = ", ".join(m.key for m in _REGISTRY)
    raise LocalCaptionError(
        f"Unknown model: {key!r}\n"
        f"Run `localcaption model list` to see the supported models.\n"
        f"Valid keys: {valid}"
    )


def by_role(role: str) -> ModelSpec:
    for spec in _REGISTRY:
        if spec.role == role:
            return spec
    raise LocalCaptionError(f"No model registered for role {role!r}")


# ── disk introspection ───────────────────────────────────────────────────


def _file_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    size = path.stat().st_size
    if path.name in _LARGE_FILES:
        return size > 1_000_000
    return size > 0


def missing_files(key: str) -> list[str]:
    spec = get_model(key)
    return [rel for rel in spec.files if not _file_ok(spec.local_dir / rel)]


def is_installed(key: str) -> bool:
    return not missing_files(key)


def missing_models(keys: list[str] | None = None) -> list[str]:
    check = keys if keys is not None else [m.key for m in _REGISTRY]
    return [k for k in check if not is_installed(k)]


def require(keys: list[str] | None = None) -> None:
    """Raise a copy-pasteable error if any required model is incomplete."""
    missing = missing_models(keys)
    if not missing:
        return
    lines = ["Missing or incomplete model checkpoints:"]
    for key in missing:
        files = missing_files(key)
        lines.append(f"  - {key}: missing {', '.join(files)}")
    lines.append("")
    lines.append("Download them with:  localcaption model download " + missing[0])
    lines.append("Or download everything:  localcaption model download --all")
    raise DependencyError("\n".join(lines))


@dataclass(frozen=True)
class ModelStatus:
    spec: ModelSpec
    installed: bool
    missing: tuple[str, ...]


def list_status() -> list[ModelStatus]:
    return [
        ModelStatus(spec=spec, installed=is_installed(spec.key),
                    missing=tuple(missing_files(spec.key)))
        for spec in _REGISTRY
    ]


# ── download / removal ───────────────────────────────────────────────────


def _run_curl(url: str, dest: Path) -> None:
    """Resumable, proxy-routed download of a single file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    if shutil.which("curl") is None:
        raise DependencyError("curl is required to download models but was not found.")
    cmd = [
        "curl", "-fL", "--retry", "8", "--retry-delay", "4", "--retry-all-errors",
        "-C", "-", "--proxy", get_proxy(), "--connect-timeout", "30",
        "-o", str(tmp), url,
    ]
    log.info(f"downloading {dest.name}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise DependencyError(
            f"Download failed for {url} (curl exit {exc.returncode})."
        ) from exc
    tmp.replace(dest)


def download_model(key: str, *, force: bool = False) -> Path:
    """Fetch every required file for *key* into its local directory."""
    spec = get_model(key)
    for rel in spec.files:
        dest = spec.local_dir / rel
        if _file_ok(dest) and not force:
            continue
        _run_curl(f"{spec.url_base}/{rel}", dest)
    return spec.local_dir


def download_all(*, force: bool = False) -> list[Path]:
    return [download_model(spec.key, force=force) for spec in _REGISTRY]


def remove_model(key: str) -> Path:
    spec = get_model(key)
    root = spec.local_dir
    if not root.exists():
        raise LocalCaptionError(f"Model {key!r} is not installed at {root}")
    shutil.rmtree(root)
    return root
