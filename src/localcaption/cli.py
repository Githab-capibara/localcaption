"""Command-line entry point.

Exposed as the ``localcaption`` console script via ``pyproject.toml``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from . import _logging as log
from .errors import LocalCaptionError
from .pipeline import transcribe_url
from .whisper import DEFAULT_MODEL


def _default_whisper_dir() -> Path:
    """Where to look for the whisper.cpp checkout.

    Order of resolution:
        1. ``$LOCALCAPTION_WHISPER_DIR`` if set.
        2. ``./whisper.cpp`` (the layout produced by ``scripts/setup.sh``).
    """
    env = os.environ.get("LOCALCAPTION_WHISPER_DIR")
    if env:
        return Path(env).expanduser()
    return Path.cwd() / "whisper.cpp"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="localcaption",
        description="Fully-local YouTube → transcript using yt-dlp + ffmpeg + whisper.cpp.",
    )
    parser.add_argument("url", help="YouTube URL (or any URL yt-dlp supports)")
    parser.add_argument(
        "-m", "--model", default=DEFAULT_MODEL,
        help=f"whisper model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "-o", "--out", type=Path, default=Path.cwd() / "transcripts",
        help="output directory for transcript files (default: ./transcripts)",
    )
    parser.add_argument(
        "-l", "--language", default="auto",
        help="ISO language code, or 'auto' (default: auto)",
    )
    parser.add_argument(
        "--whisper-dir", type=Path, default=None,
        help="path to a built whisper.cpp checkout "
             "(default: $LOCALCAPTION_WHISPER_DIR or ./whisper.cpp)",
    )
    parser.add_argument(
        "--keep-audio", action="store_true",
        help="keep the downloaded audio and intermediate WAV under <out>/.work/",
    )
    parser.add_argument(
        "--no-print", action="store_true",
        help="do not echo the transcript to stdout when finished",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    whisper_dir = args.whisper_dir or _default_whisper_dir()

    try:
        result = transcribe_url(
            args.url,
            out_dir=args.out,
            whisper_dir=whisper_dir,
            model=args.model,
            language=args.language,
            keep_intermediate=args.keep_audio,
        )
    except LocalCaptionError as exc:
        log.error(str(exc))
        return 1

    log.info("transcript files:")
    for kind, path in result.transcripts.existing().items():
        print(f"  {kind:>4}: {path}")

    if not args.no_print:
        txt = result.transcripts.txt
        if txt.exists():
            print("\n" + "─" * 30 + " transcript " + "─" * 30)
            print(txt.read_text(encoding="utf-8", errors="replace"))

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
