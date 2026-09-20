"""Tests for the `localcaption doctor` command and top-level dispatcher."""

from __future__ import annotations

import pytest

from localcaption.cli import main


def test_top_level_help_no_args(capsys) -> None:
    rc = main([])
    assert rc == 2  # bare invocation should be a non-zero exit
    out = capsys.readouterr().out
    assert "doctor" in out
    assert "transcribe" in out


def test_help_alias_zero_exit(capsys) -> None:
    rc = main(["help"])
    assert rc == 0
    assert "doctor" in capsys.readouterr().out


def test_doctor_runs_without_install(capsys) -> None:
    """`localcaption doctor` must produce a report even if nothing is installed."""
    rc = main(["doctor"])
    out = capsys.readouterr().out
    assert "localcaption" in out
    assert "System tools" in out
    assert "Model runtimes" in out
    assert "Models" in out
    # Isolated test dirs have no models/runtimes → non-zero exit.
    assert rc == 1


def test_doctor_does_not_invoke_installer_without_fix(monkeypatch, capsys) -> None:
    """Plain `doctor` must remain read-only. Load-bearing safety guarantee."""
    def explode(*_a, **_kw):
        raise AssertionError("installer must not be invoked without --fix")

    monkeypatch.setattr("localcaption.installer.install_system_dep", explode)
    monkeypatch.setattr("localcaption.installer.ensure_runtime", explode)
    monkeypatch.setattr("localcaption.models.download_all", explode)

    rc = main(["doctor"])
    assert rc == 1  # gaps detected, but no installs attempted


def test_doctor_fix_drives_installer(monkeypatch, capsys) -> None:
    calls: dict[str, int] = {"runtime": 0, "models": 0}

    monkeypatch.setattr("localcaption.installer.install_system_dep", lambda _name: None)
    monkeypatch.setattr(
        "localcaption.installer.ensure_runtime",
        lambda: calls.__setitem__("runtime", calls["runtime"] + 1),
    )
    monkeypatch.setattr(
        "localcaption.models.download_all",
        lambda **_kw: calls.__setitem__("models", calls["models"] + 1) or [],
    )

    rc = main(["doctor", "--fix"])
    out = capsys.readouterr().out
    del rc  # final rc depends on host env; we assert the fix path ran
    assert calls["runtime"] == 1
    assert calls["models"] == 1
    assert "runtimes" in out.lower()


def test_doctor_fix_aborts_when_install_step_fails(monkeypatch, capsys) -> None:
    from localcaption.errors import InstallError

    def boom() -> None:
        raise InstallError("simulated runtime failure")

    monkeypatch.setattr("localcaption.installer.install_system_dep", lambda _name: None)
    monkeypatch.setattr("localcaption.installer.ensure_runtime", boom)
    monkeypatch.setattr(
        "localcaption.models.download_all",
        lambda **_kw: pytest.fail("download must not be reached"),
    )

    rc = main(["doctor", "--fix"])
    out = capsys.readouterr().out
    assert "simulated runtime failure" in out
    assert "Fix aborted" in out
    assert rc == 1


def test_doctor_help_advertises_fix_flag(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["doctor", "--help"])
    out = capsys.readouterr().out
    assert "--fix" in out


def test_unknown_subcommand_treated_as_url(monkeypatch) -> None:
    """Non-subcommand first args fall through to transcribe."""
    sentinel: dict[str, str] = {}

    def fake(url, **kw):
        sentinel["url"] = url
        raise SystemExit(0)

    monkeypatch.setattr("localcaption.cli.transcribe_url", fake)
    monkeypatch.setattr("localcaption.cli._ensure_models", lambda *_a, **_k: True)
    with pytest.raises(SystemExit):
        main(["https://example.com/video"])
    assert sentinel["url"] == "https://example.com/video"
