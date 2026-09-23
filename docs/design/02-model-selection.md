# Model selection

Status: Research note
Date: 2026-09-22
Deciders: Maintainer, ASR reviewers
Researcher: Maintainer
Purpose: Documents the four-checkpoint registry, why each model was chosen,
and how the ML completeness heuristic protects against truncated downloads.
Feeds into: [adr/01-language-routing.md](../adr/01-language-routing.md),
[../models/README.md](../models/README.md)

## Flow

`src/localcaption/models.py` holds the `_REGISTRY` (a tuple of `ModelSpec`s).
Routing is decided before ASR: a forced `--model KEY` skips routing; otherwise
the detected language maps to a model (`asr.model_for_language`):

| Detected language / state | Model key |
|---|---|
| `ru` | `qwen3-asr-0.6b` |
| `en` | `parakeet-tdt-0.6b-v3` |
| other / unclear (score < 0.6) / forced | `nemotron-3.5-asr-streaming-0.6b` |

## Constants

| key | hf_repo | role | runtime env | approx size (MB) | files |
|---|---|---|---|---|---|
| `langid-ecapa` | `speechbrain/lang-id-commonlanguage_ecapa` | `language-id` | `langid` | 84 | `classifier.ckpt`, `embedding_model.ckpt`, `hyperparams.yaml`, `label_encoder.txt`, `config.json` |
| `qwen3-asr-0.6b` | `Qwen/Qwen3-ASR-0.6B` | `russian` | `qwen` | 1900 | `model.safetensors`, `config.json`, `generation_config.json`, `preprocessor_config.json`, `tokenizer_config.json`, `chat_template.json` |
| `parakeet-tdt-0.6b-v3` | `nvidia/parakeet-tdt-0.6b-v3` | `english` | `nvidia` | 2500 | `model.safetensors`, `config.json`, `generation_config.json`, `processor_config.json`, `tokenizer.json`, `tokenizer_config.json` |
| `nemotron-3.5-asr-streaming-0.6b` | `nvidia/nemotron-3.5-asr-streaming-0.6b` | `multilingual` | `nvidia` | 2600 | same set as parakeet |

Total ≈ 7 GB of weights. Each checkpoint is one directory under `models/`
(`LOCALCAPTION_MODELS_DIR`, default `<repo>/models`); downloads come from
`https://huggingface.co/<repo>/resolve/main/…`.

Why 0.6B: small enough to infer on CPU, still state of the art per niche, and
CUDA-accelerated when a GPU is present (see
[design/03-gpu-offload.md](03-gpu-offload.md)).

## Output shape

Checks and downloads:

- Installed = every file present **and** plausibly sized: the `> 1 MB` rule.
  `model.safetensors` must exceed `1_000_000` bytes; smaller configs just
  need `> 0` bytes (`models._LARGE_FILES`, `_file_ok`). A truncated
  safetensors counts as missing.
- Download: `curl -fL --retry 8 --retry-delay 4 --retry-all-errors -C -`
  — resumable — with `--proxy <LOCALCAPTION_PROXY>`, written to a `.part` file
  then atomically renamed. `download_model(key, force=False)` fetches only
  missing files; `model download --all` covers the registry.
- `models.require([...])` raises `LocalCaptionError` listing missing
  checkpoints before a run starts.

## Failure modes

- Unknown key → `LocalCaptionError` ("Unknown model … Run `localcaption model
  list`").
- Missing `curl` → `DependencyError`.
- Truncated file → treated as missing, re-downloaded next time.
- `model rm <key>` removes a directory (`LocalCaptionError` if not installed).