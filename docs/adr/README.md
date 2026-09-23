# Architectural decision records

Decisions that shaped `localcaption`, written in the
[Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
format (present-tense title, Context / Decision / Consequences / Alternatives
considered). New decisions append the next `NN-` prefix at the top of this
table.

| # | Decision | Status | Date |
|---|---|---|---|
| [01-language-routing](01-language-routing.md) | Route ASR by detected language (ru → Qwen, en → Parakeet, else/unclear → Nemotron) | Accepted | 2026-09-22 |
| [02-isolated-model-runtimes](02-isolated-model-runtimes.md) | One virtualenv per model family (`runtime/`) because ASR stacks pin incompatible `transformers` versions | Accepted | 2026-09-22 |
| [03-proxy-first-networking](03-proxy-first-networking.md) | All outbound traffic through a SOCKS5 proxy, loopback excluded | Accepted | 2026-09-22 |
| [04-jsonl-search-index](04-jsonl-search-index.md) | JSONL search index, upserted per video, no database | Accepted | 2026-09-22 |
| [05-local-ollama-summaries](05-local-ollama-summaries.md) | Optional summaries via a local Ollama, never a hosted LLM | Accepted | 2026-09-22 |

Statuses: `Proposed` · `Accepted` · `Deprecated` · `Superseded by <NN-…>`.

Template: [template.md](template.md) (canonical copy: [../template.md](../template.md)).