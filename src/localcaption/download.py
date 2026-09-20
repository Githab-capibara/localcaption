"""Stage 1: download the best available audio stream with yt-dlp.

We use yt-dlp's Python API rather than the CLI so we can deterministically
discover the resulting filename via :py:meth:`YoutubeDL.prepare_filename`.
This avoids the fragility of parsing ``--print after_move:filepath`` output
across yt-dlp versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _logging as log
from .errors import DependencyError, DownloadError
from .network import get_proxy

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
) -> DownloadResult:
    """Download the best audio stream for *url* into *work_dir*.

    Returns the path plus the yt-dlp info dict. Raises :class:`DownloadError`
    if yt-dlp fails to produce a usable file.
    """
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise DependencyError(
            "Python package 'yt-dlp' is not installed. "
            "Install with: pip install -e .[dev]   (or)   pip install yt-dlp"
        ) from exc

    proxy = get_proxy()
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
        "proxy": proxy,
        "extractor_args": {"youtube": {"player_client": list(player_clients)}},
    }

    # On a 403 mid-download, YouTube has usually flagged the player client.
    # Retry by trimming the client list (drop the most aggressively-blocked
    # clients first) so a less-blocked client can carry the stream.
    attempts = _client_attempts(player_clients)
    for attempt, clients in enumerate(attempts, start=1):
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
                continue
            raise DownloadError(f"yt-dlp failed: {exc}") from exc

    raise DownloadError(
        f"yt-dlp finished but no audio file was found near {ydl_opts['outtmpl']}"
    )
