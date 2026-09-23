#!/usr/bin/env python3
"""NVIDIA ASR runner (executes inside the ``nvidia`` virtualenv).

Handles both NeMo-family checkpoints we ship:

* ``parakeet-tdt-0.6b-v3`` — English, loaded through the transformers pipeline.
* ``nemotron-3.5-asr-streaming-0.6b`` — multilingual RNNT, loaded through
  ``AutoModelForRNNT`` with automatic language detection.

Both are loaded with a *partial* GPU/CPU device map: the slice of the weights
that fits in the free VRAM stays on the GPU, the overflow is pinned in host
RAM and streamed to the GPU block-by-block during inference. When the GPU has
nothing free the whole model simply runs on CPU. If the split plan still OOMs
at allocation time we fall back to a full CPU load.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wavio import (  # noqa: E402
    SAMPLE_RATE,
    iter_windows,
    read_wav16k,
)

PARAKEET = "parakeet-tdt-0.6b-v3"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--model-key", required=True)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--language", default="auto")
    ap.add_argument("--window", type=float, default=45.0)
    ap.add_argument("--max-windows", type=int, default=0)
    args = ap.parse_args()

    if args.model_key == PARAKEET:
        decode = _load_parakeet(args.model)
        lang = "en"
    else:
        decode = _load_nemotron(args.model)
        lang = "auto"

    samples = read_wav16k(args.wav)
    segments: list[dict[str, object]] = []
    texts: list[str] = []
    for start, end, chunk in iter_windows(samples, args.window):
        text = decode(chunk).strip()
        if not text:
            continue
        texts.append(text)
        segments.append({"start": round(start, 3), "end": round(end, 3), "text": text})
        print(f"  window {start:6.1f}-{end:6.1f}s -> {len(text)} chars")

    payload = {
        "text": " ".join(texts).strip(),
        "language": lang,
        "model": args.model_key,
        "segments": segments,
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"done: {len(texts)} windows, {len(payload['text'])} chars")
    return 0


def _load_parakeet(model_dir: str):
    import logging

    import torch
    from _offload import offload_kwargs
    from transformers import pipeline

    logging.getLogger("transformers").setLevel(logging.ERROR)
    plan = offload_kwargs(model_dir)
    if "max_memory" in plan:
        print(
            f"loading Parakeet: partial GPU/CPU split, "
            f"GPU slice {plan['max_memory'][0] // (1024 * 1024)} MiB",
            flush=True,
        )
    else:
        print(f"loading Parakeet on {plan.get('device_map')}", flush=True)

    try:
        # ``max_memory`` is not a named ``pipeline()`` kwarg; it must be
        # threaded through ``model_kwargs`` or it is silently dropped.
        pipe = pipeline(
            "automatic-speech-recognition",
            model=model_dir,
            model_kwargs=plan,
        )
    except torch.OutOfMemoryError:
        print(
            "CUDA out of memory splitting Parakeet; re-loading fully on CPU "
            "(slower, but the run still finishes)",
            file=sys.stderr,
            flush=True,
        )
        pipe = pipeline("automatic-speech-recognition", model=model_dir, device="cpu")

    def decode(chunk):
        out = pipe({"array": chunk, "sampling_rate": SAMPLE_RATE})
        if isinstance(out, list):
            out = out[0]
        return str(out.get("text", ""))

    return decode


def _load_nemotron(model_dir: str):
    import logging

    import torch
    from _offload import offload_kwargs
    from transformers import AutoModelForRNNT, AutoProcessor

    logging.getLogger("transformers").setLevel(logging.ERROR)
    plan = offload_kwargs(model_dir)
    if "max_memory" in plan:
        print(
            f"loading Nemotron: partial GPU/CPU split, "
            f"GPU slice {plan['max_memory'][0] // (1024 * 1024)} MiB",
            flush=True,
        )
    else:
        print(f"loading Nemotron on {plan.get('device_map')}", flush=True)

    processor = AutoProcessor.from_pretrained(model_dir)
    entry_device = _nemotron_entry_device(plan)
    try:
        model = AutoModelForRNNT.from_pretrained(model_dir, **plan)
    except torch.OutOfMemoryError:
        print(
            "CUDA out of memory splitting Nemotron; re-loading fully on CPU "
            "(slower, but the run still finishes)",
            file=sys.stderr,
            flush=True,
        )
        model = AutoModelForRNNT.from_pretrained(model_dir, device_map="cpu")
        entry_device = "cpu"
    model.eval()

    def decode(chunk):
        inputs = processor(chunk, sampling_rate=SAMPLE_RATE, language="auto", return_tensors="pt")
        # The RNNT decoder pins activations to one device; route inputs to
        # the device that hosts it (the model's entry point).
        inputs = {
            key: value.to(entry_device)
            for key, value in inputs.items()
            if hasattr(value, "to")
        }
        with torch.no_grad():
            output = model.generate(**inputs, return_dict_in_generate=True)
        sequences = getattr(output, "sequences", output)
        decoded = processor.decode(sequences, skip_special_tokens=True)
        if isinstance(decoded, list):
            decoded = decoded[0] if decoded else ""
        return str(decoded)

    return decode


def _nemotron_entry_device(plan: dict) -> str:
    """Device that hosts the Nemotron decoder (the generation entry point)."""
    if plan.get("device_map") == "cpu":
        return "cpu"
    # Whole-GPU or partial split: the decoder (tail of the map) lands on the
    # GPU whenever any slice fits there.
    return "cuda:0"


if __name__ == "__main__":
    raise SystemExit(main())
