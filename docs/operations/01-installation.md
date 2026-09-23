# Installation

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: Every supported way to install, set up, and remove `localcaption`.
Feeds into: [02-doctor-self-healing.md](02-doctor-self-healing.md),
[../api/03-configuration.md](../api/03-configuration.md)

## Prerequisites

- Python 3.10+ (the CLI itself); macOS or Linux.
- `git`, `ffmpeg`, `curl` on `$PATH` — `doctor --fix` installs what's
  missing (Homebrew or apt).
- `uv` — required to build the model runtimes (installed by
  `scripts/install.sh` automatically).

## End users — one line (recommended)

```bash
pipx install localcaption && localcaption doctor --fix
```

`install.sh` bootstraps the same thing and then delegates the heavy lifting
to `doctor --fix`:

```bash
curl -fsSL https://raw.githubusercontent.com/jatinkrmalik/localcaption/main/scripts/install.sh | bash
```

Env knobs: `LOCALCAPTION_PACKAGE_SPEC` (what pipx installs),
`LOCALCAPTION_DATA_DIR`, `LOCALCAPTION_PROXY`.

## Developers — `scripts/setup.sh`

```bash
git clone https://github.com/jatinkrmalik/localcaption && cd localcaption
./scripts/setup.sh                  # runtime/ venvs + editable install + model checkpoints
source runtime/main/bin/activate
pytest
```

Knobs: `EXTRAS=dev` (default) / `EXTRAS=""`, `SKIP_MODELS=1` (skip the ~7 GB
download). The test suite runs against `runtime/main` and needs no
checkpoints.

## DIY (no installer)

```bash
bash scripts/setup_runtime.sh       # builds main/nvidia/qwen/langid venvs
localcaption model download --all   # ~7 GB, resumable, via the proxy
localcaption doctor                  # verify
```

## Uninstall — `scripts/uninstall.sh`

Interactive, idempotent; flags `--yes`, `--keep-models`, `--dry-run`. Removes
the pipx binary, the models + runtimes in `$XDG_DATA_HOME/localcaption`, and
the cache dir. It never touches pipx itself, ffmpeg/git/curl/uv, or cloned
source repos.

## Failure modes

- Missing `uv` → `doctor --fix`/`ensure_runtime` fails with an install hint.
- Unsupported OS → installer refuses (Darwin/Linux only).
- FFmpeg missing on `$PATH` → `AudioConversionError`/`DependencyError` until
  `doctor --fix` or manual install.