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


# ---------------------------------------------------------------------------
# YouTube bot-check mitigations: cookie auto-detection + Tor circuit rotation
# ---------------------------------------------------------------------------

def test_get_ytdlp_cookies_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LOCALCAPTION_YTDLP_COOKIES", "/tmp/cookies.txt")
    assert network.get_ytdlp_cookies() == "/tmp/cookies.txt"


def test_get_ytdlp_cookies_default_file(monkeypatch) -> None:
    monkeypatch.delenv("LOCALCAPTION_YTDLP_COOKIES", raising=False)
    monkeypatch.setenv(
        "LOCALCAPTION_YTDLP_COOKIE_BROWSERS", "",
    )
    # No file, no browsers -> None when no browser is reachable.
    import yt_dlp.cookies as ycookies

    def _no_browser(_name):
        raise RuntimeError("no browser")

    monkeypatch.setattr(ycookies, "extract_cookies_from_browser", _no_browser)
    assert network.get_ytdlp_cookies() is None


def test_get_ytdlp_cookies_browser_fallback(monkeypatch) -> None:
    monkeypatch.delenv("LOCALCAPTION_YTDLP_COOKIES", raising=False)
    monkeypatch.setenv("LOCALCAPTION_YTDLP_COOKIE_BROWSERS", "firefox")
    import yt_dlp.cookies as ycookies

    class _FakeJar:
        def __len__(self) -> int:
            return 3

    monkeypatch.setattr(
        ycookies, "extract_cookies_from_browser", lambda _n: _FakeJar(),
    )
    assert network.get_ytdlp_cookies() == "firefox"


def test_parse_host_port() -> None:
    assert network._parse_host_port("socks5h://127.0.0.1:9050") == ("127.0.0.1", 9050)
    assert network._parse_host_port("http://host:8080") == ("host", 8080)
    assert network._parse_host_port("not-a-url") is None


def test_luoks_like_bot_block() -> None:
    assert network._looks_like_bot_block(
        "Sign in to confirm you’re not a bot"
    )
    assert network._looks_like_bot_block("HTTP 403 Forbidden")
    assert not network._looks_like_bot_block("connection refused")


def test_rotate_tor_circuit_no_proxy(monkeypatch) -> None:
    # A non-loopback proxy is not Tor; rotation must refuse to touch it.
    monkeypatch.setenv("LOCALCAPTION_PROXY", "http://8.8.8.8:3128")
    monkeypatch.delenv("LOCALCAPTION_TOR_CONTROL", raising=False)
    assert network.rotate_tor_circuit() is False


def test_rotate_tor_circuit_control_unreachable(monkeypatch) -> None:
    # Force the control-socket connection to fail so the graceful-False path
    # is exercised regardless of whether a real Tor is running on this box.
    import socket

    def _no_conn(*_a, **_k):
        raise OSError("no control port")

    monkeypatch.setenv("LOCALCAPTION_PROXY", "socks5h://127.0.0.1:9050")
    monkeypatch.delenv("LOCALCAPTION_TOR_CONTROL", raising=False)
    monkeypatch.setattr(socket, "create_connection", _no_conn)
    assert network.rotate_tor_circuit() is False
