# localcaption documentation

The authoritative documentation for `localcaption` — a tiny, fully-local
YouTube/file → transcript orchestrator (yt-dlp, ffmpeg, speechbrain language
ID, three specialist ASR models, all traffic over a SOCKS5 proxy, no API
keys).

## Start here

- **[docs/template.md](template.md)** — how to write for this docs tree
  (naming, numbering, ADR + design templates).
- **[design/01-pipeline-stages.md](design/01-pipeline-stages.md)** — the
  end-to-end four-stage pipeline and what files it produces.
- **[api/01-command-line-interface.md](api/01-command-line-interface.md)** —
  every CLI flag and subcommand.
- **[api/03-configuration.md](api/03-configuration.md)** — every environment
  variable and filesystem layout.
- **[repo root README.md](../README.md)** — user-facing overview and install.

## Directory map

| Folder | What lives here | README |
|---|---|---|
| [`adr/`](adr/) | Architectural Decision Records (Michael Nygard format) | [adr/README.md](adr/README.md) |
| [`design/`](design/) | Design documents: pipeline, model selection, GPU offload, batch, chapters, formats | [design/README.md](design/README.md) |
| [`networking/`](networking/) | Network layer: SOCKS5 policy, Tor rotation, bot-check, cookies | [networking/README.md](networking/README.md) |
| [`models/`](models/) | Model registry, isolated runtimes, language ID | [models/README.md](models/README.md) |
| [`api/`](api/) | CLI, Python API, configuration, error handling | [api/README.md](api/README.md) |
| [`operations/`](operations/) | Install, `doctor` self-healing, releasing | [operations/README.md](operations/README.md) |
| [`governance/`](governance/) | Contributing, code of conduct, security policy, changelog | [governance/README.md](governance/README.md) |
| [`diagrams/`](diagrams/) | Rendered architecture/pipeline/sequence diagrams (`.mmd` + `.png` + `.svg`) | [diagrams/README.md](diagrams/README.md) |
| [`icons/`](icons/) | Brand assets (`localcaption.svg`, `.png`) | [icons/README.md](icons/README.md) |

Every folder also carries a `template.md` mirroring the local document
template — see the canonical [docs/template.md](template.md).

## Key entry points

| Page | What it answers |
|---|---|
| [design/01-pipeline-stages.md](design/01-pipeline-stages.md) | What does a run actually do, and what files come out? |
| [adr/01-language-routing.md](adr/01-language-routing.md) | Why three ASR models instead of one? |
| [design/03-gpu-offload.md](design/03-gpu-offload.md) | How does GPU/CPU offloading work? |
| [networking/03-bot-check-mitigation.md](networking/03-bot-check-mitigation.md) | How does YouTube's "not a bot" wall get handled? |
| [models/02-isolated-runtimes.md](models/02-isolated-runtimes.md) | Why is there one virtualenv per model family? |
| [operations/02-doctor-self-healing.md](operations/02-doctor-self-healing.md) | What does `localcaption doctor --fix` do? |
| [operations/03-releasing.md](operations/03-releasing.md) | How are releases cut and published? |
| [api/04-error-handling.md](api/04-error-handling.md) | What exit codes and exceptions exist? |

## Governance

- [governance/01-contributing.md](governance/01-contributing.md) — how to
  contribute (quick start, layout, PR checklist).
- [governance/02-code-of-conduct.md](governance/02-code-of-conduct.md) —
  Contributor Covenant.
- [governance/03-security-policy.md](governance/03-security-policy.md) — how to
  report vulnerabilities.
- [governance/04-changelog.md](governance/04-changelog.md) — Keep a Changelog.
- Issue templates live in `.github/ISSUE_TEMPLATE/` (bug report, feature
  request) and `.github/pull_request_template.md`; CI in
  `.github/workflows/` (`ci.yml`, `release.yml`).