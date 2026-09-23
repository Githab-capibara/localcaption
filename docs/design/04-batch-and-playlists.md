# Batch processing and playlists

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: Documents `--batch` semantics and how playlist URLs are detected,
expanded and resumed.
Feeds into: [design/01-pipeline-stages.md](01-pipeline-stages.md),
[../api/01-command-line-interface.md](../api/01-command-line-interface.md)

## Flow

Two entry points share the per-item machinery:

- CLI `--batch FILE` → `src/localcaption/cli.py::_run_batch`
  → `src/localcaption/batch.py::transcribe_urls(read_url_list(path), …)`.
- CLI single URL with `&list=` / `&playlist=` → `batch.transcribe_urls` with
  the expanded list (via `src/localcaption/playlist.py::expand_playlist`).

### URL list parsing

`batch.read_url_list` skips blank lines and `#` comments, decodes UTF-8
(with BOM tolerance), and resolves local paths `~` and relative to the list
file's directory.

### Item identity

`batch.video_id_for`:

- YouTube URLs → the 11-char video id
  (`youtube.com/watch?v=…`, `/embed/`, `/shorts/`, `/live/`, `/v/`, `youtu.be`).
- Local files → a sanitised id derived from the path (`audio.mp3` in
  `show1/` vs `show2/` produces different ids).
- Other URLs → `host_path`-style id (`vimeo.com_148751763`),
  `www.` stripped.

### Playlist expansion

`playlist.has_playlist_query` is true when the query carries `list` or
`playlist`; playlist URLs are **never** detected for local paths (even a
filename containing `list=`). `expand_playlist` runs yt-dlp with
`extract_flat="in_playlist"`, `skip_download=True`, no download, quiet logger,
and an `outtmpl` that yields playlist index / id / title / webpage URL per
entry. Expansion respects the same cookies/proxy resolution as downloads.

### Per-item run and resume

`batch._transcribe_one` writes into `out_dir/<videoId>/…`. If
`out_dir/<videoId>/<videoId>.md` already exists the item is **skipped** (the
non-md equivalent `<videoId>.txt` mark is the readme-documented behaviour).
Sequential by design: a single model already saturates the machine.

## Constants

| Constant | Value |
|---|---|
| YouTube id regex | 11 chars `[A-Za-z0-9_-]` |
| playlist query params | `list`, `playlist` |
| flat-playlist mode | `extract_flat="in_playlist"` |
| default out dir | `./transcripts` |
| `--playlist-limit N` default | unset (all videos) |

## Output shape

`BatchResult{items, wall_clock_s}`: per item `source`, `video_id`,
`status` (`ok`/`failed`/`skipped`), `duration_s`, `elapsed_s`, `error`.
`summary()` renders a table with totals; `exit_code()` is **0** when nothing
failed (skips count as success), **1** otherwise.

`PlaylistInfo{playlist_id, title, entry_count, urls}` — the expanded entry
list in playlist order.

## Failure modes

- `expand_playlist` failure → `PlaylistError` (not a playlist / zero videos /
  extractor error) → CLI exits 1 for that URL.
- A failed item does not stop the batch: the next item still runs, and the
  process exits 1 at the end.
- Batch file missing → exit 1; URL and `--batch` together → argparse exit 2;
  neither → exit 2 (`provide a URL/file or --batch FILE`).