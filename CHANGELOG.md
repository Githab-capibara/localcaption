# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `scripts/install.sh` — one-line end-user installer that uses `pipx` for an
  isolated install and bootstraps `whisper.cpp` + a default model into
  `~/.local/share/localcaption/whisper.cpp` (XDG-compliant). After install,
  `localcaption` is callable from any directory.
- New `localcaption doctor` subcommand that diagnoses prerequisites,
  whisper.cpp build, and available models. Used by the bug-report template.
- The CLI now searches a third location for whisper.cpp:
  `$XDG_DATA_HOME/localcaption/whisper.cpp` (after the explicit flag, env var,
  and `./whisper.cpp` dev path).

### Changed
- `localcaption` invoked with no arguments now prints top-level help and
  exits with code 2 (was: argparse error). Existing `localcaption <url>`
  usage is unchanged.

## [0.1.0] - 2026-04-21

### Added
- Initial public release as `localcaption`.
- Modular package layout: `download` (yt-dlp), `audio` (ffmpeg), `whisper`
  (whisper.cpp), orchestrated by `pipeline.transcribe_url`.
- `localcaption` console script and `python -m localcaption` entry point.
- One-shot `scripts/setup.sh` that builds whisper.cpp and downloads a model.
- MIT license, contributor docs, security policy, GitHub Actions CI.
