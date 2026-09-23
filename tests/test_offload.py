"""Tests for the GPU/CPU offload helpers shared by the model runners.

These live in ``src/localcaption/runners/_offload.py`` and are imported by the
per-model runner scripts. The helpers are pure functions of (free VRAM,
checkpoint size -> device decision), so we can unit-test the decision logic
without a GPU by patching ``free_vram_bytes`` / ``model_weight_bytes``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_RUNNERS = _REPO / "src" / "localcaption" / "runners"


def _load_offload():
    """Import the offload helpers without pulling the runners' ML deps.

    ``_offload`` only uses the stdlib at module top-level (torch is imported
    lazily inside ``free_vram_bytes``), so we can exec the whole module in a
    stub namespace and patch the two probe functions per test.
    """
    import types

    src = (_RUNNERS / "_offload.py").read_text(encoding="utf-8")
    mod = types.ModuleType("_offload_stub")
    mod.__dict__["__builtins__"] = __builtins__
    exec(compile(src, str(_RUNNERS / "_offload.py"), "exec"), mod.__dict__)
    return mod


@pytest.fixture
def offload():
    return _load_offload()


def _plan(offload, free_mb, weight_mb):
    """Compute an offload plan for the given free VRAM / checkpoint size."""
    mod = offload
    mod.free_vram_bytes = lambda: int(free_mb * 1024**2)
    mod.model_weight_bytes = lambda _dir: int(weight_mb * 1024**2)
    return mod.offload_kwargs("dummy")


class TestOffloadDecision:
    """The three-tier decision: whole-GPU, partial split, whole-CPU."""

    def test_fits_whole_gpu(self, offload):
        # free 4GB, checkpoint 1.8GB -> entire model on the GPU.
        plan = _plan(offload, free_mb=4096, weight_mb=1789)
        assert plan == {"device_map": "cuda:0"}

    def test_partial_split_when_gpu_cannot_hold_all(self, offload):
        # free 1GB, checkpoint 1.8GB -> split: 80% of free bytes on GPU (headroom
        # for caching_allocator_warmup), overflow on CPU.
        plan = _plan(offload, free_mb=1024, weight_mb=1789)
        assert plan["device_map"] == "auto"
        # 80% of free bytes (not 80% of MiB) -> int(1024 * 1024**2 * 0.8)
        assert plan["max_memory"][0] == int(1024 * 0.8 * 1024**2)
        assert plan["max_memory"]["cpu"] >= 100 * 1024**3

    def test_zero_free_vram_runs_on_cpu(self, offload):
        # No CUDA -> whole model on the host.
        plan = _plan(offload, free_mb=0, weight_mb=1789)
        assert plan == {"device_map": "cpu"}

    def test_unknown_checkpoint_size_still_splis(self, offload):
        # Checkpoint size unknown (0): fall back to free-VRAM alone. A small
        # free budget still yields a partial split rather than a hard CPU.
        plan = _plan(offload, free_mb=512, weight_mb=0)
        assert plan["device_map"] == "auto"
        assert plan["max_memory"][0] == int(512 * 0.8 * 1024**2)  # 80% headroom


class TestNoCrossModelFallback:
    """A failing/oversized model must be offloaded to CPU, never swapped for a
    different ASR model. The qwen runner must not contain any model-swapping
    token (e.g. 'nemotron', 'parakeet', 'fallback model')."""

    def test_qwen_runner_has_no_model_swap(self):
        src = (_RUNNERS / "qwen.py").read_text(encoding="utf-8")
        low = src.lower()
        for bad in ("nemotron", "parakeet"):
            assert bad not in low, f"qwen.py must not swap to another model ({bad})"

    def test_qwen_runner_offloads_to_cpu(self):
        src = (_RUNNERS / "qwen.py").read_text(encoding="utf-8")
        assert "offload_kwargs" in src, "qwen.py must use the shared offload helper"
        assert "device_map" in src, "qwen.py must fall back to a CPU device_map"

    def test_pipeline_has_no_fallback_model_swap(self):
        src = (_REPO / "src" / "localcaption" / "pipeline.py").read_text(encoding="utf-8")
        assert "_transcribe_with_fallback" not in src, (
            "pipeline.py must not swap to a different model on OOM"
        )


def test_runners_use_the_shared_helpers():
    for name in ("nvidia.py", "qwen.py", "langid.py"):
        src = (_RUNNERS / name).read_text(encoding="utf-8")
        assert "offload_kwargs" in src, f"{name} must import offload_kwargs from _offload"
