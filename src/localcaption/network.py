"""Network policy: every byte localcaption fetches goes through a SOCKS5 proxy.

The default is a local Tor SOCKS5 endpoint at ``127.0.0.1:9050``. It is
applied to:

* ``yt-dlp`` media downloads (via the ``proxy`` option),
* model downloads (via ``curl``),
* any Hugging Face / PyTorch network access performed by the child
  processes that host the ASR models (via ``ALL_PROXY`` and friends).

Override the endpoint with ``$LOCALCAPTION_PROXY`` (any URL accepted by
``curl`` / ``yt-dlp`` / ``requests``). Loopback hosts are always excluded so
local services (Ollama, the proxy itself) are used directly.
"""

from __future__ import annotations

import os

DEFAULT_PROXY = "socks5h://127.0.0.1:9050"
_NO_PROXY_HOSTS = ("localhost", "127.0.0.1", "::1")


def get_proxy() -> str:
    """Return the proxy URL to use for all outbound traffic."""
    return os.environ.get("LOCALCAPTION_PROXY", "").strip() or DEFAULT_PROXY


def proxy_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Copy *base* (default: ``os.environ``) with proxy variables set.

    Both upper- and lower-case spellings are set because different tools
    disagree about which they honour.
    """
    env = dict(os.environ if base is None else base)
    proxy = get_proxy()
    for key in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY"):
        env[key] = proxy
        env[key.lower()] = proxy
    existing = [p.strip() for p in (env.get("NO_PROXY") or "").split(",") if p.strip()]
    for host in _NO_PROXY_HOSTS:
        if host not in existing:
            existing.append(host)
    env["NO_PROXY"] = ",".join(existing)
    env["no_proxy"] = env["NO_PROXY"]
    return env


def runner_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for a model-hosting child process: proxy + offline mode.

    Models are loaded from local directories, so Hugging Face lookups are
    disabled. If an action does need the network it still rides the proxy.
    """
    env = proxy_env(base)
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    # Keep model chatter (e.g. generation-flag notices) out of the transcript log.
    env["TRANSFORMERS_VERBOSITY"] = "error"
    env["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
    # speechbrain honours SB_LOG_LEVEL to silence its internal INFO chatter.
    env["SB_LOG_LEVEL"] = "ERROR"
    return env
