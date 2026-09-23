# SOCKS5 proxy policy

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: How the single proxy default is resolved and spread to every
consumer (yt-dlp, curl model downloads, child processes).
Feeds into: [adr/03-proxy-first-networking.md](../adr/03-proxy-first-networking.md),
[../design/01-pipeline-stages.md](../design/01-pipeline-stages.md)

## Flow

`src/localcaption/network.py` is the single source of truth:

1. `get_proxy()` returns `LOCALCAPTION_PROXY` if set, else
   `socks5h://127.0.0.1:9050`.
2. The proxy is consumed by:
   - yt-dlp (`download.py`, `playlist.py` — passed as the `proxy` option);
   - curl model downloads (`models.py::_run_curl --proxy`);
   - every child process via inherited environment.
3. Loopback is always excluded from proxying.

## Constants

| Constant | Value |
|---|---|
| `DEFAULT_PROXY` | `socks5h://127.0.0.1:9050` |
| env var | `LOCALCAPTION_PROXY` |
| `_NO_PROXY_HOSTS` | `localhost`, `127.0.0.1`, `::1` |

## Behavior

`proxy_env(base)` builds a child-process environment adding `ALL_PROXY`,
`HTTP_PROXY`, `HTTPS_PROXY` (plus lowercase forms) set to the proxy, and
appending `_NO_PROXY_HOSTS` to `NO_PROXY`/`no_proxy`. `runner_env(base)`
continues from that and adds the runner env (offline/HF/CUDA flags; see
[../models/02-isolated-runtimes.md](../models/02-isolated-runtimes.md)).

The per-run escape hatch: `--no-proxy` sets the proxy to the empty string for
that run, so yt-dlp gets no `proxy` option and downloads go direct.

## Failure modes

- Proxy unreachable: `doctor` reports it (TCP connect, 3 s timeout); runs may
  fail at download time with the underlying yt-dlp/curl error and the
  hint to set `LOCALCAPTION_PROXY` or use `--no-proxy`.
- No proxy configured on `download` → default `socks5h://127.0.0.1:9050`
  applies, which for a tool without Tor means connection refused surfaced as a
  `DownloadError`/curl error.