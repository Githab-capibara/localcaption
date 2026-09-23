"""Shared GPU offload helpers for the standalone runner scripts.

These scripts execute *inside* a model's virtualenv, so they must not import
``localcaption``. This module only needs the stdlib plus whatever the env
already has (torch, optionally accelerate).

The core idea: instead of "all on GPU" or "all on CPU", use accelerate's
``device_map`` + ``max_memory`` to *split* a model. We measure free VRAM, cap
the GPU portion at that amount, and let the overflow stay pinned in host RAM.
When the GPU has (almost) nothing free, the cap is ~0 and the whole model
simply lands on CPU.

Decision (per model):

* free VRAM >= checkpoint size  -> whole model on GPU (``cuda:0``)
* free VRAM <  checkpoint size  -> partial split (``auto`` + ``max_memory``)
* free VRAM ~ 0                 -> whole model on CPU (``cpu``)
"""

from __future__ import annotations

import glob
from pathlib import Path


def model_weight_bytes(model_dir: str | Path) -> int:
    """On-disk size of the checkpoint's weight tensors (best-effort)."""
    total = 0
    for pattern in ("*.safetensors", "*.bin", "*.pt", "*.ckpt"):
        for path in glob.glob(str(Path(model_dir) / pattern)):
            try:
                total += Path(path).stat().st_size
            except OSError:
                continue
    return total


def free_vram_bytes() -> int:
    """Free VRAM on GPU 0 right now, in bytes. 0 when CUDA is unavailable."""
    try:
        import torch
    except ImportError:
        return 0
    if not torch.cuda.is_available():
        return 0
    try:
        free, _ = torch.cuda.mem_get_info(0)
    except Exception:
        return 0
    return int(free)


def offload_kwargs(model_dir: str | Path) -> dict:
    """``from_pretrained`` kwargs that spill overflow to CPU.

    Returns a dict to merge into ``from_pretrained(**kwargs)``:

    * GPU has enough room for the whole checkpoint -> ``{"device_map": "cuda:0"}``
      (everything on the GPU, the fast path).
    * GPU has some room but not all -> ``device_map="auto"`` +
      ``max_memory`` capping the GPU slice below free VRAM to leave headroom
      for transformers' caching_allocator_warmup, so the remainder of the
      weights live on CPU and are streamed to the GPU block-by-block.
    * GPU is empty -> ``{"device_map": "cpu"}`` (the whole model on CPU).
    """
    free = free_vram_bytes()
    weight = model_weight_bytes(model_dir)

    if free <= 0:
        return {"device_map": "cpu"}
    if weight > 0 and free >= weight:
        return {"device_map": "cuda:0"}

    # Partial fit: leave ~20% headroom for caching_allocator_warmup which
    # pre-allocates a buffer on GPU 0 sized at ~half the model's GPU weight.
    # The cap must be below free VRAM or the warmup OOMs.
    cap = int(free * 0.8)
    if cap <= 0:
        return {"device_map": "cpu"}

    return {
        "device_map": "auto",
        "max_memory": {0: cap, "cpu": 100 * 1024**3},
    }
