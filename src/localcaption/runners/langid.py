#!/usr/bin/env python3
"""Language-ID runner (executes inside the ``langid`` virtualenv).

Prints progress to stdout and writes a JSON manifest to ``--out``:

    {"name": "Russian", "score": 0.97, "scores": {"Russian": 0.97, ...}}
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wavio import iter_windows, read_wav16k  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="local model directory")
    ap.add_argument("--model-key", default="")
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--language", default="auto")
    ap.add_argument("--window", type=float, default=6.0)
    ap.add_argument("--max-windows", type=int, default=16)
    args = ap.parse_args()

    import torch

    # Silence speechbrain's loggers *before* the model load. The
    # label-encoder deserialisation inside from_hparams re-reads SB_LOG_LEVEL
    # (set in runner_env) via get_logger; the env var is the reliable switch
    # because get_logger mutates os.environ on first call. Keep these as a
    # backup for direct (non-pipeline) invocations.
    for name in (
        "speechbrain",
        "speechbrain.dataio.encoder",
        "speechbrain.utils.logger",
    ):
        logging.getLogger(name).setLevel(logging.ERROR)
    from _offload import offload_kwargs
    from speechbrain.inference import EncoderClassifier

    savedir = Path(args.model) / ".speechbrain"
    plan = offload_kwargs(args.model)
    if "max_memory" in plan:
        device = "cuda:0"
        gpu_mib = plan["max_memory"][0] // (1024 * 1024)
    elif plan.get("device_map") == "cuda:0":
        device = "cuda:0"
        gpu_mib = 0
    else:
        device = "cpu"
        gpu_mib = 0
    print(f"loading language-ID model: {args.model} (device {device}, GPU slice {gpu_mib} MiB)")
    # The checkpoint's hyperparams.yaml references its files through the
    # ``pretrained_path`` ref (a Hugging Face repo id). Point that ref at our
    # local directory so nothing is fetched at load time.
    try:
        classifier = EncoderClassifier.from_hparams(
            source=args.model,
            savedir=str(savedir),
            overrides={"pretrained_path": args.model},
            run_opts={"device": device},
        )
    except Exception:
        if device == "cpu":
            raise
        print(
            "language-ID model failed on GPU; retrying on CPU "
            "(slower, but the run still finishes)",
            flush=True,
        )
        device = "cpu"
        classifier = EncoderClassifier.from_hparams(
            source=args.model,
            savedir=str(savedir),
            overrides={"pretrained_path": args.model},
            run_opts={"device": device},
        )

    samples = read_wav16k(args.wav)
    print(f"audio: {len(samples) / 16000:.1f}s, model dir: {args.model}")

    probs_sum: np.ndarray | None = None
    n = 0
    labels: list[str] = []
    with torch.no_grad():
        for start, end, chunk in iter_windows(
            samples, args.window, max_windows=args.max_windows
        ):
            tensor = torch.from_numpy(chunk).unsqueeze(0)
            out_prob, _score, _index, text_lab = classifier.classify_batch(tensor)
            probs = out_prob.squeeze(0).cpu().numpy()
            probs_sum = probs if probs_sum is None else probs_sum + probs
            labels = [str(x) for x in text_lab]
            n += 1
            print(f"  window {start:6.1f}-{end:6.1f}s -> {text_lab[0]}")

    if probs_sum is None or n == 0:
        raise SystemExit("no audio windows classified")

    probs = probs_sum / n
    best = int(np.argmax(probs))

    label_encoder = getattr(classifier.hparams, "label_encoder", None)
    names: list[str]
    try:
        ind2lab = label_encoder.ind2lab
        names = [ind2lab[i] for i in range(len(probs))]
    except Exception:
        names = labels if len(labels) == len(probs) else [f"class_{i}" for i in range(len(probs))]

    name = names[best] if best < len(names) else labels[0]
    scores = {
        names[i]: float(probs[i])
        for i in np.argsort(probs)[::-1][:5]
    }
    payload = {"name": name, "score": float(probs[best]), "scores": scores}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"detected: {name} (p={probs[best]:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
