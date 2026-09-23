# Title: Route ASR by detected language

Status: Accepted
Date: 2026-09-22
Deciders: Maintainer, ASR reviewers
Related: [design/02-model-selection.md](../design/02-model-selection.md), [models/03-language-identification.md](../models/03-language-identification.md)

## Context

The project replaced the single whisper.cpp / faster-whisper backends with a
developer-supported, routed multi-model ASR stage (`src/localcaption/asr.py`).
One model rarely wins on every language: the best 0.6B-class checkpoints are
language-specialised (Russian is dominated by Qwen3-ASR, English by NVIDIA
Parakeet). We also want inference on CPU, no GPU to be required, and the
whole thing to stay off APIs and stay local.

## Decision

Detect the spoken language first, then route:

| Detected language | Model key | Role |
|---|---|---|
| `ru` | `qwen3-asr-0.6b` | Russian |
| `en` | `parakeet-tdt-0.6b-v3` | English |
| anything else, or unclear | `nemotron-3.5-asr-streaming-0.6b` | multilingual catch-all |

Detection uses a speechbrain ECAPA-TDNN classifier (`langid-ecapa`, 45
languages). A result is *confident* when `score >= 0.6`
(`src/localcaption/langid.py`, `LANGID_CONFIDENCE_THRESHOLD`); below that the
multilingual Nemotron model is used instead of guessing. Users can bypass
routing with `--language CODE` or force a model with `--model KEY`
(`src/localcaption/pipeline.py`, `resolve_model` / `asr.model_for_language`).

## Consequences

Positive:
- Best-known WER per language family at 0.6B scale; multilingual fallback
  still covers any of the 45 detected languages.
- Offline: the language-ID and ASR checkpoints live under `models/`.
- Deterministic, testable routing contract (`tests/test_asr.py`,
  `tests/test_pipeline.py`).

Negative / trade-offs:
- Four checkpoints ≈ 7 GB total download on first install.
- A wrong low-confidence guess quietly uses the slower multilingual model
  (accuracy over speed).
- Each model family lives in its own runtime — see
  [adr/02-isolated-model-runtimes.md](02-isolated-model-runtimes.md).

## Alternatives considered

- A single multilingual model for everything — simpler install, but worse
  Russian and English WER at the same size class.
- OpenAI Whisper as the only backend — heavier, and the removed
  whisper.cpp/faster-whisper backends complicated the surface (`--backend`,
  `--whisper-dir`) for no routing gain.
- Cloud transcription APIs — rejected outright: this project promises fully
  local transcription with no API key.