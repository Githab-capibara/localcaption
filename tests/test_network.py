"""Tests for the proxy / network policy."""

from __future__ import annotations

from localcaption import network


def test_get_proxy_default(monkeypatch) -> None:
    monkeypatch.delenv("LOCALCAPTION_PROXY", raising=False)
    assert network.get_proxy() == "socks5h://127.0.0.1:9050"


def test_get_proxy_override(monkeypatch) -> None:
    monkeypatch.setenv("LOCALCAPTION_PROXY", "socks5://10.0.0.1:1080")
    assert network.get_proxy() == "socks5://10.0.0.1:1080"


def test_proxy_env_sets_all_spellings(monkeypatch) -> None:
    monkeypatch.setenv("LOCALCAPTION_PROXY", "socks5h://127.0.0.1:9050")
    env = network.proxy_env({"PATH": "/bin"})
    for key in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY"):
        assert env[key] == "socks5h://127.0.0.1:9050"
        assert env[key.lower()] == "socks5h://127.0.0.1:9050"
    assert env["PATH"] == "/bin"


def test_proxy_env_excludes_loopback() -> None:
    env = network.proxy_env({"NO_PROXY": "example.com"})
    parts = env["NO_PROXY"].split(",")
    assert "example.com" in parts
    assert "localhost" in parts
    assert "127.0.0.1" in parts


def test_runner_env_forces_offline(monkeypatch) -> None:
    env = network.runner_env({})
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["ALL_PROXY"] == network.get_proxy()
