# Design documents

Research-note design documents for the mechanisms that make up `localcaption`.
Each page describes one mechanism: flow, constants, output shapes, failure
modes. They feed the ADRs in [../adr/](../adr/README.md) and the operational
pages in [../networking/](../networking/README.md),
[../models/](../models/README.md), [../api/](../api/README.md) and
[../operations/](../operations/README.md).

| # | Design | What it establishes |
|---|---|---|
| [01-pipeline-stages](01-pipeline-stages.md) | The end-to-end run: download → re-encode → language ID → routed ASR → artefacts | What files come out and where |
| [02-model-selection](02-model-selection.md) | The four checkpoints, their roles, and the routing table | Why exactly these models, sizes, and a 1 MB completeness heuristic |
| [03-gpu-offload](03-gpu-offload.md) | Device-map planning for GPU/CPU offload | 80 % headroom rule, 100 GiB CPU budget, OOM fallback |
| [04-batch-and-playlists](04-batch-and-playlists.md) | `--batch` and playlist URL expansion | YouTube id naming, skip-if-done, exit codes, timing |
| [05-chapters-and-search](05-chapters-and-search.md) | YouTube chapters and the JSONL search index | Chapter folding, SRT parsing, index schema, ranking |
| [06-output-formats](06-output-formats.md) | Serialisation: `.md` / `.txt` / `.srt` / `.vtt` / `.json` | Defaults, clock formats, chapter folding, summary input |

Template: [template.md](template.md) (canonical copy: [../template.md](../template.md)).