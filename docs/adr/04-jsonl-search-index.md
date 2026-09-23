# Title: Store the search index as upserted JSONL

Status: Accepted
Date: 2026-09-22
Deciders: Maintainer
Related: [design/05-chapters-and-search.md](../design/05-chapters-and-search.md), [api/03-configuration.md](../api/03-configuration.md)

## Context

`localcaption search <term>` needs to grep past transcripts with timestamps,
ranked, without a database or a service. Transcripts accumulate one file set
per video; we needed an index that is cheap to write, easy to inspect, atomic
to update, and tolerant of corruption (transcripts live on user disks).

## Decision

Use a **JSONL file** (`src/localcaption/index.py`):

- Default path `~/.local/share/localcaption/index.jsonl` (XDG-derived),
  override `LOCALCAPTION_INDEX_PATH`.
- One JSON object per row: `id`, `url`, `title`, `duration`, `language`,
  `model`, `chapters`, `transcript` (path to the `.txt`/`.md` artefact).
- `upsert_index` replaces the row whose `id` matches and writes atomically via
  a sibling `.tmp` file + `replace()` — a crashed write never corrupts the
  index.
- Search is a case-insensitive substring over transcript segments and chapter
  titles, ranked by hit count with a title boost; timestamps come from the
  sibling `.json`/`.srt` when present (`search_index`, `SearchHit`).

## Consequences

Positive:
- Zero-dependency, greppable, human-readable; `sort`/`jq` compatible.
- Re-running a video upserts in place (idempotent re-transcription).
- Malformed or non-dict rows are skipped, not fatal.

Negative / trade-offs:
- Single process writes at a time — fine for a single-user CLI.
- Literal text search, not a real full-text engine (no stemming, no
  daemon).

## Alternatives considered

- SQLite — heavier dependency and an on-disk format users can't `grep`;
  overkill for a single-user transcript index.
- Grepping transcript files directly — no title metadata, no ranking, no
  upsert, no deletion semantics.