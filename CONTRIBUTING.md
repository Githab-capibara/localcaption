# Contributing to localcaption

Thanks for considering a contribution! This project is intentionally small —
the goal is to stay a thin, dependable orchestrator over `yt-dlp`, `ffmpeg`,
and a handful of local language-ID / ASR models. PRs that keep that surface
tidy are very welcome.

## Quick start

```bash
git clone https://github.com/jatinkrmalik/localcaption
cd localcaption
./scripts/setup.sh                  # creates .venv and builds runtime/
source .venv/bin/activate
pip install -e .[dev]               # if not already done by setup.sh
pytest                              # run the test suite
ruff check src tests                # lint
```

The `runtime/` virtualenvs hold multi-gigabyte ASR stacks. `scripts/setup_runtime.sh`
builds them; the test suite itself runs against `runtime/main` and does not
need any model checkpoints to be present.

## Project layout

```
src/localcaption/
├── __init__.py
├── __main__.py        # python -m localcaption
├── _logging.py        # tiny stdout logger (no logging-module config)
├── asr.py             # stage 3: route to the right ASR model, write artefacts
├── audio.py           # ffmpeg → 16 kHz mono WAV (stage 2)
├── batch.py           # public Python API: transcribe_urls(...)
├── chapters.py        # YouTube chapter sidecars + chaptered Markdown
├── cli.py             # argparse entry point (the `localcaption` script)
├── download.py        # yt-dlp Python API wrapper (stage 1)
├── errors.py          # exception hierarchy
├── formats.py         # txt / srt / vtt / json writers
├── index.py           # JSONL search index
├── installer.py       # system-dep + runtime installation helpers
├── langid.py          # language detection (via the langid runner)
├── languages.py       # SpeechBrain label ↔ ISO code mapping
├── models.py          # checkpoint registry + download/remove
├── network.py         # proxy policy for every outbound request
├── paths.py           # models/ and runtime/ layout
├── pipeline.py        # public Python API: transcribe_url(...)
├── runtime.py         # per-model virtualenv introspection
├── summary.py         # optional local Ollama summary
└── runners/           # standalone scripts executed inside each venv
    ├── _wavio.py      # shared WAV reader + windowing
    ├── langid.py      # speechbrain ECAPA-TDNN
    ├── qwen.py        # Qwen3-ASR
    └── nvidia.py      # Parakeet / Nemotron
scripts/
├── setup.sh           # dev venv + runtime bootstrap
├── setup_runtime.sh   # builds the per-model virtualenvs
├── install.sh         # end-user pipx bootstrap
└── uninstall.sh       # removes binary + runtimes + models
tests/                 # pytest suite
```

Each pipeline stage is its own module so you can swap one out (e.g. replace
the Qwen3-ASR runner for Russian) without touching the others. Runners must
stay dependency-free of the `localcaption` package itself — they are imported
inside a foreign virtualenv.

## Pull request checklist

- [ ] `pytest` passes.
- [ ] `ruff check src tests` passes (the CI runs both).
- [ ] New behaviour is covered by a test.
- [ ] User-visible changes are noted in `CHANGELOG.md` under `## [Unreleased]`.
- [ ] Public APIs have docstrings.

## Reporting bugs

Please include:

- The exact command you ran.
- The output of `localcaption --version` and `yt-dlp --version`.
- Your OS + Python version (`python --version`).
- The output of `localcaption doctor`.

For YouTube-side issues (HTTP 4xx, "Sign in to confirm…"), try
`pip install -U yt-dlp` first — those are usually upstream extractor breakage,
not bugs in this project.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
By participating you agree to abide by its terms.
