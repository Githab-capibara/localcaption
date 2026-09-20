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
    """Every ASR runner must offload inference to the GPU, never regress to CPU."""
    from pathlib import Path

    runners_dir = Path(__file__).resolve().parents[1] / "src" / "localcaption" / "runners"
    checks = {
        "nvidia.py": ("device=\"cuda:0\"", ".to(\"cuda\")"),
        "qwen.py": ("device_map={\"\": \"cuda:0\"}",),
        "langid.py": ("run_opts={\"device\": \"cuda:0\"}",),
    }
    for name, needles in checks.items():
        src = (runners_dir / name).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in src, f"{name} missing GPU target: {needle}"
