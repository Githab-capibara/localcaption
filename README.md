<div align="center">

<img src="docs/icons/localcaption.svg" alt="localcaption" width="56" height="56" /> 

# localcaption

Fully-local transcription for YouTube and local files. Language-ID routing, three specialist ASR models, SRT/VTT/JSON out. No API key.

<!-- Package -->
<p>
  <a href="https://pypi.org/project/localcaption/"><img src="https://img.shields.io/pypi/v/localcaption?logo=pypi&logoColor=white&color=%233775A9&cacheSeconds=300" alt="PyPI version"></a>
  <a href="https://pypi.org/project/localcaption/"><img src="https://img.shields.io/pypi/pyversions/localcaption?logo=python&logoColor=white&cacheSeconds=300" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/jatinkrmalik/localcaption?color=yellow" alt="License: MIT"></a>
</p>

<!-- Build -->
<p>
  <a href="https://github.com/jatinkrmalik/localcaption/actions/workflows/ci.yml"><img src="https://github.com/jatinkrmalik/localcaption/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/jatinkrmalik/localcaption/actions/workflows/release.yml"><img src="https://github.com/jatinkrmalik/localcaption/actions/workflows/release.yml/badge.svg" alt="Release"></a>
  <a href="https://github.com/pypa/hatch"><img src="https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg" alt="Hatch project"></a>
</p>

<!-- Community -->
<p>
  <a href="https://github.com/jatinkrmalik/localcaption/stargazers"><img src="https://img.shields.io/github/stars/jatinkrmalik/localcaption?style=flat&logo=github" alt="GitHub stars"></a>
  <a href="https://github.com/jatinkrmalik/localcaption/commits/main"><img src="https://img.shields.io/github/last-commit/jatinkrmalik/localcaption?logo=github" alt="Last commit"></a>
  <a href="https://github.com/jatinkrmalik/localcaption/issues"><img src="https://img.shields.io/github/issues/jatinkrmalik/localcaption" alt="Open issues"></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs welcome"></a>
</p>

```bash
pipx install localcaption && localcaption doctor --fix # to get started
```

</div>

> [!TIP]
> Local, offline transcription for YouTube, Vimeo, Twitch, Twitter/X, and [1000+ other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) via yt-dlp, plus any video or audio file on disk. Paste a URL or a path; get `.txt`, `.srt`, `.vtt`, and `.json` without an API key and without uploading audio to the cloud. A speechbrain language-ID model picks between [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-0.6B), [Parakeet TDT](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), and [Nemotron 3.5 ASR](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b).

`localcaption` is a tiny orchestrator over four stages:

| Stage | Tool |
|---|---|
| Download best audio | [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) (YouTube, Vimeo, Twitch, 1000+ sites) |
| Re-encode to 16 kHz mono WAV | [`ffmpeg`](https://ffmpeg.org/) |
| Detect the language | [`speechbrain`](https://speechbrain.github.io/) ECAPA-TDNN (45 languages) |
| Transcribe locally | Qwen3-ASR 0.6B · Parakeet TDT 0.6B v3 · Nemotron 3.5 ASR 0.6B |

Nothing is uploaded to a third-party service. No OpenAI / Google / DeepL keys
required. Unlike pasting a clip into ChatGPT or calling the Whisper API,
transcription stays on your laptop after the download.

![Pipeline overview](docs/diagrams/pipeline.png)

## Why localcaption

- **Offline models.** Audio is transcribed on your machine. No API key, no account.
- **Language routing.** A 45-language ID model sends Russian to Qwen3-ASR, English to Parakeet, and everything else to Nemotron.
- **URLs and local files.** Any URL [yt-dlp](https://github.com/yt-dlp/yt-dlp) supports, plus local `.mp4` / `.wav` / `.mp3` / similar.
- **Captions you can use.** One run writes a single `.md` by default (use `--output-format` for `.txt`/`.srt`/`.vtt`/`.json`/`all`).
- **Batch.** `--batch urls.txt` walks a list of URLs or files.
- **Chapters.** With `--output-format md` (default) YouTube chapter markers are folded into that single `.md`; other formats also emit `.chapters.json` and `.chaptered.md`.
- **Search.** `localcaption search <term>` greps past transcripts with timestamps.
- **Local summaries.** `--summary` talks to a local [Ollama](https://ollama.com), not a hosted LLM.
- **Proxy-first.** All network traffic (downloads, model fetches, child processes) can be routed through a SOCKS5 proxy.
- **`doctor --fix`.** Installs missing tools, builds the model runtimes, and downloads the checkpoints.

## Why three ASR models?

One model rarely wins everywhere. The 0.6B models below are small enough to
infer on CPU yet state-of-the-art for their niche — and run on the NVIDIA GPU
when available:

| Model | Role | Size | Why |
|---|---|---|---|
| [Qwen3-ASR 0.6B](https://huggingface.co/Qwen/Qwen3-ASR-0.6B) | Russian | ~1.9 GB | Best-in-class Russian WER at 0.6B |
| [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) | English | ~2.5 GB | Top of the Open ASR leaderboard |
| [Nemotron 3.5 ASR Streaming 0.6B](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b) | 40+ languages | ~2.6 GB | Multilingual catch-all fallback |
| [speechbrain lang-id-commonlanguage_ecapa](https://huggingface.co/speechbrain/lang-id-commonlanguage_ecapa) | routing | ~84 MB | 45-language classifier |

If the language is unclear (best posterior < 0.6), localcaption falls back to
the multilingual Nemotron model instead of guessing.

## Who this is for

- Podcasters and video folks who need SRT/VTT without uploading episodes.
- Researchers transcribing interviews or lectures they cannot send to a cloud API.
- Anyone who wants a YouTube transcript without logging into Google or pasting audio into ChatGPT.

## Install

### Prerequisites

- Python 3.10+
- `git`, `ffmpeg`, `curl` on your `$PATH`
  (macOS: `brew install ffmpeg`)

### Recommended: pipx (one line)

The most Pythonic install. [`pipx`](https://pipx.pypa.io) creates an isolated
virtualenv for `localcaption` and drops the console script on your `$PATH`,
so you can run `localcaption <url-or-file>` from anywhere without polluting your
system Python.

```bash
pipx install localcaption
```

The first time you run `localcaption <url-or-file>` it will tell you it can't find
the model runtimes. The fastest way to set everything up is to let
`localcaption` do it itself: build the runtimes and download the checkpoints:

```bash
localcaption doctor --fix
```

`doctor --fix` is idempotent and end-to-end: it installs missing system
tools (`ffmpeg`/`git`/`curl` via `brew`/`apt`), builds one isolated Python
runtime per model family, downloads the checkpoints, and re-runs the
diagnostics to confirm everything works.

Prefer to do it yourself?

```bash
# Option A: bootstrap script (also installs pipx + the localcaption package):
curl -fsSL https://raw.githubusercontent.com/jatinkrmalik/localcaption/main/scripts/install.sh | bash

# Option B: DIY. Build the runtimes and fetch the models, then verify:
bash scripts/setup_runtime.sh
localcaption model download --all
localcaption doctor
```

> 💡 The model runtimes live in `runtime/` and the checkpoints in `models/`
> (both overridable, see [Configuration](#configuration)). A full install is
> roughly 7 GB of weights, so the download takes a while on a slow link.

After install, verify everything is wired up:

```bash
localcaption doctor                # read-only diagnostic
localcaption doctor --fix          # diagnostic + auto-repair anything missing
```

### Uninstall

To completely remove `localcaption` and everything it installed (the
binary, the model runtimes, and the checkpoints):

```bash
# pipx + runtimes + models, with confirmation prompts:
curl -fsSL https://raw.githubusercontent.com/jatinkrmalik/localcaption/main/scripts/uninstall.sh | bash

# Or, if you cloned the repo:
bash scripts/uninstall.sh
```

Useful flags: `--dry-run` (preview), `--yes` (skip prompts),
`--keep-models` (uninstall the binary but keep the runtimes + checkpoints
for next time).

Sample output:

```
localcaption 0.4.1

System tools:
  ✅ python  (3.12.14)
  ✅ ffmpeg  (/usr/bin/ffmpeg)
  ✅ git     (/usr/bin/git)
  ✅ curl    (/usr/bin/curl)

Python dependencies:
  ✅ yt-dlp  (2026.08.19)

Network:
  ✅ proxy  (socks5h://127.0.0.1:9050 (reachable))

Model runtimes:
  ✅ langid  (torch, speechbrain)
  ✅ qwen    (torch, qwen_asr)
  ✅ nvidia  (torch, transformers)

Models:
  ✅ langid-ecapa (~84 MB)  (ECAPA-TDNN language identifier, 45 languages (routing))
  ✅ qwen3-asr-0.6b (~1.9 GB)  (Qwen3-ASR 0.6B — Russian (WER 5.13))
  ✅ parakeet-tdt-0.6b-v3 (~2.4 GB)  (NVIDIA Parakeet TDT 0.6B v3 — English (Open ASR #1))
  ✅ nemotron-3.5-asr-streaming-0.6b (~2.5 GB)  (NVIDIA Nemotron 3.5 ASR Streaming 0.6B — 40 languages)

All checks passed. You're good to go: localcaption <url-or-file>
```

If anything is missing, re-run with `--fix` and `localcaption` will build the
missing runtimes, download the missing checkpoints, then re-verify.

### Dev install (contributors)

If you're hacking on `localcaption` itself, install editable from a clone:

```bash
git clone https://github.com/jatinkrmalik/localcaption
cd localcaption
./scripts/setup.sh           # creates .venv, installs -e .[dev], builds runtime/
source .venv/bin/activate
pytest                        # the suite should pass
```

The dev setup keeps `runtime/` and `models/` inside the repo (so you can poke
at them) and editable-installs the package so source edits take effect
immediately.

## Usage

### CLI

```bash
# YouTube
localcaption "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Vimeo, Twitch, Twitter/X, and 1000+ other sites work too
localcaption "https://vimeo.com/148751763"

# Local video/audio files
localcaption /path/to/video.mp4
localcaption ./recording.wav

# Force a model and skip language detection
localcaption ./talk.mp4 --language ru

# Batch: one URL or local path per line (# comments and blank lines ignored)
localcaption --batch urls.txt -o transcripts/

# Transcript + local summary (requires a running Ollama)
localcaption "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --summary
localcaption ./talk.mp4 --summary --summary-model llama3.1:8b
```

| flag | default | what it does |
|---|---|---|
| `-o`, `--out` | `./transcripts` | output directory |
| `-l`, `--language` | `auto` | ISO code or language name, or `auto` to detect |
| `--model KEY` | routing | force a specific ASR model key, skip language routing |
| `--keep-audio` | off | keep the downloaded audio + intermediate WAV in `<out>/.work/` |
| `--no-print` | off | don't echo the transcript to stdout |
| `--auto-download` | off | download missing models without prompting |
| `--batch FILE` | off | transcribe each non-empty, non-`#` line in FILE sequentially |
| `--summary` | off | after transcription, write `<id>.summary.md` via local Ollama |
| `--summary-model` | `llama3.1:8b` | Ollama model used by `--summary` |
| `--summary-prompt` | built-in | path to a prompt template (`{transcript}` is replaced if present) |

Outputs a single `<id>.md` by default (use `--output-format txt|srt|vtt|json|all`
for the other formats). For local files, the output filename is derived from the
input file's name. With `--summary`, also writes `<id>.summary.md`. When the
source has chapter markers (typical on YouTube), they are folded into that single
`.md` (default); with other formats, also `<id>.chapters.json` and
`<id>.chaptered.md` are written.

`--batch FILE` writes each item into `<out>/<videoId>/` and skips any video
whose `.md` (or `.txt`, for non-md runs) is already there, so you can re-run a
list after a failure.
Local paths are relative to the list file (and `~` is expanded). The process
is sequential (a model already saturates the machine). Exit 0 if everything
succeeded or was skipped, 1 otherwise.

You can also invoke it as a module: `python -m localcaption <url-or-file>`.

### Summaries (optional)

If [Ollama](https://ollama.com) is running locally, `--summary` sends the
`.txt` transcript to `http://localhost:11434/api/generate` and writes
`<id>.summary.md` next to it. The built-in prompt asks for a TL;DR, key
points, notable quotes, and action items.

```bash
localcaption <url-or-file> --summary
localcaption <url-or-file> --summary --summary-model mistral
localcaption <url-or-file> --summary --summary-prompt ./my_prompt.txt
```

If Ollama isn't reachable, localcaption logs a warning and still exits 0.
The transcript files are unchanged.

### Subcommands

| Subcommand | What it does |
|---|---|
| _(default)_ `localcaption <url-or-file>` | Transcribe a URL or local video/audio file. |
| `localcaption doctor` | Read-only diagnostic: tools, proxy, runtimes, checkpoints. Useful before filing a bug. |
| `localcaption doctor --fix` | Self-heal: install missing tools, build the runtimes, download missing models, then re-verify. Idempotent. |
| `localcaption model list` | List every supported model with role + size + install status. |
| `localcaption model info <key>` | Show metadata about a single model. |
| `localcaption model download <key>` | Download a model (or `--all`) with resumable transfers. |
| `localcaption model rm <key>` | Remove an installed model to free disk space. |
| `localcaption search <term>` | Grep previously transcribed videos. Ranked matches with timestamps. |

### Search past transcripts

Each successful transcription upserts one JSON line in
`~/.local/share/localcaption/index.jsonl` (`id`, `url`, `title`, `duration`,
`language`, `model`, `chapters`, `transcript`). Re-running the same id replaces
that row. Override the path with `LOCALCAPTION_INDEX_PATH`.

```bash
localcaption search "install"
# vid123  02:30  First, let's install pip
#         Lecture on Python tooling
```

Search is a case-insensitive substring. Hits are ranked by how often the term
appears (title matches get a small boost). Timestamps come from the sibling
transcript `.json` or `.srt` when those files are still next to the `.txt`.

### Managing models

```bash
localcaption model list                  # see what's available
localcaption model info parakeet-tdt-0.6b-v3
localcaption model download qwen3-asr-0.6b
localcaption model download --all        # ~7 GB, resumable
localcaption model rm nemotron-3.5-asr-streaming-0.6b
```

For scripted/CI use, pass `--auto-download` to skip the in-run prompt:

```bash
localcaption --model parakeet-tdt-0.6b-v3 --auto-download "https://www.youtube.com/..."
```

| Model key | Role | Size |
|---|---|---|
| `langid-ecapa` | language routing | ~84 MB |
| `qwen3-asr-0.6b` | Russian | ~1.9 GB |
| `parakeet-tdt-0.6b-v3` | English | ~2.5 GB |
| `nemotron-3.5-asr-streaming-0.6b` | multilingual fallback | ~2.6 GB |

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `LOCALCAPTION_PROXY` | `socks5h://127.0.0.1:9050` | Proxy for **all** network traffic. Loopback is always excluded. |
| `LOCALCAPTION_MODELS_DIR` | `<repo>/models` | Where checkpoints are stored. |
| `LOCALCAPTION_RUNTIME_DIR` | `<repo>/runtime` | Where the per-model virtualenvs live. |
| `LOCALCAPTION_INDEX_PATH` | `~/.local/share/localcaption/index.jsonl` | Search index location. |

### Python API

```python
from pathlib import Path
from localcaption.pipeline import transcribe_url

result = transcribe_url(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    out_dir=Path("transcripts"),
    language="auto",     # or "ru" / "Russian" to skip detection
    summary=True,        # optional; writes .summary.md via local Ollama
)
print(result.language, result.model)
print(result.transcripts.md.read_text())
```

Batch from Python:

```python
from pathlib import Path
from localcaption.batch import read_url_list, transcribe_urls

result = transcribe_urls(
    read_url_list(Path("urls.txt")),
    out_dir=Path("transcripts"),
)
print(result.summary())
```

## Architecture

`localcaption` is intentionally tiny: an orchestrator (`pipeline.py`) drives
four single-responsibility stages, each wrapping one external tool. The ASR
stage routes to one of three models, each hosted by a standalone runner in an
isolated virtualenv.

### Module map

![Module architecture](docs/diagrams/architecture.png)

| Layer | Files | Responsibility |
|---|---|---|
| Entry points | `cli.py`, `__main__.py` | argparse, exit codes, stdout formatting |
| Orchestration | `pipeline.py`, `batch.py` | public Python API: `transcribe_url(...)`, `transcribe_urls(...)` |
| Pipeline stages | `download.py`, `audio.py`, `langid.py`, `asr.py`, `summary.py` | download, re-encode, language ID, routed ASR, optional Ollama summary |
| Model runners | `runners/` | `langid.py`, `qwen.py`, `nvidia.py` executed inside their own venv |
| Chapters & search | `chapters.py`, `index.py` | YouTube chapter sidecars + JSONL search index |
| Support | `models.py`, `runtime.py`, `network.py`, `paths.py`, `languages.py`, `formats.py`, `errors.py`, `_logging.py` | registry, runtimes, proxy policy, paths, language names, serialisation |

### Runtime sequence

End-to-end call flow for a single `localcaption <url>` invocation, including
the subprocess hops to yt-dlp, ffmpeg, and the model runner. The intermediate
`.work/` directory is cleaned up at the end unless `--keep-audio` is passed.

![Sequence diagram](docs/diagrams/sequence.png)

> Diagrams live in [`docs/diagrams/`](docs/diagrams) as Mermaid `.mmd` source
> files alongside the rendered PNGs. Regenerate with:
> ```bash
> mmdc -i docs/diagrams/<name>.mmd -o docs/diagrams/<name>.png \
>   -t default -b white --width 1600 --scale 2
> ```

## Notes

- The model runners execute on an NVIDIA GPU (`cuda:0`) via CUDA 12.6 build
  of PyTorch; the runtimes pin `+cu126` wheels so Maxwell (SM_5.2) cards keep
  working after CUDA 13 drops support. The `torch+cu126` wheels replace the
  old `+cpu` wheels in `runtime/{nvidia,qwen,langid}`.
- The first run in a fresh runtime loads several GB of weights; later runs are much faster.
- The pipeline accepts any URL `yt-dlp` supports (Vimeo, Twitch VODs, Twitter/X,
  podcast pages, and [1000+ more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)),
  not just YouTube.
- If you hit `HTTP 403 Forbidden`, your `yt-dlp` is probably stale.
  `pip install -U yt-dlp` usually fixes it.

## Roadmap

The roadmap lives on GitHub Issues so it's easy to track, comment on, and
contribute to:

👉 **[Open roadmap items](https://github.com/jatinkrmalik/localcaption/issues?q=is%3Aissue+is%3Aopen+label%3Aroadmap)**

**Have an idea?** Open a
[feature request](https://github.com/jatinkrmalik/localcaption/issues/new/choose),
or jump into [Discussions](https://github.com/jatinkrmalik/localcaption/discussions)
if you want to chat about it first.

## FAQ

**Does it need an OpenAI API key?**
No. All models run locally.

**Does audio leave my machine?**
No, except the download of a URL you asked for. Transcription and optional Ollama summaries stay on localhost.

**YouTube only?**
No. Any site [yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) (Vimeo, Twitch, Twitter/X, podcasts, and many more), plus local video and audio files.

**Does it write SRT and VTT?**
Yes. Each run writes `.txt`, `.srt`, `.vtt`, and `.json`.

**Windows?**
macOS and Linux are the supported platforms (`doctor --fix` uses Homebrew or apt). Native Windows is not supported. WSL is the realistic path if you are on Windows.

## Related projects

`localcaption` deliberately stays tiny. If you want more, check out:

- [`whishper`](https://github.com/pluja/whishper): full web UI for local
  transcription with translation and editing.
- [`transcribe-anything`](https://github.com/zackees/transcribe-anything):
  multi-backend, Mac-arm optimised, supports URLs.
- [`WhisperX`](https://github.com/m-bain/whisperX): word-level timestamps and
  diarisation on top of openai-whisper.

## Contributing

Pull requests welcome! See [CONTRIBUTING.md](CONTRIBUTING.md). By
participating you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE).
