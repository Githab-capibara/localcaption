# Title: Give each model family its own virtualenv

Status: Accepted
Date: 2026-09-22
Deciders: Maintainer, runtime reviewers
Related: [adr/01-language-routing.md](01-language-routing.md), [models/02-isolated-runtimes.md](../models/02-isolated-runtimes.md)

## Context

The three ASR families pin **incompatible** `transformers` versions:
`qwen-asr` wants `transformers` 4.x while the NVIDIA NeMo-based models
(Parakeet, Nemotron) need `transformers >= 5.13`. speechbrain additionally
imports `torchaudio` at import time, and CPU `torchaudio` wheels only ship up
to 2.11 — forcing an older `torch` for that env. No single Python environment
can satisfy all of them.

## Decision

Build **one isolated virtualenv per model family** under `runtime/`, plus a
`main` environment for the package itself:

| venv | Packages (via `scripts/setup_runtime.sh`, uv, Python 3.12) |
|---|---|
| `main` | the `localcaption` package (editable) + `yt-dlp` |
| `nvidia` | `torch==2.14.0` (CPU index), `transformers>=5.13.0`, `numpy`, `librosa>=0.10` |
| `qwen` | `torch==2.14.0` (CPU index), `qwen-asr>=0.0.6` |
| `langid` | `torch==2.11.0`, `torchaudio==2.11.0` (CPU index), `speechbrain>=1.0` |

The ASR stage (`src/localcaption/asr.py`) drives each model through a
standalone runner script (`src/localcaption/runners/*.py`) executed as a
subprocess with that env's interpreter; the runner writes a JSON segment
manifest. The main package never imports `torch`/`transformers`/`speechbrain`
(`runtime.check_env`, `asr.run_runner`). Whichever libs are present in the
host Python are irrelevant — only the env Python matters.

## Consequences

Positive:
- Each family pins exactly what it needs; upgrades are isolated.
- The main package stays light (only `yt-dlp` as runtime dependency).
- A broken ASR env fails loudly at `doctor` time, not mid-run.

Negative / trade-offs:
- 4 virtualenvs ≈ multi-GB of disk under `runtime/`.
- First install is slow: `scripts/setup_runtime.sh` downloads torch per env.
- Every transcription pays a subprocess hop per runner invocation.

## Alternatives considered

- One shared env pinned to a single `transformers` version — impossible: the
  4.x-vs-≥5.13 conflict is hard and blocks both families.
- Vendoring the model stacks into the sdist — would balloon the package and
  break the "small orchestrator" property.
- A process-level dependency-injection layer on one env — forces the three
  stacks to coexist in RAM and on disk, defeating the point.