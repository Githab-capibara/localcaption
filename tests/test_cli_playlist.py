"""Tests for CLI playlist routing.

A URL with ``&list=`` should auto-expand to every video in the list and run
each through the batch machinery (per-video output dirs, skip-if-done). These
tests stub the expansion + transcribe steps so we assert routing, not network.
"""

from __future__ import annotations

from pathlib import Path

from localcaption import cli

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def test_no_playlist_flag_defaults_to_on() -> None:
    """--no-playlist must default to True (transcribe whole list by default)."""
    args = cli._build_transcribe_parser().parse_args(
        ["https://www.youtube.com/watch?v=x&list=PL1"]
    )
    assert args.playlist is True


def test_no_playlist_flag_turns_it_off() -> None:
    args = cli._build_transcribe_parser().parse_args(
        ["--no-playlist", "https://www.youtube.com/watch?v=x&list=PL1"]
    )
    assert args.playlist is False


def test_playlist_limit_flag() -> None:
    args = cli._build_transcribe_parser().parse_args(
        ["--playlist-limit", "3", "https://www.youtube.com/watch?v=x&list=PL1"]
    )
    assert args.playlist_limit == 3


# ---------------------------------------------------------------------------
# Routing: _run_playlist calls expand_playlist then transcribe_urls
# ---------------------------------------------------------------------------

def _make_args(tmp_path: Path, **overrides):
    defaults = {
        "url": "https://www.youtube.com/watch?v=x&list=PL1",
        "out": tmp_path / "out",
        "language": "auto",
        "model": None,
        "keep_audio": False,
        "summary": False,
        "summary_model": "llama3.1:8b",
        "summary_prompt": None,
        "cookies": None,
        "no_proxy": False,
        "rotate_tor": False,
        "playlist": True,
        "playlist_limit": None,
        "no_print": False,
        "batch": None,
        "auto_download": True,
    }
    defaults.update(overrides)
    return _Namespace(defaults)


class _Namespace:
    """Lightweight argparse.Namespace stand-in."""

    def __init__(self, mapping: dict) -> None:
        self.__dict__.update(mapping)


def test_run_playlist_expands_and_routes(monkeypatch, tmp_path: Path) -> None:
    """A playlist URL must be expanded and each entry run through batch."""
    captured_batch: dict = {}

    def _fake_expand(url, *, proxy, cookies):
        assert url.endswith("list=PL1")
        return type("Info", (), {
            "urls": [
                "https://www.youtube.com/watch?v=vid1",
                "https://www.youtube.com/watch?v=vid2",
            ],
            "entry_count": 2,
            "playlist_id": "PL1",
            "title": "t",
        })()

    def _fake_batch(urls, *, out_dir, language, force_model, keep_intermediate,
                    cookies, proxy, force_rotate):
        captured_batch["urls"] = list(urls)
        captured_batch["out_dir"] = out_dir
        # Return a BatchResult with zero items and no failures.
        from localcaption.batch import BatchResult
        return BatchResult(items=[], wall_clock_s=0.0)

    monkeypatch.setattr(cli, "expand_playlist", _fake_expand)
    monkeypatch.setattr(cli, "transcribe_urls", _fake_batch)

    args = _make_args(tmp_path)
    rc = cli._run_playlist(args, urls=[args.url], proxy=None, cookies=None)
    assert rc == 0
    assert captured_batch["urls"] == [
        "https://www.youtube.com/watch?v=vid1",
        "https://www.youtube.com/watch?v=vid2",
    ]


def test_run_playlist_respects_limit(monkeypatch, tmp_path: Path) -> None:
    """--playlist-limit must truncate the expanded list."""
    captured_batch: dict = {}

    def _fake_expand(url, *, proxy, cookies):
        return type("Info", (), {
            "urls": [f"https://www.youtube.com/watch?v=v{i}" for i in range(10)],
            "entry_count": 10,
            "playlist_id": "PL1",
            "title": "t",
        })()

    def _fake_batch(urls, *, out_dir, language, force_model, keep_intermediate,
                    cookies, proxy, force_rotate):
        captured_batch["urls"] = list(urls)
        from localcaption.batch import BatchResult
        return BatchResult(items=[], wall_clock_s=0.0)

    monkeypatch.setattr(cli, "expand_playlist", _fake_expand)
    monkeypatch.setattr(cli, "transcribe_urls", _fake_batch)

    args = _make_args(tmp_path, playlist_limit=3)
    rc = cli._run_playlist(args, urls=[args.url], proxy=None, cookies=None)
    assert rc == 0
    assert len(captured_batch["urls"]) == 3


def test_run_playlist_expansion_error_returns_1(monkeypatch, tmp_path: Path) -> None:
    """A PlaylistError from expansion must propagate as exit code 1."""
    from localcaption.playlist import PlaylistError

    def _fake_expand(url, *, proxy, cookies):
        raise PlaylistError("boom")

    monkeypatch.setattr(cli, "expand_playlist", _fake_expand)

    args = _make_args(tmp_path)
    rc = cli._run_playlist(args, urls=[args.url], proxy=None, cookies=None)
    assert rc == 1


# ---------------------------------------------------------------------------
# _run_one routes playlist URLs to _run_playlist
# ---------------------------------------------------------------------------

def test_run_one_routes_playlist_url(monkeypatch, tmp_path: Path) -> None:
    """When args.playlist is True and the URL has &list=, call _run_playlist."""
    called: dict = {}

    def _fake_run_playlist(args, *, urls, proxy, cookies):
        called["urls"] = urls
        return 0

    monkeypatch.setattr(cli, "_run_playlist", _fake_run_playlist)
    args = _make_args(tmp_path)
    rc = cli._run_one(args)
    assert rc == 0
    assert called["urls"] == [args.url]


def test_run_one_no_playlist_skips_expansion(monkeypatch, tmp_path: Path) -> None:
    """--no-playlist must NOT call _run_playlist; it runs the single-video path."""
    called: dict = {"run_playlist": False}

    def _fake_run_playlist(args, *, urls, proxy, cookies):
        called["run_playlist"] = True
        return 0

    def _fake_transcribe_url(url, **kwargs):
        # Stub a PipelineResult with the attrs _run_one reads.
        class _T:
            @staticmethod
            def existing():
                return {}

            txt = tmp_path / "nope.md"

        class _P:
            transcripts = _T()
            summary = None
            chapters_json = None
            chaptered_md = None

        return _P()

    monkeypatch.setattr(cli, "_run_playlist", _fake_run_playlist)
    monkeypatch.setattr(cli, "transcribe_url", _fake_transcribe_url)
    args = _make_args(tmp_path, playlist=False)
    rc = cli._run_one(args)
    assert rc == 0
    assert called["run_playlist"] is False
