# Pipeline stages

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: Documents the end-to-end flow of a single `localcaption <url-or-file>`
run and the exact set of artefacts it produces.
Feeds into: [adr/01-language-routing.md](../adr/01-language-routing.md),
[design/04-batch-and-playlists.md](04-batch-and-playlists.md),
[design/05-chapters-and-search.md](05-chapters-and-search.md),
[design/06-output-formats.md](06-output-formats.md)

## Flow

`src/localcaption/pipeline.py::transcribe_url` orchestrates everything:

1. **Validate** — a forced `--model` key is checked up front
   (`models.get_model`).
2. **Work dir** — `out_dir/` is created, and an intermediate dir
   `out_dir/.work/` for downloaded audio and the WAV.
3. **Stage 1 · Resolve source** (`download.py`, `audio.py`):
   - Local file: used as-is; `info` is synthesized from the name.
   - URL: `download_audio(url, work_dir, …)` via yt-dlp
     (`bestaudio[acodec=opus]/bestaudio/best`), and playlist URLs are handled
     up-front by the CLI (see [design/04](04-batch-and-playlists.md)).
   - All downloader traffic goes through the SOCKS5 proxy; see
     [networking/*](../networking/README.md).
4. **Stage 2 · Re-encode** (`audio.py::to_wav`): `ffmpeg -y -loglevel error
   -i <src> -ac 1 -ar 16000 -vn -c:a pcm_s16le` → `<stem>.16k.wav` in the
   work dir. Duration is measured from the WAV.
5. **Stage 3 · Language ID** (`langid.py`): when language is `auto`, runs the
   `langid` runner (ECAPA-TDNN, 6 s windows, max 16, threshold 0.6). See
   [models/03-language-identification.md](../models/03-language-identification.md).
6. **Stage 4 · Routed ASR** (`asr.py::transcribe`): picks the model
   (`resolve_model`), runs its runner subprocess inside the model's venv, and
   writes the selected artefacts. See
   [design/02-model-selection.md](02-model-selection.md) and
   [design/06-output-formats.md](06-output-formats.md).
7. **Chapters** — when the source has chapters and the format is `md`, they
   are folded directly into the single `.md`; otherwise
   `<stem>.chapters.json` + `<stem>.chaptered.md` sidecars are written. See
   [design/05](05-chapters-and-search.md).
8. **Search index** — one JSONL row is upserted (warnings are non-fatal).
9. **Cleanup** — unless `--keep-audio`, `out_dir/.work/` is removed and the
   audio/WAV paths are nulled on the result.
10. **Optional summary** — with `--summary`, the transcript is POSTed to local
    Ollama and `<stem>.summary.md` is written. See
    [adr/05-local-ollama-summaries.md](../adr/05-local-ollama-summaries.md).

## Constants

| Constant | Value | Where |
|---|---|---|
| `TARGET_SAMPLE_RATE` | `16_000` | `audio.py` |
| `TARGET_CHANNELS` | `1` | `audio.py` |
| `WINDOW_SECONDS` | `45.0` | `asr.py` (ASR window) |
| `LANGID_WINDOW_SECONDS` | `6.0` | `langid.py` |
| `LANGID_MAX_WINDOWS` | `16` | `langid.py` |
| `LANGID_CONFIDENCE_THRESHOLD` | `0.6` (inclusive) | `langid.py` |
| default output format | `md` | `asr.py` |

## Output shape

For source `<stem>` and out dir `<out>` (default `./transcripts`):

| Artefact | Written when |
|---|---|
| `<out>/.work/<id>.<ext>` | downloaded audio (from yt-dlp), removed unless `--keep-audio` |
| `<out>/.work/<stem>.16k.wav` | intermediate WAV, same rule |
| `<out>/<stem>.md` | **default** single Markdown (chapters folded in if any) |
| `<out>/<stem>.txt` `.srt` `.vtt` `.json` | when `--output-format` selects them (or `all`) |
| `<out>/<stem>.chapters.json`, `.chaptered.md` | only when chapters exist **and** format ≠ `md` |
| `<out>/<stem>.summary.md` | only with `--summary` (Ollama reachable or not) |
| `~/.local/share/localcaption/index.jsonl` | every successful run (upsert by id) |

Batch/playlist runs nest artefacts under `<out>/<videoId>/<videoId>.*`.

Note: in the default `md` mode the pipeline's "transcript pointer" is the
`.md` file — the index row's `transcript` field and the `--summary` input both
refer to it. With `--output-format` producing `.txt`, that pointer is the
`.txt`.

## Failure modes

- Missing system tool → `DependencyError` (ffmpeg/yt-dlp/curl/runner missing).
- yt-dlp failure → `DownloadError` (with a special bot-check message — see
  [networking/03-bot-check-mitigation.md](../networking/03-bot-check-mitigation.md)).
- ffmpeg failure → `AudioConversionError`.
- ASR failure → `TranscriptionError`.
- Index/summary problems are warnings, never fatal.