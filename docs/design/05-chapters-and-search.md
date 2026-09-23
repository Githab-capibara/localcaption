# Chapters and the search index

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: Documents how YouTube chapter markers are captured, folded into
Markdown, and how the JSONL search index is built and ranked.
Feeds into: [adr/04-jsonl-search-index.md](../adr/04-jsonl-search-index.md),
[design/01-pipeline-stages.md](01-pipeline-stages.md),
[../api/01-command-line-interface.md](../api/01-command-line-interface.md)

## Flow

### Chapters (`src/localcaption/chapters.py`)

1. `chapters_from_info(info)` reads yt-dlp's `info["chapters"]`, skipping
   entries without a valid numeric `start_time`, defaulting titles to
   `Chapter <n>`, and back-filling missing `end_time` from the next chapter's
   start.
2. In the default single-`.md` mode the chapters are folded into the Markdown
   as `## MM:SS Title` headings, with transcript segments bucketed into the
   chapter whose `start_time ≤ segment.start`.
3. In any other output format the pipeline writes `<stem>.chapters.json`
   (array of `{"title","start_time","end_time"}`, indented, `ensure_ascii=False`)
   and `<stem>.chaptered.md` alongside; the fallback text is the `.txt` when
   it exists.

SRT segment parsing (`_segments_from_srt`, used by chaptered markdown and the
search index when no sibling `.json` exists): blocks split on blank lines; the
timestamp line is the first line containing `-->`; the regex accepts `,` or
`.` millisecond separators with exactly 3 digits; untimed or empty blocks are
skipped. Clock parsing normalises `H:M:S` / `M:S` / plain floats.

### Search index (`src/localcaption/index.py`)

- One JSONL row per video: `id`, `url`, `title`, `duration`, `language`,
  `model`, `chapters`, `transcript` (path). Upsert by `id`, atomic
  `.tmp` + `replace` write (see [adr/04](../adr/04-jsonl-search-index.md)).
- Timestamps come from the sibling `<stem>.json` (preferred) or `.srt` via
  `load_segments`; dotted stems are preserved (`ep.12.txt` finds
  `ep.12.json`). With no timed artefact, search falls back to a synthetic
  untimed segment per transcript line.

`localcaption search <term>` (`src/localcaption/cli.py::_cmd_search`): a
case-insensitive substring scan, ranked `(-score, id, start)`. Scored as:

| Hit | score |
|---|---|
| chapter title hit | `count + title_bonus + 2`, text prefixed `[chapter] ` |
| transcript segment hit | `count + title_bonus` |
| title-only fallback | `title_bonus` |

## Constants

| Constant | Value |
|---|---|
| default index path | `~/.local/share/localcaption/index.jsonl` (XDG-derived; `LOCALCAPTION_INDEX_PATH` overrides) |
| index schema | `id, url, title, duration, language, model, chapters, transcript` |
| chapter heading | `## MM:SS Title` |
| back-fill rule | missing `end_time` ← next chapter start |

## Output shape

- `<stem>.chapters.json` / `<stem>.chaptered.md` — only when chapters exist
  and output format ≠ `md`.
- Search hit line: `<id>  <MM:SS or ---:-->  <matching text>`, title on an
  indented second line. No matches → exit 1 with `No matches for …`.

## Failure modes

- Corrupt index rows (non-dict, unparseable JSON, garbage) are skipped on
  rewrite and search, never fatal (`test_index.py`,
  `test_pipeline.py::test_corrupt_index_does_not_fail_run`).
- Index upsert failure → warning only, run still succeeds.
- Unreadable chapter artefacts → warning `could not write chapter files`.