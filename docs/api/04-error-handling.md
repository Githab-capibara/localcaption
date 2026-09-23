# Error handling

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: The exception hierarchy and the mapping to CLI exit codes.
Feeds into: [../design/01-pipeline-stages.md](../design/01-pipeline-stages.md),
[../api/01-command-line-interface.md](../api/01-command-line-interface.md)

## Exception hierarchy

`src/localcaption/errors.py` — every project exception subclasses
`LocalCaptionError`:

| Exception | Raised when | Raised in |
|---|---|---|
| `DependencyError` | an external tool/model is missing (ffmpeg, yt-dlp, curl, model checkpoint, runner script/venv) | `audio.py`, `asr.py`, `download.py`, `models.py`, `playlist.py` |
| `DownloadError` | yt-dlp failed — including the bot-block message with Tor/cookies guidance | `download.py` |
| `AudioConversionError` | ffmpeg produced no WAV (nonzero exit or missing output) | `audio.py` |
| `TranscriptionError` | a runner exited nonzero or produced no manifest | `asr.py` |
| `InstallError` | an install step failed (unknown dep, no package manager, missing command, nonzero exit) | `installer.py` |
| `LocalCaptionError` (bare) | unknown model key, missing role, remove-of-uninstalled | `models.py` |
| `PlaylistError` (not a `LocalCaptionError`) | playlist expansion failed / produced zero videos | `playlist.py` |

Every runner failure is reported with the model key and exit code
(`Model <key> failed (exit N) on …`).

## Exit-code contract

From `src/localcaption/cli.py::main`:

| Code | Condition |
|---|---|
| 0 | success; all-ok/all-skipped batch; `help`/`--help` |
| 1 | any runtime failure (`LocalCaptionError`/`PlaylistError`/batch failures, search no-matches, doctor gaps, `--fix` abort) |
| 2 | usage errors: bare invocation, conflicting/missing transcribe args, unknown `model` subcommand or `info` key, `download` without key |
| 130 | `KeyboardInterrupt` during `model download`/`rm` |

## Non-fatal paths

The following never fail a run — they log warnings:

- Search-index upsert failure (`could not update search index`).
- Ollama summary failure (unreachable/timeout/HTTP/invalid body → `None`,
  "Summary skipped").
- Chapter sidecar write failure (`could not write chapter files`).
- Low-confidence language ID (routes to the multilingual model with a
  warning).