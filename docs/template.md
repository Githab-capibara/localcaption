# Documentation style guide and templates

This is the canonical style guide for every page in `docs/`. It defines the two
document types, the naming rules, and — for reference — the templates that live
in each topic folder. Everything in `docs/` follows this guide.

## Document types

| Type | Purpose | Where it lives | Fields |
|---|---|---|---|
| **ADR** | A decision that was made, and why | `docs/adr/` | Michael Nygard format — see `docs/adr/template.md` |
| **Design document** | A mechanism, how it works, and how it feeds other docs | `docs/design/` and the topic folders (`networking/`, `models/`, `api/`, `operations/` — for the corresponding mechanisms) | see `docs/design/template.md` |
| **README** | Navigation table for a folder | `docs/README.md` (master index) and each folder's `README.md` | link table |
| **template** | One per folder, mirrors this guide locally | every folder | boilerplate to copy |

## Naming rules

- Every document (except `README.md`) is numbered `01-`, `02-`, … **restarting
  at 01 in each folder**.
- Filenames are **lowercase** (except `README.md`).
- The filename carries a short, descriptive title in 2–3 words (occasionally
  more) that says what the document is about — e.g. `03-bot-check-mitigation.md`.
- All documentation is written in **English**.
- Never use the word *report* or its translations in folder or document names.
  These are documentation pages, not reports.
- Every folder contains exactly two management files: `README.md` (its
  navigation index) and `template.md` (the local copy of the template for the
  document type in that folder).

## Writing rules

- One mechanism per document. Split large mechanisms into several pages
  (e.g. the network layer has one page per concern: proxy, Tor rotation,
  bot-check mitigation, cookies).
- Reference `file:line`-free: describe behaviour by module name
  (`src/localcaption/network.py`), not by unstable line numbers.
- Every claim should mirror the code. When code and prose drift, the prose is
  the bug — fix it.
- Use the exact strings and constants from the source (thresholds, env-var
  names, model keys, exit codes).
- If a document builds on another, link it. The master index is
  `docs/README.md`.

## ADR template (Michael Nygard)

Mirrored in `docs/adr/template.md`. The title is a short, present-tense,
imperative sentence stating the decision. The header block:

```markdown
# Title: <imperative statement of the decision>

Status: <Proposed | Accepted | Deprecated | Superseded by ADR-NNN>
Date: <YYYY-MM-DD>
Deciders: <people or roles who decided>
Related: <links to ADRs / design docs this builds on or conflicts with>
```

Body sections:

```markdown
## Context
...the forces at play, the problem, and what we considered mandatory...

## Decision
...what we decided to do — the technical guidance anyone implementing or
maintaining this must follow...

## Consequences
Positive:
- ...
Negative / trade-offs:
- ...

## Alternatives considered
- Alternative ...
- ...and why it was rejected.
```

## Design document template

Mirrored in `docs/design/template.md`. Documents a mechanism as a research note.

```markdown
# <Mechanism name>

Status: Research note
Date: <YYYY-MM-DD>
Deciders: <roles>
Researcher: <roles>
Purpose: <short for-me boardmembers: what this doc establishes>
Feeds into: <links to ADRs, design docs, or other folders that build on this>
```

Then free-form sections, plain Markdown, tables for constants and options,
snippets for output shapes. Use "Mechanism" framing: `## Flow`, `## Constants`,
`## Output shape`, `## Failure modes`.

## Maintenance

- When a mechanism changes, update its design document and any ADR it
  supersedes in the same PR.
- When the `docs/` tree is touched, re-check `docs/README.md` "Directory map"
  and every folder `README.md` link table.