#!/usr/bin/env python3
"""NVIDIA ASR runner (executes inside the ``nvidia`` virtualenv).

Handles both NeMo-family checkpoints we ship:

* ``parakeet-tdt-0.6b-v3`` — English, loaded through the transformers pipeline.
* ``nemotron-3.5-asr-streaming-0.6b`` — multilingual RNNT, loaded through
  ``AutoModelForRNNT`` with automatic language detection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wavio import SAMPLE_RATE, iter_windows, read_wav16k  # noqa: E402

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

    from transformers import pipeline

    logging.getLogger("transformers").setLevel(logging.ERROR)
    print(f"loading Parakeet model: {model_dir}")
    pipe = pipeline(
        "automatic-speech-recognition",
        model=model_dir,
        device="cuda:0",
    )

    def decode(chunk):
        out = pipe({"array": chunk, "sampling_rate": SAMPLE_RATE})
        if isinstance(out, list):
            out = out[0]
        return str(out.get("text", ""))

    return decode


def _load_nemotron(model_dir: str):
    import logging

    import torch
    from transformers import AutoModelForRNNT, AutoProcessor

    logging.getLogger("transformers").setLevel(logging.ERROR)
    print(f"loading Nemotron model: {model_dir}")
    processor = AutoProcessor.from_pretrained(model_dir)
    model = AutoModelForRNNT.from_pretrained(model_dir)
    model.eval()
    model = model.to("cuda")
    device = next(model.parameters()).device

    def decode(chunk):
        inputs = processor(
            chunk, sampling_rate=SAMPLE_RATE, language="auto", return_tensors="pt"
        )
        inputs = {
            key: value.to(device)
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


if __name__ == "__main__":
    raise SystemExit(main())
