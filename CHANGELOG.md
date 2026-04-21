# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-21

### Added
- Initial public release as `localcaption`.
- Modular package layout: `download` (yt-dlp), `audio` (ffmpeg), `whisper`
  (whisper.cpp), orchestrated by `pipeline.transcribe_url`.
- `localcaption` console script and `python -m localcaption` entry point.
- One-shot `scripts/setup.sh` that builds whisper.cpp and downloads a model.
- MIT license, contributor docs, security policy, GitHub Actions CI.
