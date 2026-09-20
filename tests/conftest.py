"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_localcaption_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Keep tests away from the real 7 GB models, runtimes, and search index."""
    monkeypatch.setenv("LOCALCAPTION_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("LOCALCAPTION_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LOCALCAPTION_INDEX_PATH", str(tmp_path / "index.jsonl"))
