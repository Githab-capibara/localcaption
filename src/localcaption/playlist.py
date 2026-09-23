"""Playlist expansion.

YouTube (and other ``yt-dlp`` sites) URLs can carry a playlist id:
``https://www.youtube.com/watch?v=ID&list=PL...``. The pipeline's
downloader uses ``noplaylist=True`` for predictable single-file output,
so the rest of the list is silently dropped. This module detects that
situation up front and lets the caller expand the list to individual
video URLs via ``yt-dlp --flat-playlist``.

The expansion is a metadata-only round-trip (no download), so it is fast
even over a Tor proxy.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from . import _logging as log
from .network import get_proxy


@dataclass(frozen=True)
class PlaylistInfo:
    """Result of expanding one URL."""

    playlist_id: str
    title: str | None
    entry_count: int
    urls: list[str]


class PlaylistError(Exception):
    """Raised when playlist expansion fails."""


def has_playlist_query(url: str) -> bool:
    """Return True when *url* carries a ``list=`` (or ``playlist=``) query param."""
    if "://" not in url:
        return False
    query = parse_qs(urlparse(url).query)
    return bool(query.get("list") or query.get("playlist"))


def playlist_query_id(url: str) -> str | None:
    """Return the playlist id from the query string, or None."""
    if "://" not in url:
        return None
    query = parse_qs(urlparse(url).query)
    return (query.get("list") or query.get("playlist") or [None])[0]


def _resolved_proxy(proxy: str | None) -> str:
    if proxy is not None:
        return proxy
    return os.environ.get("LOCALCAPTION_PROXY", "").strip() or get_proxy()


def _apply_cookies(opts: dict, cookies: str | None) -> None:
    """Set ``cookiefile``/``cookiejar`` on *opts* from *cookies*.

    A real file path uses ``cookiefile``; a browser name (or auto-detected
    source) loads the jar in-memory so we don't dump a Netscape file into
    the current working directory. Mirrors the logic in download.py.
    """
    if cookies is None:
        from .network import get_ytdlp_cookies

        cookies = get_ytdlp_cookies()
    if not cookies:
        return
    # A browser name must be passed to yt-dlp's extract_cookies_from_browser,
    # NOT cookiefile. cookiefile=<browser> silently dumps a Netscape jar into
    # the CWD (the bug we are fixing) and a leaked jar of that name then
    # breaks os.path.isfile, so we dispatch on whether the value is a known
    # browser name rather than probing the filesystem.
    from yt_dlp.cookies import extract_cookies_from_browser

    known_browsers = {
        "chrome", "chromium", "edge", "firefox", "brave", "bravebrowser",
        "vivaldi", "opera", "safari", "konqueror", "ie", "silk",
    }
    # A bare browser name (no slash, no extension) routes to
    # extract_cookies_from_browser. A value with a path separator or a file
    # extension is a file path — even if its basename matches a browser name
    # (e.g. "./firefox.txt").
    has_path_sep = any(sep in cookies for sep in ("/", os.sep))
    has_extension = os.path.splitext(cookies)[1] != ""
    if cookies.lower() in known_browsers and not has_path_sep and not has_extension:
        try:
            jar = extract_cookies_from_browser(cookies)
        except Exception:
            return
        if jar:
            opts["cookiejar"] = jar
        return
    # Otherwise treat it as a file path.
    opts["cookiefile"] = os.path.expanduser(cookies)


def expand_playlist(
    url: str,
    *,
    proxy: str | None = None,
    cookies: str | None = None,
) -> PlaylistInfo:
    """Expand a playlist URL to its individual video URLs.

    Uses ``yt-dlp`` flat-playlist metadata extraction (no audio fetched),
    so it is fast even over a Tor proxy. Raises ``PlaylistError`` on
    failure (bad proxy, empty list, …).
    """
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - defensive
        from .errors import DependencyError

        raise DependencyError("yt-dlp is required to expand playlists") from exc

    resolved_proxy = _resolved_proxy(proxy)
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        # extract_flat='in_playlist' is the key: it returns one entry per
        # video *without* hitting each individual video's player API. That
        # avoids the per-video bot-check that `flat_playlist=True` would
        # otherwise trigger on every entry.
        "extract_flat": "in_playlist",
        "skip_download": True,
        "ignoreerrors": False,
        "logger": _DummyLogger(),
        "outtmpl": "%(playlist_index)s\t%(id)s\t%(title)s\t%(webpage_url)s",
    }
    if resolved_proxy:
        opts["proxy"] = resolved_proxy
    _apply_cookies(opts, cookies)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise PlaylistError(f"failed to expand playlist {url!r}: {exc}") from exc

    entries = info.get("entries") if isinstance(info, dict) else None
    if entries is None:
        raise PlaylistError(f"URL is not a playlist (no entries returned): {url}")
    urls: list[str] = []
    for entry in entries:
        if entry is None:
            continue
        entry_url = entry.get("webpage_url") or entry.get("url") or entry.get("original_url")
        if entry_url:
            urls.append(str(entry_url))
    if not urls:
        raise PlaylistError(f"playlist {url} resolved to zero videos")
    title = info.get("title")
    log.info(f"playlist: {len(urls)} videos" + (f" ({title})" if title else ""))
    return PlaylistInfo(
        playlist_id=playlist_query_id(url) or info.get("id", "") or "",
        title=title,
        entry_count=len(urls),
        urls=urls,
    )


class _DummyLogger:
    """Silent yt-dlp logger for metadata-only extraction."""

    def debug(self, msg: object) -> None:
        pass

    def info(self, msg: object) -> None:
        pass

    def warning(self, msg: object) -> None:
        pass

    def error(self, msg: object) -> None:
        pass


__all__ = [
    "PlaylistError",
    "PlaylistInfo",
    "expand_playlist",
    "has_playlist_query",
    "playlist_query_id",
]
