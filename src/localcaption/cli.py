"""Command-line entry point.

Exposed as the ``localcaption`` console script via ``pyproject.toml``.

Invocation styles:

    localcaption <url-or-file> [options]   # one-shot transcription (default)
    localcaption --batch FILE [options]    # sequential list of URLs/files
    localcaption doctor                    # diagnose your install
    localcaption model <subcommand>        # list/download/rm/info
    localcaption search <term>             # grep past transcripts
"""

from __future__ import annotations

import argparse
import shutil
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from . import _logging as log
from .batch import read_url_list, transcribe_urls
from .errors import LocalCaptionError
from .network import get_proxy
from .pipeline import normalize_language, transcribe_url
from .summary import DEFAULT_MODEL as DEFAULT_SUMMARY_MODEL

SUBCOMMANDS = frozenset({"doctor", "transcribe", "search", "model"})


# --- transcribe (default) subcommand -------------------------------------

def _build_transcribe_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="localcaption",
        description="Fully-local video → transcript using yt-dlp + ffmpeg + "
                    "local language-ID and ASR models.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="YouTube URL, any URL yt-dlp supports, or path to a local video/audio file",
    )
    parser.add_argument(
        "--batch",
        type=Path,
        metavar="FILE",
        help="transcribe every non-empty, non-# line in FILE sequentially",
    )
    parser.add_argument(
        "--model", metavar="KEY", default=None,
        help="force a specific ASR model key (skip language routing); "
             "see `localcaption model list`",
    )
    parser.add_argument(
        "-o", "--out", type=Path, default="transcripts",
        help="output directory for transcript files (default: ./transcripts)",
    )
    parser.add_argument(
        "-l", "--language", default="auto",
        help="ISO code or language name, or 'auto' to detect (default: auto)",
    )
    parser.add_argument(
        "--output-format", dest="output_format", default="md",
        choices=["md", "txt", "srt", "vtt", "json", "all"],
        help="output format(s). Default 'md' = a single Markdown file. "
              "'all'/'full'/'complete' emits every format.",
    )
    parser.add_argument(
        "--keep-audio", action="store_true",
        help="keep the downloaded audio and intermediate WAV under <out>/.work/",
    )
    parser.add_argument(
        "--no-print", action="store_true",
        help="do not echo the transcript to stdout when finished",
    )
    parser.add_argument(
        "--auto-download", action="store_true",
        help="if a required model isn't installed, download it without asking",
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="write a Markdown summary via local Ollama (http://localhost:11434)",
    )
    parser.add_argument(
        "--summary-model", default=DEFAULT_SUMMARY_MODEL,
        help=f"Ollama model for --summary (default: {DEFAULT_SUMMARY_MODEL})",
    )
    parser.add_argument(
        "--summary-prompt", type=Path, default=None,
        help="path to a prompt template for --summary (default: built-in)",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _required_models(language: str, force_model: str | None) -> list[str]:
    """Model keys we can predict are needed for this run."""
    from . import asr, models

    if force_model is not None:
        return [force_model]
    code = normalize_language(language)
    if code == "auto":
        return [m.key for m in models.known_models()]
    return [asr.model_for_language(code)]


def _format_size_mb(mb: int) -> str:
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb} MB"


def _ensure_models(keys: list[str], auto: bool) -> bool:
    """Make sure *keys* are installed, prompting/downloading as needed."""
    from . import models

    try:
        missing = models.missing_models(keys)
    except LocalCaptionError as exc:
        log.error(str(exc))
        return False
    if not missing:
        return True

    print("Missing model checkpoints:")
    for key in missing:
        spec = models.get_model(key)
        print(f"  - {spec.key}: {spec.description} (~{_format_size_mb(spec.approx_size_mb)})")

    if auto:
        proceed = True
    elif not sys.stdin.isatty():
        log.error(
            "Cannot prompt to download models (stdin is not a TTY).\n"
            f"  Run: localcaption model download {missing[0]}\n"
            "  Or pass --auto-download."
        )
        return False
    else:
        try:
            reply = input("  Download now? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return False
        proceed = reply in {"", "y", "yes"}

    if not proceed:
        print(f"  Skipped. Run: localcaption model download {missing[0]}")
        return False

    try:
        for key in missing:
            models.download_model(key)
    except LocalCaptionError as exc:
        log.error(str(exc))
        return False
    except KeyboardInterrupt:
        log.error("interrupted; partial downloads were kept and can resume.")
        return False
    return True


def _cmd_transcribe(argv: list[str]) -> int:
    parser = _build_transcribe_parser()
    args = parser.parse_args(argv)
    has_batch = args.batch is not None
    has_url = bool(args.url)
    if has_batch == has_url:
        parser.error(
            "provide a URL/file or --batch FILE" + (", not both" if has_batch else "")
        )

    if not _ensure_models(_required_models(args.language, args.model), args.auto_download):
        return 1

    if args.batch:
        return _run_batch(args)
    return _run_one(args)


def _run_one(args: argparse.Namespace) -> int:
    try:
        result = transcribe_url(
            args.url,
            out_dir=args.out,
            language=args.language,
            force_model=args.model,
            keep_intermediate=args.keep_audio,
            summary=args.summary,
            summary_model=args.summary_model,
            summary_prompt=args.summary_prompt,
        )
    except LocalCaptionError as exc:
        log.error(str(exc))
        return 1

    log.info("transcript files:")
    for kind, path in result.transcripts.existing().items():
        print(f"  {kind:>4}: {path}")
    if result.summary is not None:
        print(f"  summary: {result.summary}")
    if result.chapters_json:
        print(f"  chapters: {result.chapters_json}")
    if result.chaptered_md:
        print(f"  chaptered: {result.chaptered_md}")

    if not args.no_print:
        txt = result.transcripts.txt
        if txt.exists():
            print("\n" + "─" * 30 + " transcript " + "─" * 30)
            print(txt.read_text(encoding="utf-8", errors="replace"))

    return 0


def _run_batch(args: argparse.Namespace) -> int:
    if not args.batch.is_file():
        log.error(f"batch file not found: {args.batch}")
        return 1
    try:
        urls = read_url_list(args.batch)
    except OSError as exc:
        log.error(f"cannot read batch file: {exc}")
        return 1
    if not urls:
        log.warn(f"no URLs in {args.batch}")

    result = transcribe_urls(
        urls,
        out_dir=args.out,
        language=args.language,
        force_model=args.model,
        keep_intermediate=args.keep_audio,
    )
    print(result.summary())
    return result.exit_code()


# --- doctor subcommand ---------------------------------------------------

def _check(label: str, ok: bool, detail: str = "") -> bool:
    """Print a diagnostic line. Returns ``ok`` for chaining into a final exit code."""
    mark = "✅" if ok else "❌"
    suffix = f"  ({detail})" if detail else ""
    print(f"  {mark} {label}{suffix}")
    return ok


def _proxy_reachable(proxy: str) -> bool:
    """Best-effort TCP check that the configured proxy is listening."""
    parsed = urlparse(proxy)
    if not parsed.hostname or not parsed.port:
        return False
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=3):
            return True
    except OSError:
        return False


def _run_doctor_diagnostics() -> tuple[bool, list[str], dict[str, bool]]:
    """Run all diagnostic checks and print results.

    Returns ``(all_ok, fix_hints, gaps)`` where ``gaps`` drives ``--fix``:

        {"ffmpeg": bool, "git": bool, "curl": bool, "runtime": bool, "models": bool}
    """
    from . import models, runtime

    gaps = {"ffmpeg": False, "git": False, "curl": False, "runtime": False, "models": False}
    fix_hints: list[str] = []
    all_ok = True

    print("System tools:")
    all_ok &= _check("python", True, sys.version.split()[0])
    for tool, hint in (
        ("ffmpeg", "needed to decode audio — `brew install ffmpeg`"),
        ("git", "needed by yt-dlp for some extractors"),
        ("curl", "needed to download models"),
    ):
        path = shutil.which(tool)
        all_ok &= _check(tool, path is not None, path or f"missing — {hint}")
        if path is None:
            gaps[tool] = True

    print("\nPython dependencies:")
    try:
        import yt_dlp  # noqa: F401
        from yt_dlp.version import __version__ as ytdlp_ver
        all_ok &= _check("yt-dlp", True, ytdlp_ver)
    except ImportError:
        all_ok &= _check("yt-dlp", False, "missing — `pip install yt-dlp`")

    print("\nNetwork:")
    proxy = get_proxy()
    reachable = _proxy_reachable(proxy)
    all_ok &= _check(
        "proxy", reachable,
        f"{proxy} ({'reachable' if reachable else 'not reachable'})",
    )
    if not reachable:
        fix_hints.append(
            f"The SOCKS5 proxy at {proxy} is not reachable.\n"
            "Start your proxy (e.g. Tor) or point localcaption elsewhere:\n"
            "    export LOCALCAPTION_PROXY=socks5h://host:port"
        )

    print("\nModel runtimes:")
    env_status = runtime.check_all()
    for name, status in env_status.items():
        all_ok &= _check(name, status.ready, status.detail)
    if any(not s.ready for s in env_status.values()):
        gaps["runtime"] = True
        fix_hints.append(
            "One or more model runtimes are missing. To build them:\n"
            "    bash scripts/setup_runtime.sh\n"
            "    (or just run: localcaption doctor --fix)"
        )

    print("\nModels:")
    statuses = models.list_status()
    for row in statuses:
        size = _format_size_mb(row.spec.approx_size_mb)
        detail = row.spec.description if row.installed else f"missing: {', '.join(row.missing)}"
        all_ok &= _check(f"{row.spec.key} (~{size})", row.installed, detail)
    if any(not row.installed for row in statuses):
        gaps["models"] = True
        fix_hints.append(
            "Some models are missing. To download everything:\n"
            "    localcaption model download --all\n"
            "    (or just run: localcaption doctor --fix)"
        )

    return all_ok, fix_hints, gaps


def _apply_doctor_fix(gaps: dict[str, bool]) -> bool:
    """Try to repair the gaps found by the diagnostic sweep."""
    from . import installer, models

    print("\nAttempting fixes:\n")

    for dep in ("git", "curl", "ffmpeg"):
        if gaps.get(dep):
            print(f"▸ Installing system dependency: {dep}")
            try:
                installer.install_system_dep(dep)
            except LocalCaptionError as exc:
                print(f"  ❌ Could not install {dep}: {exc}")
                return False
            print(f"  ✅ {dep} installed")

    if gaps.get("runtime"):
        print("▸ Creating model runtimes (this can take several minutes)")
        try:
            installer.ensure_runtime()
        except LocalCaptionError as exc:
            print(f"  ❌ Could not create runtimes: {exc}")
            return False
        print("  ✅ runtimes ready")

    if gaps.get("models"):
        print("▸ Downloading missing models (via the proxy)")
        try:
            models.download_all()
        except LocalCaptionError as exc:
            print(f"  ❌ Could not download models: {exc}")
            return False
        print("  ✅ models ready")

    return True


def _cmd_doctor(argv: list[str]) -> int:
    """Diagnose a localcaption install. With ``--fix``, also try to repair it."""
    parser = argparse.ArgumentParser(
        prog="localcaption doctor",
        description="Diagnose a localcaption install: external tools, proxy, "
                    "model runtimes, and checkpoints. Use --fix to attempt repair.",
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="attempt to install missing system tools, build the model "
             "runtimes, and download missing models",
    )
    args = parser.parse_args(argv)

    print(f"localcaption {__version__}\n")
    all_ok, fix_hints, gaps = _run_doctor_diagnostics()

    if all_ok:
        print("\nAll checks passed. You're good to go: localcaption <url-or-file>")
        return 0

    if not args.fix:
        if fix_hints:
            print("\nHow to fix:\n")
            for hint in fix_hints:
                for line in hint.splitlines():
                    print(f"  {line}" if line else "")
                print()
        print("Some checks failed. See 'How to fix' above, or re-run with --fix.")
        return 1

    if not _apply_doctor_fix(gaps):
        print("\nFix aborted. Address the error above and re-run.")
        return 1

    print("\n" + "─" * 60)
    print("Re-running diagnostics to verify…\n")
    all_ok_after, _, _ = _run_doctor_diagnostics()
    if all_ok_after:
        print("\nAll checks passed. You're good to go: localcaption <url-or-file>")
        return 0
    print("\nSome checks still failing — see output above.")
    return 1


# --- `model` subcommand family -------------------------------------------

def _cmd_model(argv: list[str]) -> int:
    """Dispatch `localcaption model {list,download,rm,info}`."""
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(
            "usage: localcaption model <subcommand> [options]\n\n"
            "subcommands:\n"
            "  list                list every supported model + install status\n"
            "  download <key>      download one model (or --all)\n"
            "  rm <key>            remove an installed model\n"
            "  info <key>          show details about one model\n"
        )
        return 0 if argv and argv[0] in {"-h", "--help", "help"} else 2

    sub = argv[0]
    rest = argv[1:]
    if sub == "list":
        return _cmd_model_list(rest)
    if sub == "download":
        return _cmd_model_download(rest)
    if sub in {"rm", "remove", "delete"}:
        return _cmd_model_rm(rest)
    if sub == "info":
        return _cmd_model_info(rest)

    print(f"localcaption model: unknown subcommand: {sub}", file=sys.stderr)
    print("Run `localcaption model --help` to see available subcommands.", file=sys.stderr)
    return 2


def _cmd_model_list(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="localcaption model list")
    parser.parse_args(argv)

    from . import models

    print("Models used by localcaption:\n")
    print(f"  {'Key':<30}{'Role':<14}{'Size':>10}   Status")
    print(f"  {'-' * 30:<30}{'-' * 14:<14}{'-' * 10:>10}   {'-' * 11}")
    for row in models.list_status():
        size = _format_size_mb(row.spec.approx_size_mb)
        status = "✅ installed" if row.installed else "not installed"
        print(f"  {row.spec.key:<30}{row.spec.role:<14}{size:>10}   {status}")

    print(f"\nInstall location: {models.paths.models_root()}")
    print("\nTips:")
    print("  • Russian audio → Qwen3-ASR, English → Parakeet, other → Nemotron.")
    print("  • To download one:  localcaption model download qwen3-asr-0.6b")
    print("  • To download all:  localcaption model download --all")
    return 0


def _cmd_model_info(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="localcaption model info")
    parser.add_argument("key", help="model key (e.g. parakeet-tdt-0.6b-v3)")
    args = parser.parse_args(argv)

    from . import models

    try:
        spec = models.get_model(args.key)
    except LocalCaptionError as exc:
        print(f"localcaption: {exc}", file=sys.stderr)
        return 2

    missing = models.missing_files(spec.key)
    print(f"Model:        {spec.key}")
    print(f"Role:         {spec.role}")
    print(f"Description:  {spec.description}")
    print(f"Approx size:  {_format_size_mb(spec.approx_size_mb)}")
    print(f"Runtime env:  {spec.env}")
    print(f"Source:       https://huggingface.co/{spec.hf_repo}")
    print(f"Local path:   {spec.local_dir}")
    if not missing:
        total = sum((spec.local_dir / f).stat().st_size for f in spec.files)
        print(f"Installed:    yes ({_format_size_mb(total // (1024 * 1024))} on disk)")
    else:
        print("Installed:    no")
        print(f"Missing:      {', '.join(missing)}")
        print(f"\nDownload with:  localcaption model download {spec.key}")
    return 0


def _cmd_model_download(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="localcaption model download")
    parser.add_argument("key", nargs="?", help="model key")
    parser.add_argument("--all", action="store_true",
                        help="download every registered model")
    parser.add_argument("--force", action="store_true",
                        help="re-download even if the model is already present")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="skip the confirmation prompt for --all")
    args = parser.parse_args(argv)

    from . import models

    if args.all:
        specs = list(models.known_models())
    elif args.key:
        try:
            specs = [models.get_model(args.key)]
        except LocalCaptionError as exc:
            print(f"localcaption: {exc}", file=sys.stderr)
            return 2
    else:
        parser.error("provide a model key or --all")

    total = sum(s.approx_size_mb for s in specs)
    print(f"▸ Downloading {len(specs)} model(s), ~{_format_size_mb(total)} total")
    print(f"  via proxy {get_proxy()}")
    try:
        for spec in specs:
            path = models.download_model(spec.key, force=args.force)
            print(f"✅ {spec.key} → {path}")
    except LocalCaptionError as exc:
        print(f"\nlocalcaption: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nlocalcaption: interrupted; partial downloads kept (resumable).", file=sys.stderr)
        return 130
    return 0


def _cmd_model_rm(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="localcaption model rm")
    parser.add_argument("key", help="model key")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="skip the confirmation prompt")
    args = parser.parse_args(argv)

    from . import models

    try:
        spec = models.get_model(args.key)
    except LocalCaptionError as exc:
        print(f"localcaption: {exc}", file=sys.stderr)
        return 2

    if not spec.local_dir.exists():
        print(
            f"localcaption: model {args.key!r} is not installed at {spec.local_dir}\n"
            "  Run `localcaption model list` to see installed models.",
            file=sys.stderr,
        )
        return 1

    print(f"About to remove: {spec.local_dir}")
    if not args.yes:
        try:
            reply = input("Continue? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.", file=sys.stderr)
            return 130
        if reply not in {"y", "yes"}:
            print("Cancelled.")
            return 0

    try:
        models.remove_model(args.key)
    except LocalCaptionError as exc:
        print(f"localcaption: {exc}", file=sys.stderr)
        return 1

    print("✓ Removed.")
    return 0


# --- search subcommand ----------------------------------------------------

def _cmd_search(argv: list[str]) -> int:
    """Grep previously transcribed videos via the JSONL search index."""
    parser = argparse.ArgumentParser(
        prog="localcaption search",
        description="Search past transcripts. Ranked by hit count; "
                    "timestamps come from the transcript JSON/SRT when present.",
    )
    parser.add_argument("term", nargs="+", help="search term (case-insensitive substring)")
    args = parser.parse_args(argv)

    from .chapters import format_timestamp
    from .index import default_index_path, search_index

    term = " ".join(args.term)
    try:
        hits = search_index(term)
    except OSError as exc:
        log.error(f"could not read search index: {exc}")
        return 1
    if not hits:
        print(f"No matches for {term!r} in {default_index_path()}")
        return 1

    for hit in hits:
        ts = format_timestamp(hit.start) if hit.start is not None else "--:--"
        print(f"{hit.id}  {ts}  {hit.text}")
        if hit.title:
            print(f"        {hit.title}")
    return 0


def _print_top_level_help() -> None:
    print("""\
usage: localcaption <url-or-file> [options]    transcribe a video (default)
       localcaption --batch FILE [options]     transcribe a list of URLs/files
       localcaption doctor [--fix]             diagnose your install
       localcaption model <subcommand>         list / download / remove models
       localcaption search <term>              search past transcripts
       localcaption --help                     show transcribe help
       localcaption --version                  print version

Run `localcaption <subcommand> --help` for details on each.""")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        _print_top_level_help()
        return 2

    head = argv[0]

    if head in {"help", "--help-all"}:
        _print_top_level_help()
        return 0

    if head == "doctor":
        return _cmd_doctor(argv[1:])
    if head == "model":
        return _cmd_model(argv[1:])
    if head == "search":
        return _cmd_search(argv[1:])
    if head == "transcribe":
        return _cmd_transcribe(argv[1:])

    return _cmd_transcribe(argv)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
