#!/usr/bin/env python3
"""Qwen3-ASR runner (executes inside the ``qwen`` virtualenv).

Loads a local Qwen3-ASR checkpoint and transcribes a 16 kHz mono WAV in
fixed windows, emitting timed segments.

Device policy: the model is loaded with a *partial* GPU/CPU device map —
whatever slice of the weights fits in the free VRAM stays on the GPU and
the overflow is pinned in host RAM, streamed to the GPU block-by-block.
When the GPU has nothing free the whole model runs on CPU. If the split
plan still OOMs at allocation time we fall back to a full CPU load.
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

# Qwen3-ASR accepts full language names; None lets it auto-detect.
QWEN_LANGUAGE_NAMES = {
    "ru": "Russian",
    "en": "English",
    "zh": "Chinese",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "tr": "Turkish",
    "ar": "Arabic",
}


def _load_model(model_dir: str, torch):
    from _offload import offload_kwargs
    from qwen_asr import Qwen3ASRModel

    kwargs = dict(
        pretrained_model_name_or_path=model_dir,
        dtype=torch.float32,
        max_inference_batch_size=1,
        max_new_tokens=1024,
    )
    plan = offload_kwargs(model_dir)
    if "max_memory" in plan:
        print(
            f"loading Qwen3-ASR: partial GPU/CPU split, "
            f"GPU slice {plan['max_memory'][0] // (1024 * 1024)} MiB",
            flush=True,
        )
    else:
        print(f"loading Qwen3-ASR on {plan.get('device_map')}", flush=True)

    try:
        model = Qwen3ASRModel.from_pretrained(**plan, **kwargs)
    except torch.OutOfMemoryError:
        # The split plan still OOMed on allocation (VRAM shrank between the
        # measurement and the load). Fall back to a full CPU load.
        print(
            "CUDA out of memory splitting Qwen3-ASR; re-loading fully on CPU "
            "(slower, but the run still finishes)",
            file=sys.stderr,
            flush=True,
        )
        model = Qwen3ASRModel.from_pretrained(device_map="cpu", **kwargs)

    return model


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--model-key", default="")
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--language", default="auto")
    ap.add_argument("--window", type=float, default=45.0)
    ap.add_argument("--max-windows", type=int, default=0)
    args = ap.parse_args()

    import logging

    import torch

    logging.getLogger("transformers").setLevel(logging.ERROR)

    model = _load_model(args.model, torch)
    forced = QWEN_LANGUAGE_NAMES.get(args.language.lower())
    print(f"language hint: {forced or 'auto'}")

    samples = read_wav16k(args.wav)
    segments: list[dict[str, object]] = []
    texts: list[str] = []
    detected = forced or "undetermined"

    for start, end, chunk in iter_windows(samples, args.window):
        try:
            results = model.transcribe(audio=(chunk, SAMPLE_RATE), language=forced)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"  window {start:.1f}-{end:.1f}s failed: {exc}", flush=True)
            continue
        if not results:
            continue
        result = results[0]
        text = (getattr(result, "text", "") or "").strip()
        if getattr(result, "language", None):
            detected = result.language
        if not text:
            continue
        texts.append(text)
        segments.append({"start": round(start, 3), "end": round(end, 3), "text": text})
        print(f"  window {start:6.1f}-{end:6.1f}s -> {len(text)} chars")

    payload = {
        "text": " ".join(texts).strip(),
        "language": _normalize(detected),
        "model": args.model_key or "qwen3-asr-0.6b",
        "segments": segments,
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"done: {len(texts)} windows, {len(payload['text'])} chars")
    return 0


_CODE_BY_NAME = {
    "russian": "ru",
    "english": "en",
    "chinese": "zh",
    "german": "de",
    "french": "fr",
    "spanish": "es",
    "italian": "it",
    "japanese": "ja",
    "korean": "ko",
    "portuguese": "pt",
    "turkish": "tr",
    "arabic": "ar",
}


def _normalize(language: str) -> str:
    return _CODE_BY_NAME.get(str(language).strip().lower(), str(language).strip().lower())


if __name__ == "__main__":
    raise SystemExit(main())
