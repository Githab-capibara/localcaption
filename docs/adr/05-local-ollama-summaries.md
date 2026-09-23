# Title: Summarise with a local Ollama, never a hosted LLM

Status: Accepted
Date: 2026-09-22
Deciders: Maintainer
Related: [design/01-pipeline-stages.md](../design/01-pipeline-stages.md), [api/01-command-line-interface.md](../api/01-command-line-interface.md)

## Context

Summaries are a nice-to-have on top of transcription. Adding them must not
violate the "no API keys, nothing leaves your machine" promise, must not add
heavy dependencies, and must never fail a transcription that otherwise
succeeded.

## Decision

Optional summaries via a **local Ollama** instance
(`src/localcaption/summary.py`):

- `--summary` posts the transcript to `http://localhost:11434/api/generate`
  (`DEFAULT_ENDPOINT`) with the default model `llama3.1:8b`
  (`DEFAULT_MODEL`), body `{"model", "prompt", "stream": false}`.
- Result is written to `<transcript stem>.summary.md` next to the transcript.
- Uses the stdlib `urllib` with an empty `ProxyHandler({})`, so the request
  deliberately ignores `HTTP(S)_PROXY` — Ollama is localhost.
- Every failure mode (unreachable, HTTP error, timeout, empty/invalid body)
  returns `None` with a warning; the CLI still exits 0. Transcripts are
  never modified.
- Prompt template lives in `src/localcaption/summary_prompt.txt`; override
  with `--summary-prompt PATH` (a `{transcript}` placeholder is substituted
  when present).

## Consequences

Positive:
- Summaries stay on localhost; no account, key, or upload.
- Zero new dependencies (stdlib HTTP client).
- Graceful degradation on a missing Ollama.

Negative / trade-offs:
- Requires the user to run Ollama separately for summaries.
- Summary latency scales with the model and transcript length.
- Result quality depends on the user-chosen local model.

## Alternatives considered

- Hosted summariser APIs — rejected: privacy promise and API keys.
- Embedding a summariser model in the project — heavy, duplicates the ASR
  runtime machinery for an optional feature.