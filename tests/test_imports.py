"""Smoke tests: the package imports cleanly and exposes the expected public API."""

from __future__ import annotations

import importlib


def test_package_imports() -> None:
    mod = importlib.import_module("localcaption")
    assert hasattr(mod, "__version__")
    assert isinstance(mod.__version__, str)


def test_cli_help_does_not_crash(capsys) -> None:
    import pytest

    from localcaption.cli import main

    # argparse exits with SystemExit(0) on --help; we just want it not to blow up.
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0

    captured = capsys.readouterr()
    assert "localcaption" in captured.out


def test_pipeline_public_surface() -> None:
    from localcaption.pipeline import PipelineResult, transcribe_url

    assert callable(transcribe_url)
    assert PipelineResult.__dataclass_fields__.keys() >= {
        "source_url", "audio_path", "wav_path", "transcripts", "summary",
    }


def test_new_stage_modules_import() -> None:
    for name in (
        "localcaption.asr",
        "localcaption.audio",
        "localcaption.formats",
        "localcaption.langid",
        "localcaption.languages",
        "localcaption.models",
        "localcaption.network",
        "localcaption.paths",
        "localcaption.runtime",
    ):
        assert importlib.import_module(name) is not None


def test_legacy_modules_are_gone() -> None:
    import pytest

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("localcaption.whisper")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("localcaption.backends")


def test_asr_runners_target_cuda() -> None:
    """Every ASR runner must use the GPU when VRAM allows, and offload to CPU
    when it doesn't (never hard-fail on a small or busy GPU).

    The decision is centralised in ``_offload.offload_kwargs``; each runner
    just calls it and merges the returned ``device_map``/``max_memory`` into
    its ``from_pretrained``/``pipeline`` call. The test therefore checks that
    every runner imports and calls the shared helper, and that the helper
    itself emits both a GPU (``cuda:0``) and a CPU placement option.
    """
    from pathlib import Path

    runners_dir = Path(__file__).resolve().parents[1] / "src" / "localcaption" / "runners"
    # every runner must reach for the shared offload helper
    for name in ("nvidia.py", "qwen.py", "langid.py"):
        src = (runners_dir / name).read_text(encoding="utf-8")
        assert "offload_kwargs" in src, f"{name} must import offload_kwargs from _offload"
        assert "device_map" in src, f"{name} must apply a device_map"

    # the helper must be able to place on the GPU *and* on CPU
    off = (runners_dir / "_offload.py").read_text(encoding="utf-8")
    assert "cuda:0" in off, "_offload must be able to target the GPU"
    assert '"cpu"' in off, "_offload must be able to target CPU"
