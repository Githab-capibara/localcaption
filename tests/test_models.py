"""Tests for ``localcaption.models`` — registry, listing, installation checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from localcaption import models
from localcaption.errors import LocalCaptionError

# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────


def test_registry_has_the_four_models():
    keys = {m.key for m in models.known_models()}
    assert keys == {
        "langid-ecapa",
        "qwen3-asr-0.6b",
        "parakeet-tdt-0.6b-v3",
        "nemotron-3.5-asr-streaming-0.6b",
    }


def test_registry_roles_and_envs():
    by_role = {m.role: m for m in models.known_models()}
    assert by_role["language-id"].env == "langid"
    assert by_role["russian"].env == "qwen"
    assert by_role["english"].env == "nvidia"
    assert by_role["multilingual"].env == "nvidia"


def test_get_model_returns_spec():
    spec = models.get_model("parakeet-tdt-0.6b-v3")
    assert spec.hf_repo == "nvidia/parakeet-tdt-0.6b-v3"
    assert spec.url_base.endswith("/nvidia/parakeet-tdt-0.6b-v3/resolve/main")
    assert "model.safetensors" in spec.files


def test_get_model_raises_on_unknown():
    with pytest.raises(LocalCaptionError) as exc_info:
        models.get_model("not-a-model")
    msg = str(exc_info.value)
    assert "Unknown model" in msg
    assert "model list" in msg


def test_by_role_lookup():
    assert models.by_role("russian").key == "qwen3-asr-0.6b"
    with pytest.raises(LocalCaptionError):
        models.by_role("klingon")


# ──────────────────────────────────────────────────────────────────────
# Disk introspection
# ──────────────────────────────────────────────────────────────────────


def _install(root: Path, key: str) -> None:
    spec = models.get_model(key)
    for rel in spec.files:
        target = root / key / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # Large files need >1 MB to count as complete; small configs just >0.
        target.write_bytes(b"\0" * (2_000_000 if rel == "model.safetensors" else 8))


def test_missing_files_when_absent():
    assert models.missing_files("langid-ecapa")
    assert not models.is_installed("langid-ecapa")


def test_installed_when_all_files_present():
    _install(models.paths.models_root(), "langid-ecapa")
    assert models.is_installed("langid-ecapa")


def test_tiny_safetensors_counts_as_missing():
    root = models.paths.models_root()
    spec = models.get_model("qwen3-asr-0.6b")
    for rel in spec.files:
        target = root / spec.key / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\0" * 32)
    assert "model.safetensors" in models.missing_files("qwen3-asr-0.6b")


def test_missing_models_and_require():
    only_langid = models.paths.models_root()
    _install(only_langid, "langid-ecapa")
    assert models.missing_models(["langid-ecapa"]) == []
    missing = models.missing_models(["langid-ecapa", "qwen3-asr-0.6b"])
    assert missing == ["qwen3-asr-0.6b"]
    with pytest.raises(LocalCaptionError, match="qwen3-asr-0.6b"):
        models.require(["qwen3-asr-0.6b"])


def test_list_status_marks_installed():
    _install(models.paths.models_root(), "langid-ecapa")
    rows = {r.spec.key: r for r in models.list_status()}
    assert rows["langid-ecapa"].installed is True
    assert rows["qwen3-asr-0.6b"].installed is False


# ──────────────────────────────────────────────────────────────────────
# Removal
# ──────────────────────────────────────────────────────────────────────


def test_remove_model_deletes_directory():
    _install(models.paths.models_root(), "langid-ecapa")
    assert models.is_installed("langid-ecapa")
    removed = models.remove_model("langid-ecapa")
    assert removed == models.get_model("langid-ecapa").local_dir
    assert not removed.exists()


def test_remove_model_raises_when_missing():
    with pytest.raises(LocalCaptionError, match="not installed"):
        models.remove_model("langid-ecapa")
