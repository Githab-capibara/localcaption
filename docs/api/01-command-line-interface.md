# Command-line interface

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: The full CLI reference — subcommands, flags, defaults, exit codes.
Feeds into: [../design/04-batch-and-playlists.md](../design/04-batch-and-playlists.md),
[../models/01-model-registry.md](../models/01-model-registry.md)

## Entry point

Console script `localcaption` (`pyproject.toml [project.scripts]`) and
`python -m localcaption`, both → `src/localcaption/cli.py::main`.

## Subcommands

| Invocation | What it does |
|---|---|
| `localcaption <url-or-file>` | **Default** — transcribe. |
| `localcaption transcribe <url-or-file>` | Explicit alias of the default. |
| `localcaption doctor [--fix]` | Read-only diagnostics; `--fix` repairs. |
| `localcaption model list` | List models: key, role, size, status. |
| `localcaption model info <key>` | Metadata for one model. |
| `localcaption model download <key> \| --all` | Download (resumable); `--force`, `-y`. |
| `localcaption model rm <key>` | Remove (aliases `remove`, `delete`); `-y`. |
| `localcaption search <term>…` | Search past transcripts (exit 1 if none). |
| `localcaption help` / `--help-all` | Top-level help, exit 0. |

## transcribe flags

| Flag | Default | What it does |
|---|---|---|
| `url` (positional) or `--batch FILE` | — | exactly one required; providing both or neither exits 2 |
| `-o`, `--out` | `transcripts` | output directory |
| `-l`, `--language` | `auto` | ISO code or language name, or `auto` to detect |
| `--model KEY` | unset | force an ASR model key, skip routing |
| `--output-format` | `md` | `md`\|`txt`\|`srt`\|`vtt`\|`json`\|`all` |
| `--keep-audio` | off | keep `out/.work/` audio + WAV |
| `--no-print` | off | don't echo the transcript to stdout |
| `--cookies BROWSER_OR_FILE` | auto | cookie source (browser name or Netscape file) |
| `--no-proxy` | off | bypass `LOCALCAPTION_PROXY` for this run |
| `--rotate-tor` | off | force a fresh Tor circuit before downloading |
| `--no-playlist` | off | transcribe only the first video of a playlist URL |
| `--playlist-limit N` | unset | transcribe only the first N videos |
| `--auto-download` | off | download missing models without prompting |
| `--summary` | off | write `<stem>.summary.md` via local Ollama |
| `--summary-model` | `llama3.1:8b` | Ollama model for `--summary` |
| `--summary-prompt PATH` | built-in | prompt template; `{transcript}` placeholder |
| `-V`, `--version` | — | print version, exit 0 |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success, or all items ok/skipped; `help`/`--help` |
| 1 | runtime failure: doctor gaps, model rm missing, missing batch file, batch failures, search no-match, playlist expansion error |
| 2 | usage error: bare invocation, unknown model subcommand/`info` key, `download` without key/`--all`, URL + batch, neither URL nor batch |
| 130 | interrupted (`KeyboardInterrupt`) |

## Examples

```bash
localcaption "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
localcaption ./talk.mp4 --language ru
localcaption --batch urls.txt -o transcripts/
localcaption "..." --summary --summary-model mistral
localcaption model download --all --yes
localcaption search "ffmpeg"
```