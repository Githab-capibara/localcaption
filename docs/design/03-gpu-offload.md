# GPU offload

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: Documents the shared device-map planner used by every ASR runner so
a small or busy GPU degrades gracefully to CPU.
Feeds into: [design/02-model-selection.md](02-model-selection.md),
[../models/02-isolated-runtimes.md](../models/02-isolated-runtimes.md)

## Flow

`src/localcaption/runners/_offload.py::offload_kwargs(model_dir)` computes a
`device_map` once per invocation, before the runner loads its checkpoint:

1. **No GPU** (`torch.cuda.mem_get_info` free ≤ 0, or torch/CUDA unavailable)
   → `{"device_map": "cpu"}`.
2. **Fits whole GPU** (weights known and `free >= weight`)
   → `{"device_map": "cuda:0"}`.
3. **Partial split** → `{"device_map": "auto", "max_memory": {0: int(free * 0.8),
   "cpu": 100 * 1024**3}}` — the GPU budget is **80 % of free VRAM**, leaving
   ≈ 20 % headroom for transformers' `caching_allocator_warmup` (which
   pre-allocates roughly half the model's GPU weights); the CPU budget is
   100 GiB.

Weights are summed from `model.safetensors` / `.bin` / `.pt` / `.ckpt` files
in the model directory (`model_weight_bytes`). Unknown checkpoint size with
free VRAM still splits (`device_map: auto`).

Each runner threads the plan in: Qwen3-ASR via `from_pretrained(**plan)`;
Parakeet via `pipeline(..., model_kwargs=plan)` (it must go through
`model_kwargs` or `max_memory` is silently dropped); Nemotron via
`AutoModelForRNNT.from_pretrained(**plan)`.

## Constants

| Constant | Value |
|---|---|
| GPU weight headroom | `int(free * 0.8)` |
| CPU memory budget | `100 * 1024**3` bytes (100 GiB) |
| `model.safetensors` min size | `1_000_000` bytes |

## Output shape

`offload_kwargs` returns one of `{"device_map": "cpu"}`,
`{"device_map": "cuda:0"}`, or `{"device_map": "auto",
"max_memory": {0: ..., "cpu": ...}}`. Runners print
`loading Parakeet on cpu` / `loading Nemotron: partial GPU/CPU split, GPU
slice <n> MiB` variants at load time.

## Failure modes

- CUDA OOM while splitting → the runner **re-loads fully on CPU** and the run
  still finishes (a stderr message explains it is slower). This is a
  per-runner decision; the pipeline never swaps ASR models on OOM
  (`tests/test_offload.py` pins both).
- No torch in the runner env → offload degrades to `"cpu"` without raising.