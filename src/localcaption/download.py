"""Stage 1: download the best available audio stream with yt-dlp.

We use yt-dlp's Python API rather than the CLI so we can deterministically
discover the resulting filename via :py:meth:`YoutubeDL.prepare_filename`.
This avoids the fragility of parsing ``--print after_move:filepath`` output
across yt-dlp versions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _logging as log
from .errors import DependencyError, DownloadError
from .network import _looks_like_bot_block, get_proxy, get_ytdlp_cookies, rotate_tor_circuit

# YouTube periodically blocks specific player clients. The mobile clients
# tend to be the most stable for audio-only retrieval. Order matters: yt-dlp
# tries them left-to-right.
DEFAULT_PLAYER_CLIENTS: tuple[str, ...] = ("tv", "mweb", "android", "ios", "web")


@dataclass(frozen=True)
class DownloadResult:
    """Downloaded audio plus the yt-dlp info dict (chapters, title, ...)."""
    path: Path
    info: dict[str, Any]


def _client_attempts(clients: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Build a sequence of player-client lists for retrying a blocked download.

    The first attempt uses every requested client (in order). Each later
    attempt drops the client tried *first* on the previous attempt — the one
    most likely to be the one YouTube flagged — so a less-blocked client
    carries the stream next.
    """
    attempts: list[tuple[str, ...]] = []
    current = list(clients)
    while current:
        attempts.append(tuple(current))
        current = current[1:]
    return attempts


def download_audio(
    url: str,
    work_dir: Path,
    *,
    player_clients: tuple[str, ...] = DEFAULT_PLAYER_CLIENTS,
    cookies: str | None = None,
    proxy: str | None = None,
    force_rotate: bool = False,
) -> DownloadResult:
    """Download the best audio stream for *url* into *work_dir*.

    Returns the path plus the yt-dlp info dict. Raises :class:`DownloadError`
    if yt-dlp fails to produce a usable file.

    ``cookies`` (when given) overrides the auto-detected cookie source; ``proxy``
    (when given) overrides the configured proxy — ``""`` disables the proxy.
    ``force_rotate`` requests a fresh Tor exit circuit up front even when no
    block has been seen yet.
    """
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise DependencyError("yt-dlp is not installed (pip install yt-dlp)") from exc

    work_dir.mkdir(parents=True, exist_ok=True)
    proxy = get_proxy() if proxy is None else proxy
    cookies = cookies if cookies is not None else get_ytdlp_cookies()
    ydl_opts: dict[str, Any] = {
        # Opus audio-only streams are far smaller and more resilient to drop
        # and rate-limit than the m4a/MP4 bestaudio mux; fall back to any
        # audio, then to a full (video+audio) stream when audio alone is not
        # available.
        "format": "bestaudio[acodec=opus]/bestaudio/best",
        "outtmpl": str(work_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": False,
        "no_warnings": True,
        "restrictfilenames": True,
        "overwrites": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "extractor_args": {"youtube": {"player_client": list(player_clients)}},
    }
    if proxy:
        ydl_opts["proxy"] = proxy
    # A logged-in browser cookie jar is the most reliable way past YouTube's
    # "Sign in to confirm you're not a bot" wall, which fires on Tor exit IPs.
    if cookies:
        # A browser name must go to extract_cookies_from_browser, NOT
        # cookiefile: cookiefile=<browser> silently dumps a Netscape jar into
        # the CWD, and a leaked jar of that name would then break
        # is_file(), so dispatch on browser name rather than probing the fs.
        known_browsers = {
            "chrome", "chromium", "edge", "firefox", "brave", "bravebrowser",
            "vivaldi", "opera", "safari", "konqueror", "ie", "silk",
        }
        has_path_sep = any(sep in cookies for sep in ("/", os.sep))
        has_extension = os.path.splitext(cookies)[1] != ""
        if cookies.lower() in known_browsers and not has_path_sep and not has_extension:
            from yt_dlp.cookies import extract_cookies_from_browser

            try:
                jar = extract_cookies_from_browser(cookies)
                if jar:
                    ydl_opts["cookiejar"] = jar
                    log.info(f"yt-dlp: using {len(jar)} cookies from browser {cookies}")
            except Exception as exc:  # browser not installed / not logged in
                log.warn(f"could not load cookies from '{cookies}': {exc}")
        else:
            cookies_path = Path(os.path.expanduser(cookies))
            ydl_opts["cookiefile"] = str(cookies_path)
            log.info(f"yt-dlp: using cookies from file {cookies_path}")
    if not proxy:
        log.info("yt-dlp: downloading without a proxy (direct connection)")

    # When the exit IP itself is flagged (bot check), no amount of client
    # rotation helps. Rotate the Tor circuit *before* the first attempt so the
    # whole download runs on a fresh exit, and re-rotate between attempts if a
    # bot-block error surfaces.
    attempts = _client_attempts(player_clients)
    for attempt, clients in enumerate(attempts, start=1):
        if (attempt == 1 or force_rotate) and rotate_tor_circuit():
            # Fresh exit before the first real try when a Tor proxy is in use.
            log.info("tor: rotated to a fresh exit circuit")
        opts = {**ydl_opts, "extractor_args": {"youtube": {"player_client": list(clients)}}}
        log.info(f"yt-dlp: downloading bestaudio via {proxy} (clients: {', '.join(clients)})")
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # Playlists nest one level deeper. We disabled them above, but be
                # defensive in case the URL is e.g. a single video inside a list.
                if "entries" in info and info["entries"]:
                    info = info["entries"][0]
                audio_path = Path(ydl.prepare_filename(info))
            if not audio_path.is_file():
                matches = sorted(work_dir.glob(f"{info.get('id', '*')}.*"))
                if matches:
                    audio_path = matches[0]
            if audio_path.is_file():
                log.info(f"downloaded audio: {audio_path.name}")
                return DownloadResult(path=audio_path, info=info or {})
        except Exception as exc:  # yt-dlp raises a zoo of exception types
            if attempt < len(attempts):
                log.warn(f"download attempt {attempt} failed ({exc}); retrying with fewer clients")
                if _looks_like_bot_block(str(exc)):
                    log.info(
                        "download blocked (bot check) — rotating Tor exit and "
                        "retrying before giving up"
                    )
                    if rotate_tor_circuit():
                        log.info("tor: rotated to a fresh exit circuit for retry")
                continue
            # Final attempt exhausted: if this was a bot-block, surface the
            # cookie/proxy guidance instead of a generic failure.
            if _looks_like_bot_block(str(exc)):
                raise DownloadError(
                    "yt-dlp was blocked by YouTube ('Sign in to confirm you're "
                    "not a bot'). The Tor exit IP was flagged. Options: "
                    "(1) drop a Netscape-format cookie jar at "
                    f"{cookies or '~/.localcaption/yt-dlp-cookies.txt'} "
                    "(or set LOCALCAPTION_YTDLP_COOKIES), "
                    "(2) retry to grab a fresh Tor exit, "
                    "(3) point LOCALCAPTION_PROXY at a non-Tor exit that "
                    "YouTube does not flag."
                ) from exc
            raise DownloadError(f"yt-dlp failed: {exc}") from exc

    raise DownloadError(
        f"yt-dlp finished but no audio file was found near {ydl_opts['outtmpl']}"
    )
