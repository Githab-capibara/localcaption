# Configuration

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: Every environment variable, its default, and the filesystem layout.
Feeds into: [../networking/01-socks5-proxy-policy.md](../networking/01-socks5-proxy-policy.md),
[../models/01-model-registry.md](../models/01-model-registry.md)

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `LOCALCAPTION_PROXY` | `socks5h://127.0.0.1:9050` | Proxy for **all** outbound traffic; loopback always excluded. |
| `LOCALCAPTION_YTDLP_COOKIES` | — | Netscape cookie file path (first cookie source). |
| `LOCALCAPTION_YTDLP_COOKIE_BROWSERS` | `chrome,firefox` | Comma-separated browser names tried in order. |
| `LOCALCAPTION_TOR_CONTROL` | proxy port + 1 (`127.0.0.1:9051`) | Tor control-port endpoint for `SIGNAL NEWNYM`. |
| `LOCALCAPTION_TOR_DATADIR` | — | Tor data dir; control cookie probed at `<dir>/control.authcookie`. |
| `LOCALCAPTION_MODELS_DIR` | `<repo>/models` | Where the four checkpoints live. |
| `LOCALCAPTION_RUNTIME_DIR` | `<repo>/runtime` | Where the per-model virtualenvs live. |
| `LOCALCAPTION_INDEX_PATH` | `~/.local/share/localcaption/index.jsonl` | Search index location (XDG-derived). |
| `NO_COLOR` | — | Presence disables ANSI colors in CLI logs. |

XDG fallbacks: `XDG_DATA_HOME`/`XDG_CACHE_HOME` shape the data/cache dirs
(index, caches under `localcaption/`).

## Filesystem layout

```
<repo>/
├── models/            # 4 checkpoints, one dir per key (overridable)
├── runtime/           # main nvidia qwen langid virtualenvs (overridable)
├── docs/              # this documentation tree (index: docs/README.md)
├── scripts/           # install.sh, setup.sh, setup_runtime.sh, uninstall.sh
└── src/localcaption/  # the package
```

Per a pipx install, models + runtimes land under the data dir
(`$XDG_DATA_HOME/localcaption`), matching what `scripts/uninstall.sh`
removes.

## Scripts

| Script | Audience | Key knobs |
|---|---|---|
| `scripts/install.sh` | end users | `LOCALCAPTION_PACKAGE_SPEC`, `LOCALCAPTION_DATA_DIR`, `LOCALCAPTION_PROXY` |
| `scripts/setup.sh` | developers | `EXTRAS` (default `dev`), `SKIP_MODELS` (default `0`) |
| `scripts/setup_runtime.sh` | both | `LOCALCAPTION_RUNTIME_DIR`, `LOCALCAPTION_PROXY`, `PYTHON_VERSION` (default `3.12`) |
| `scripts/uninstall.sh` | end users | `--yes`, `--keep-models`, `--dry-run` |

See [../operations/01-installation.md](../operations/01-installation.md).