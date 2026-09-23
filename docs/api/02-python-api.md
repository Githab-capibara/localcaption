# Python API

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: The public Python surface beyond the CLI.
Feeds into: [../design/01-pipeline-stages.md](../design/01-pipeline-stages.md),
[../design/04-batch-and-playlists.md](../design/04-batch-and-playlists.md)

## Functions

### `localcaption.pipeline.transcribe_url`

```python
transcribe_url(
    url: str,
    *,
    out_dir: Path,
    language: str = "auto",
    force_model: str | None = None,
    keep_intermediate: bool = False,
    stem: str | None = None,
    summary: bool = False,
    summary_model: str = DEFAULT_SUMMARY_MODEL,      # "llama3.1:8b"
    summary_prompt: Path | None = None,
    output_format: str = "md",
    cookies: str | None = None,
    proxy: str | None = None,
    force_rotate: bool = False,
) -> PipelineResult
```

The full pipeline for one URL or local file. See
[../design/01-pipeline-stages.md](../design/01-pipeline-stages.md) for stage
order and output names.

### `localcaption.batch`

```python
read_url_list(path: Path) -> list[str]
transcribe_urls(urls: list[str], *, out_dir: Path,
    language="auto", force_model=None, keep_intermediate=False,
    cookies=None, proxy=None, force_rotate=False) -> BatchResult
video_id_for(source: str) -> str
```

`read_url_list` skips blanks/`#` comments, expands `~` and resolves local
paths against the list file's directory. `transcribe_urls` runs items
sequentially into `out_dir/<videoId>/`, skipping already-done videos (see
[../design/04-batch-and-playlists.md](../design/04-batch-and-playlists.md)).

## Dataclasses

| Class | Fields | Notes |
|---|---|---|
| `PipelineResult` | `source_url`, `audio_path`, `wav_path`, `transcripts`, `duration_s`, `summary`, `chapters_json`, `chaptered_md` | `.language`, `.model` delegate to transcripts; audio paths are `None` unless `keep_intermediate` |
| `TranscriptionResult` | `txt`, `srt`, `vtt`, `json`, `md`, `language="und"`, `model=""` | `.existing()` returns only present paths |
| `BatchItem` | `source`, `video_id`, `status` (`ok`/`failed`/`skipped`), `duration_s`, `elapsed_s`, `error` | |
| `BatchResult` | `items`, `wall_clock_s` | `.summary()`, `.exit_code()` (0 unless a failure) |
| `LangIdResult` | `code`, `name`, `score`, `scores` | `.confident` (`score >= 0.6`) |

## Example

```python
from pathlib import Path
from localcaption.pipeline import transcribe_url

result = transcribe_url("https://youtu.be/PSRJfaAYkW4", out_dir=Path("transcripts"))
print(result.language, result.model)
print(result.transcripts.md.read_text())
```