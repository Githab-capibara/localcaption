# Security Policy

## Supported Versions

`localcaption` is pre-1.0; only the `main` branch is officially supported.

## Reporting a Vulnerability

Please **do not** open public GitHub issues for security problems.

Instead, use GitHub's private vulnerability reporting:

1. Navigate to the **Security** tab of the repository.
2. Click **Report a vulnerability**.
3. Provide a clear description, reproduction steps, and impact assessment.

We aim to acknowledge reports within 7 days.

## Scope

In-scope:

- The `localcaption` Python package itself.
- The `scripts/setup.sh` bootstrap.

Out of scope:

- Vulnerabilities in upstream `yt-dlp`, `ffmpeg`, or `whisper.cpp` — please
  report those to the respective projects.
- Issues that require local code execution as the same user already running
  `localcaption` (we treat the local user as trusted).
