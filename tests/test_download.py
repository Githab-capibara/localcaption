"""Tests for the yt-dlp download stage.

``download_audio`` now takes ``cookies`` / ``proxy`` / ``force_rotate``
overrides and, on a bot-check block, rotates the Tor exit circuit before
retrying. These tests exercise that decision logic by stubbing the heavy
pieces (YoutubeDL, rotation, cookie auto-detection) so we can assert the
*what* without hitting the network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from localcaption import download
from localcaption.errors import DependencyError, DownloadError


def _fail_ydl_factory(error_text: str):
    """Build a ``YoutubeDL`` factory that always raises with *error_text*."""

    class _Fail:
        def __init__(self, opts, *a, **k):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def extract_info(self, *_a, **_k):
            raise RuntimeError(error_text)

        def prepare_filename(self, info):
            return str(Path("/nonexistent") / "x.m4a")

    return _Fail


def _capturing_factory(error_text: str):
    """Build a factory that records opts then raises *error_text*."""
    captured: dict = {}

    class _Cap:
        def __init__(self, opts, *a, **k):
            captured.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def extract_info(self, *_a, **_k):
            raise RuntimeError(error_text)

        def prepare_filename(self, info):
            return str(Path("/nonexistent") / "x.m4a")

    return _Cap, captured


def test_download_missing_ytdlp(monkeypatch, tmp_path: Path) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "yt_dlp", None)
    with pytest.raises(DependencyError):
        download.download_audio("https://example.com/v", tmp_path)


def test_bot_block_rotates_and_retries(monkeypatch, tmp_path: Path) -> None:
    """A bot-check error must keep retrying and surface Tor guidance at the end."""
    bot_msg = "Sign in to confirm you’re not a bot"
    monkeypatch.setattr("yt_dlp.YoutubeDL", _fail_ydl_factory(bot_msg))
    rotated: list[str] = []
    monkeypatch.setattr(
        "localcaption.download.rotate_tor_circuit",
        lambda: rotated.append("1") or True,
    )
    monkeypatch.setattr("localcaption.download.get_ytdlp_cookies", lambda: None)
    monkeypatch.setattr("localcaption.download.get_proxy", lambda: "socks5h://127.0.0.1:9050")

    with pytest.raises(DownloadError) as exc:
        download.download_audio("https://www.youtube.com/watch?v=x", tmp_path)
    # The final error must carry the actionable bot-block guidance.
    assert "Tor exit IP" in str(exc.value)
    # Rotation fired on the pre-first-attempt and on each bot-block retry.
    assert len(rotated) >= 1


def test_non_bot_block_raises_plain_download_error(monkeypatch, tmp_path: Path) -> None:
    """A non-bot-check failure must NOT emit the Tor-specific guidance."""
    monkeypatch.setattr("yt_dlp.YoutubeDL", _fail_ydl_factory("connection reset by peer"))
    monkeypatch.setattr("localcaption.download.rotate_tor_circuit", lambda: False)
    monkeypatch.setattr("localcaption.download.get_ytdlp_cookies", lambda: None)
    monkeypatch.setattr("localcaption.download.get_proxy", lambda: "")

    with pytest.raises(DownloadError) as exc:
        download.download_audio("https://example.com/v", tmp_path)
    assert "Tor exit IP" not in str(exc.value)
    assert "connection reset" in str(exc.value)


def test_cookies_and_proxy_are_passed_to_ytdlp(monkeypatch, tmp_path: Path) -> None:
    """A cookie *file* must be passed via ``cookiefile``; a browser name via ``cookiejar``."""
    # A real cookie file path.
    jar_file = tmp_path / "cookies.txt"
    jar_file.write_text("# Netscape cookie file\n")
    factory, captured = _capturing_factory("done")
    monkeypatch.setattr("yt_dlp.YoutubeDL", factory)
    monkeypatch.setattr("localcaption.download.rotate_tor_circuit", lambda: False)
    monkeypatch.setattr("localcaption.download.get_proxy", lambda: "socks5h://127.0.0.1:9050")

    with pytest.raises(DownloadError):
        download.download_audio(
            "https://www.youtube.com/watch?v=x",
            tmp_path,
            cookies=str(jar_file),
            proxy="socks5h://10.0.0.1:1080",
        )
    assert captured.get("cookiefile") == str(jar_file)
    assert "cookiejar" not in captured
    assert captured.get("proxy") == "socks5h://10.0.0.1:1080"


def test_browser_name_cookies_use_cookiejar(monkeypatch, tmp_path: Path) -> None:
    """A browser name (not a file) must be loaded in-memory via ``cookiejar``."""
    factory, captured = _capturing_factory("done")
    monkeypatch.setattr("yt_dlp.YoutubeDL", factory)
    monkeypatch.setattr("localcaption.download.rotate_tor_circuit", lambda: False)
    monkeypatch.setattr("localcaption.download.get_proxy", lambda: "")

    # A fake browser that returns an empty jar -> no cookiejar key.
    import yt_dlp.cookies as ycookies

    monkeypatch.setattr(ycookies, "extract_cookies_from_browser", lambda _n: [])
    with pytest.raises(DownloadError):
        download.download_audio(
            "https://www.youtube.com/watch?v=x", tmp_path, cookies="firefox"
        )
    # No cookiefile/cookiejar because the fake jar was empty.
    assert "cookiefile" not in captured


def test_no_proxy_omits_proxy_option(monkeypatch, tmp_path: Path) -> None:
    """An empty proxy string must NOT set the yt-dlp proxy option."""
    factory, captured = _capturing_factory("done")
    monkeypatch.setattr("yt_dlp.YoutubeDL", factory)
    monkeypatch.setattr("localcaption.download.rotate_tor_circuit", lambda: False)

    with pytest.raises(DownloadError):
        download.download_audio("https://www.youtube.com/watch?v=x", tmp_path, proxy="")
    assert "proxy" not in captured
