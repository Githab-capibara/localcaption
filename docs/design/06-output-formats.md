# Output formats

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: Documents the serialisation layer: which artefacts exist per run,
their exact shapes, and the default-mode nuances.
Feeds into: [design/01-pipeline-stages.md](01-pipeline-stages.md),
[design/05-chapters-and-search.md](05-chapters-and-search.md)

## Flow

`src/localcaption/asr.py::transcribe` writes artefacts through
`formats.write_*(...)`. The selection is `--output-format
{md,txt,srt,vtt,json,all}` (choices in `asr.SUPPORTED_OUTPUT_FORMATS`);
`all`/`full`/`complete` emit every format. The default is a single `md`.

In `md` mode (default), a YouTube source's chapters are folded directly into
the `.md` — this is why the default run produces **no**
`.chapters.json`/`.chaptered.md` (see [design/05](05-chapters-and-search.md)).
With any other format, chapter sidecars are written instead.

## Constants

| Writer | Format | Details |
|---|---|---|
| `write_txt` | `.txt` | plain text, rstrip + trailing newline |
| `write_md` | `.md` | transcript body; when timed segments exist appends `## Timestamps` with ``- `HH:MM:SS,mmm` — text`` lines |
| `write_srt` | `.srt` | indexed cues `N\nHH:MM:SS,mmm --> HH:MM:SS,mmm\n<text>`, blank-line separated; whitespace-only segments skipped |
| `write_vtt` | `.vtt` | `WEBVTT` header + dot milliseconds `HH:MM:SS.mmm` |
| `write_json` | `.json` | `{"model", "role": "", "language", "language_name", "text", "segments": [{"start","end","text"}]}`, indented, `ensure_ascii=False` |

Clock helpers: `formats._clock(seconds, vtt=True)` switches `,` ↔ `.`; SRT
uses comma, VTT uses dot. `chapters.format_timestamp` renders chapter
headings as `MM:SS` (or `H:MM:SS` ≥ 1 h).

## Output shape

For source `<stem>` and default `--output-format md`:

```
<out>/<stem>.md          <- the single default artefact
<out>/<stem>.txt|srt|vtt|json   <- only on --output-format
<out>/<stem>.chapters.json + chaptered.md  <- chapters present AND fmt != md
<out>/<stem>.summary.md  <- only with --summary
```

Filename stems keep dots intact (`output_file` never strips them), so
`ep.12` produces `ep.12.md` — and the ASR JSON / SRT / chapter sidecars keep
the full dotted stem.

## Failure modes

- Writer failures are ordinary `OSError` surfaces (they propagate as errors
  from the ASR stage).
- An empty segment list still yields a valid empty/whitespace text or VTT
  `WEBVTT` header; empty SRT cues are dropped and numbering re-starts at 1.