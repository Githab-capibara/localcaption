# Title: Route every outbound request through a SOCKS5 proxy

Status: Accepted
Date: 2026-09-22
Deciders: Maintainer, network reviewers
Related: [design/01-pipeline-stages.md](../design/01-pipeline-stages.md), [networking/*](../networking/README.md)

## Context

The project's privacy promise is "no data leaves your machine except the URL
you asked for". That promise is only true if **all** network activity is
controllable: the yt-dlp download, the Hugging Face checkpoint fetches, and
any child processes they spawn. Many users run a local Tor SOCKS proxy, and
YouTube flags Tor exit IPs with bot-checks — see
[networking/03-bot-check-mitigation.md](../networking/03-bot-check-mitigation.md).

## Decision

Proxy-first by default:

- Default proxy `socks5h://127.0.0.1:9050`; override with `LOCALCAPTION_PROXY`
  (`src/localcaption/network.py`, `get_proxy`).
- Loopback hosts (`localhost`, `127.0.0.1`, `::1`) are always excluded.
- The proxy env is propagated to every child process: `ALL_PROXY` /
  `HTTP_PROXY` / `HTTPS_PROXY` plus lowercase variants, and `NO_PROXY`
  extended with the loopback set (`network.proxy_env`).
- Model checkpoints download through `curl --proxy …`
  (`src/localcaption/models.py`, `_run_curl`).
- Per-run escape hatch: `--no-proxy` sets an empty proxy for that run only
  (`src/localcaption/cli.py`).
- The local Ollama client deliberately ignores `HTTP(S)_PROXY` — it targets
  localhost (see [adr/05-local-ollama-summaries.md](05-local-ollama-summaries.md)).

## Consequences

Positive:
- No accidental direct connections: downloads, model fetches and subprocesses
  inherit the same policy.
- Tor users route everything through Tor immediately.
- `doctor` verifies proxy reachability as part of diagnostics.

Negative / trade-offs:
- Requires *some* local proxy to be running by default; without Tor, users
  must set `LOCALCAPTION_PROXY` or pass `--no-proxy`.
- Proxy adds latency to large model downloads.

## Alternatives considered

- Direct connection by default, proxy opt-in — rejected: breaks the
  privacy-by-default promise.
- HTTP proxy only — SOCKS covers Tor natively; HTTP proxies don't.