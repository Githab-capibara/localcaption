# Doctor and self-healing

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: `localcaption doctor` diagnostics and the `--fix` repair order.
Feeds into: [01-installation.md](01-installation.md),
[../api/04-error-handling.md](../api/04-error-handling.md)

## Flow

`src/localcaption/cli.py::_cmd_doctor`. Plain `doctor` is **read-only** — it
must never invoke the installer (`tests/test_cli_doctor.py` pins this with a
safety guarantee).

1. Header `localcaption <version>`.
2. `System tools:` — python version, `ffmpeg`, `git`, `curl` (with hints:
   brew `ffmpeg` for audio, `git` for yt-dlp extractors, `curl` for model
   downloads). `_check` prints ✅/❌ per item.
3. `Python dependencies:` — `yt-dlp` import + version.
4. `Network:` — proxy reachability (TCP connect, 3 s timeout).
5. `YouTube / Tor bot-check mitigations:` — cookie source availability and
   Tor rotation reachability (control port; hint `Tor control port 9051?`).
6. `Model runtimes:` — each env via `runtime.check_all()` (`main` isn't
   probed; `langid`/`qwen`/`nvidia` import their probe package).
7. `Models:` — `models.list_status()` per checkpoint.
8. Success message: `All checks passed. You're good to go:
   localcaption <url-or-file>`.

## `--fix` repair order

`_apply_doctor_fix` runs only on missing items, in order:

1. System deps in order — `git`, `curl`, `ffmpeg` — via `brew install` or
   `sudo apt-get update -y && sudo apt-get install -y …`.
2. Model runtimes — `installer.ensure_runtime()` → `bash
   scripts/setup_runtime.sh` (requires `uv`).
3. Model checkpoints — `models.download_all()`.

Each step is idempotent; a failed step aborts the fix run with
`Fix aborted` and exit 1, and later steps are not reached.

## Failure modes

- Doctor with gaps → exit 1 (expected before first install).
- `--fix` failure → exit 1 with the failing step surfaced; re-running resumes
  only the missing parts.