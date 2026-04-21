"""Command-line entry point.

Exposed as the ``localcaption`` console script via ``pyproject.toml``.

Two invocation styles are supported:

    localcaption <url> [options]      # one-shot transcription (default)
    localcaption doctor               # diagnose your install
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from . import _logging as log
from .errors import LocalCaptionError
from .pipeline import transcribe_url
from .whisper import DEFAULT_MODEL, WhisperPaths

# Subcommands recognised by the dispatcher. Anything else is treated as a URL
# and routed to the implicit "transcribe" command for backwards compatibility.
SUBCOMMANDS = frozenset({"doctor", "transcribe"})


# --- whisper.cpp directory resolution ------------------------------------

def _xdg_data_home() -> Path:
    """Return $XDG_DATA_HOME or its conventional fallback (~/.local/share)."""
    env = os.environ.get("XDG_DATA_HOME")
    return Path(env).expanduser() if env else Path.home() / ".local" / "share"


def _candidate_whisper_dirs() -> list[Path]:
    """Where to look for the whisper.cpp checkout, in priority order.

    1. ``$LOCALCAPTION_WHISPER_DIR`` if set (explicit override).
    2. ``./whisper.cpp`` if running from a dev checkout.
    3. ``$XDG_DATA_HOME/localcaption/whisper.cpp`` (where ``install.sh`` puts it).
    """
    candidates: list[Path] = []
    env = os.environ.get("LOCALCAPTION_WHISPER_DIR")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path.cwd() / "whisper.cpp")
    candidates.append(_xdg_data_home() / "localcaption" / "whisper.cpp")
    return candidates


def _default_whisper_dir() -> Path:
    """Pick the first existing whisper.cpp directory, or the last candidate.

    The "last candidate" fallback ensures error messages point users at the
    canonical install location rather than the dev-only ``./whisper.cpp``.
    """
    candidates = _candidate_whisper_dirs()
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[-1]


# --- transcribe (default) subcommand -------------------------------------

def _build_transcribe_parser() -> argparse.ArgumentParser:
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
             "(default: $LOCALCAPTION_WHISPER_DIR, ./whisper.cpp, "
             "or ~/.local/share/localcaption/whisper.cpp)",
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


def _cmd_transcribe(argv: list[str]) -> int:
    args = _build_transcribe_parser().parse_args(argv)
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


# --- doctor subcommand ---------------------------------------------------

def _check(label: str, ok: bool, detail: str = "") -> bool:
    """Print a diagnostic line. Returns ``ok`` for chaining into a final exit code."""
    mark = "✅" if ok else "❌"
    suffix = f"  ({detail})" if detail else ""
    print(f"  {mark} {label}{suffix}")
    return ok


def _cmd_doctor(argv: list[str]) -> int:
    """Diagnose a localcaption install: prereqs, whisper.cpp, models."""
    parser = argparse.ArgumentParser(
        prog="localcaption doctor",
        description="Diagnose a localcaption install: external tools, "
                    "whisper.cpp build, available models.",
    )
    parser.add_argument(
        "--whisper-dir", type=Path, default=None,
        help="check this whisper.cpp directory (default: auto-detect)",
    )
    args = parser.parse_args(argv)

    print(f"localcaption {__version__}\n")

    all_ok = True

    print("System tools:")
    all_ok &= _check("python", True, sys.version.split()[0])
    ff = shutil.which("ffmpeg")
    all_ok &= _check("ffmpeg", ff is not None, ff or "missing — `brew install ffmpeg`")
    git = shutil.which("git")
    all_ok &= _check("git", git is not None, git or "missing")

    print("\nPython dependencies:")
    try:
        import yt_dlp  # noqa: F401
        from yt_dlp.version import __version__ as ytdlp_ver
        all_ok &= _check("yt-dlp", True, ytdlp_ver)
    except ImportError:
        all_ok &= _check("yt-dlp", False, "missing — `pip install yt-dlp`")

    print("\nwhisper.cpp:")
    whisper_dir = args.whisper_dir or _default_whisper_dir()
    print(f"  searching: {whisper_dir}")
    fix_hints: list[str] = []

    if whisper_dir.is_dir():
        _check("directory exists", True, str(whisper_dir))
        paths = WhisperPaths(whisper_dir)
        try:
            binary = paths.find_binary()
            all_ok &= _check("binary built", True, str(binary))
        except LocalCaptionError as exc:
            all_ok &= _check("binary built", False, str(exc).splitlines()[0])
            fix_hints.append(
                "whisper.cpp directory exists but isn't built. To build it:\n"
                f"    cd {whisper_dir}\n"
                "    cmake -B build && cmake --build build -j --config Release"
            )

        models_dir = paths.models_dir
        if models_dir.is_dir():
            available = sorted(p.name for p in models_dir.glob("ggml-*.bin"))
            if available:
                _check("models present", True, ", ".join(available))
            else:
                all_ok &= _check("models present", False, f"no ggml-*.bin in {models_dir}")
                fix_hints.append(
                    "No ggml-*.bin model files found. To download the default model:\n"
                    f"    bash {models_dir}/download-ggml-model.sh base.en"
                )
        else:
            all_ok &= _check("models directory", False, str(models_dir))
            fix_hints.append(
                f"models/ subdirectory missing under {whisper_dir} — "
                "your whisper.cpp clone may be incomplete; re-clone it."
            )
    else:
        all_ok &= _check("directory exists", False, str(whisper_dir))
        fix_hints.append(
            "whisper.cpp is not installed. Pick ONE of:\n\n"
            "  Option A — let our installer do it for you:\n"
            "    curl -fsSL https://raw.githubusercontent.com/jatinkrmalik/"
            "localcaption/main/scripts/install.sh | bash\n\n"
            "  Option B — DIY, anywhere you like:\n"
            "    git clone https://github.com/ggerganov/whisper.cpp \\\n"
            "        ~/.local/share/localcaption/whisper.cpp\n"
            "    cd ~/.local/share/localcaption/whisper.cpp\n"
            "    cmake -B build && cmake --build build -j --config Release\n"
            "    bash models/download-ggml-model.sh base.en\n\n"
            "  Option C — point us at an existing whisper.cpp checkout:\n"
            "    export LOCALCAPTION_WHISPER_DIR=/path/to/your/whisper.cpp\n"
            "    # add that line to your shell rc to make it stick"
        )

    print("\nLookup paths searched:")
    for c in _candidate_whisper_dirs():
        marker = "✓" if c.is_dir() else "·"
        print(f"  {marker} {c}")

    if fix_hints:
        print("\nHow to fix:\n")
        for hint in fix_hints:
            for line in hint.splitlines():
                print(f"  {line}" if line else "")
            print()

    if all_ok:
        print("All checks passed. You're good to go: localcaption <url>")
        return 0
    else:
        print("Some checks failed. See 'How to fix' above.")
        return 1


# --- top-level dispatcher -------------------------------------------------

def _print_top_level_help() -> None:
    print("""\
usage: localcaption <url> [options]            transcribe a video (default)
       localcaption doctor                     diagnose your install
       localcaption --help                     show transcribe help
       localcaption --version                  print version

Run `localcaption <subcommand> --help` for details on each.""")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Bare invocation → top-level help (exit non-zero, like most CLIs do).
    if not argv:
        _print_top_level_help()
        return 2

    head = argv[0]

    # Allow `localcaption help` as a friendly alias for the top-level help.
    if head in {"help", "--help-all"}:
        _print_top_level_help()
        return 0

    # Explicit subcommands.
    if head == "doctor":
        return _cmd_doctor(argv[1:])
    if head == "transcribe":
        return _cmd_transcribe(argv[1:])

    # Anything else (URL, --help, --version, …) goes to the default transcribe.
    return _cmd_transcribe(argv)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
