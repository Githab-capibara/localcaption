"""Tests for playlist expansion.

A URL with ``&list=`` carries a playlist. The downloader uses
``noplaylist=True``, so without detection the rest of the list is silently
dropped. These tests cover the pure-URL helpers (no network) and the
expansion stub (no yt-dlp round-trip).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from localcaption.playlist import (
    PlaylistError,
    expand_playlist,
    has_playlist_query,
    playlist_query_id,
)

# ---------------------------------------------------------------------------
# Pure URL helpers (no network)
# ---------------------------------------------------------------------------

def test_has_playlist_query_detects_list() -> None:
    assert has_playlist_query(
        "https://www.youtube.com/watch?v=Be4x5IPo9Ic&list=PLBP4Q3FNSLK3dd-3lHjPij-dMSgNskoF6"
    )
    assert has_playlist_query("https://www.youtube.com/playlist?list=PL123")


def test_has_playlist_query_false_for_plain_url() -> None:
    assert not has_playlist_query("https://www.youtube.com/watch?v=Be4x5IPo9Ic")
    assert not has_playlist_query("file.mp4")
    assert not has_playlist_query("/tmp/video.mp4")


def test_has_playlist_query_local_files_never_playlist() -> None:
    # Local paths should never be treated as playlists even if they look odd.
    assert not has_playlist_query("C:\\list=foo.mp4")


def test_playlist_query_id_extracts_id() -> None:
    assert (
        playlist_query_id(
            "https://www.youtube.com/watch?v=Be4x5IPo9Ic&list=PLBP4Q3FNSLK3dd-3lHjPij-dMSgNskoF6"
        )
        == "PLBP4Q3FNSLK3dd-3lHjPij-dMSgNskoF6"
    )
    assert playlist_query_id("https://www.youtube.com/playlist?list=PLabc") == "PLabc"
    assert playlist_query_id("https://www.youtube.com/watch?v=x") is None
    assert playlist_query_id("file.mp4") is None


def test_has_playlist_query_playlist_param() -> None:
    # Some sites use `playlist=` instead of `list=`.
    assert has_playlist_query("https://example.com/watch?v=x&playlist=PL123")
    assert playlist_query_id("https://example.com/watch?v=x&playlist=PL123") == "PL123"


# ---------------------------------------------------------------------------
# expand_playlist with a stubbed yt-dlp (no network)
# ---------------------------------------------------------------------------

def _fake_playlist_ydl(monkeypatch, entries: list[dict], captured: dict | None = None,
                       playlist_type: str = "playlist") -> None:
    """Patch yt_dlp.YoutubeDL so extract_info returns a fake playlist.

    Also sets ``yt_dlp.cookies`` as an attribute on the fake yt_dlp module so
    ``from yt_dlp.cookies import extract_cookies_from_browser`` inside
    ``_apply_cookies`` resolves correctly.
    """
    import sys
    import types

    class _YDL:
        def __init__(self, opts):
            if captured is not None:
                captured.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def extract_info(self, url, download):
            assert download is False
            return {
                "_type": playlist_type,
                "title": "fake",
                "id": "PLFAKE",
                "entries": entries,
            }

    mod = types.ModuleType("yt_dlp")
    mod.YoutubeDL = _YDL
    # Provide a cookies sub-module so `from yt_dlp.cookies import ...` works.
    cookies_mod = types.ModuleType("yt_dlp.cookies")
    cookies_mod.extract_cookies_from_browser = lambda _n: None
    mod.cookies = cookies_mod
    monkeypatch.setitem(sys.modules, "yt_dlp", mod)
    monkeypatch.setitem(sys.modules, "yt_dlp.cookies", cookies_mod)


def test_expand_playlist_returns_all_entries(monkeypatch) -> None:
    entries = [
        {"id": "vid1", "webpage_url": "https://www.youtube.com/watch?v=vid1"},
        {"id": "vid2", "webpage_url": "https://www.youtube.com/watch?v=vid2"},
    ]
    _fake_playlist_ydl(monkeypatch, entries)
    info = expand_playlist(
        "https://www.youtube.com/watch?v=vid1&list=PLFAKE", proxy=""
    )
    assert info.entry_count == 2
    assert info.playlist_id == "PLFAKE"
    assert info.urls == [
        "https://www.youtube.com/watch?v=vid1",
        "https://www.youtube.com/watch?v=vid2",
    ]


def test_expand_playlist_not_a_playlist_raises(monkeypatch) -> None:
    _fake_playlist_ydl(monkeypatch, [], playlist_type="video")
    # Simulate extract_info returning a non-playlist (no entries key).
    import sys
    import types

    class _YDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def extract_info(self, url, download):
            return {"_type": "video", "title": "single", "id": "vid1"}

    mod = types.ModuleType("yt_dlp")
    mod.YoutubeDL = _YDL
    monkeypatch.setitem(sys.modules, "yt_dlp", mod)
    with pytest.raises(PlaylistError, match="not a playlist"):
        expand_playlist("https://www.youtube.com/watch?v=vid1", proxy="")


def test_expand_playlist_empty_entries_raises(monkeypatch) -> None:
    _fake_playlist_ydl(monkeypatch, [])
    with pytest.raises(PlaylistError, match="zero videos"):
        expand_playlist("https://www.youtube.com/watch?v=x&list=PL", proxy="")


def test_expand_playlist_passes_proxy_and_cookies(monkeypatch, tmp_path: Path) -> None:
    """A real cookie file path is passed via ``cookiefile``; extract_flat is set."""
    jar_file = tmp_path / "cookies.txt"
    jar_file.write_text("# Netscape cookie file\n")

    captured: dict = {}
    _fake_playlist_ydl(monkeypatch, [{"webpage_url": "https://x/watch?v=v1"}], captured)

    expand_playlist(
        "https://www.youtube.com/watch?v=v1&list=PL1",
        proxy="socks5h://10.0.0.1:1080",
        cookies=str(jar_file),
    )
    assert captured.get("proxy") == "socks5h://10.0.0.1:1080"
    assert captured.get("cookiefile") == str(jar_file)
    assert captured.get("extract_flat") == "in_playlist"


def test_expand_playlist_auto_detects_cookies(monkeypatch, tmp_path: Path) -> None:
    """When cookies=None, get_ytdlp_cookies is consulted and its file path used."""
    jar_file = tmp_path / "auto-cookies.txt"
    jar_file.write_text("# Netscape cookie file\n")
    captured: dict = {}
    _fake_playlist_ydl(monkeypatch, [{"webpage_url": "https://x/watch?v=v1"}], captured)
    monkeypatch.setattr(
        "localcaption.network.get_ytdlp_cookies",
        lambda: str(jar_file),
    )
    monkeypatch.setenv("LOCALCAPTION_PROXY", "")

    expand_playlist("https://www.youtube.com/watch?v=v1&list=PL1", proxy="")
    assert captured.get("cookiefile") == str(jar_file)


def test_expand_playlist_browser_name_uses_cookiejar(monkeypatch, tmp_path: Path) -> None:
    """A browser name (not a file) must load the jar in-memory."""
    captured: dict = {}
    _fake_playlist_ydl(monkeypatch, [{"webpage_url": "https://x/watch?v=v1"}], captured)

    class _FakeJar:
        def __len__(self) -> int:
            return 1

    # Patch the cookies sub-module that _fake_playlist_ydl installed.
    monkeypatch.setattr(
        "yt_dlp.cookies.extract_cookies_from_browser",
        lambda _n: _FakeJar(),
    )

    monkeypatch.setenv("LOCALCAPTION_PROXY", "")
    expand_playlist(
        "https://www.youtube.com/watch?v=v1&list=PL1",
        proxy="",
        cookies="firefox",
    )
    assert "cookiejar" in captured
    assert "cookiefile" not in captured
