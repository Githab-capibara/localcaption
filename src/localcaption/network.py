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
import re
import socket
from pathlib import Path

DEFAULT_PROXY = "socks5h://127.0.0.1:9050"
_DEFAULT_YTDLP_COOKIES = "~/.localcaption/yt-dlp-cookies.txt"
_NO_PROXY_HOSTS = ("localhost", "127.0.0.1", "::1")


def get_proxy() -> str:
    """Return the proxy URL to use for all outbound traffic."""
    return os.environ.get("LOCALCAPTION_PROXY", "").strip() or DEFAULT_PROXY


def get_ytdlp_cookies() -> str | None:
    """Return a cookies-file path for yt-dlp, or ``None``.

    A logged-in browser cookie jar is the single most reliable way past
    YouTube's "Sign in to confirm you're not a bot" wall (which fires on
    Tor exit IPs). Resolution order:

    1. ``$LOCALCAPTION_YTDLP_COOKIES`` (Netscape-format cookie file)
    2. ``~/.localcaption/yt-dlp-cookies.txt``
    3. first of ``$LOCALCAPTION_YTDLP_COOKIE_BROWSERS`` (comma-separated list
       of browser names, tried in order) if that file exists
    4. ``None``
    """
    env = os.environ.get("LOCALCAPTION_YTDLP_COOKIES", "").strip()
    if env:
        return env
    default = Path(os.path.expanduser(_DEFAULT_YTDLP_COOKIES))
    if default.is_file():
        return str(default)
    browsers = os.environ.get("LOCALCAPTION_YTDLP_COOKIE_BROWSERS", "").strip()
    for name in (browsers.split(",") if browsers else ["chrome", "firefox"]):
        name = name.strip()
        if not name:
            continue
        try:
            from yt_dlp.cookies import extract_cookies_from_browser
        except ImportError:
            break
        try:
            cookiejar = extract_cookies_from_browser(name)
        except Exception:
            continue
        if cookiejar:
            return name
    return None


def _parse_host_port(proxy: str) -> tuple[str, int] | None:
    """Extract ``(host, port)`` from a proxy URL; ``None`` when unparseable."""
    m = re.match(r"^[a-z0-9+]+://([^:/]+):(\d+)", proxy, re.I)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def _tor_control_host_port() -> tuple[str, int]:
    """Return a reachable ``(host, port)`` for the Tor control port, or None."""
    control = os.environ.get("LOCALCAPTION_TOR_CONTROL", "").strip()
    if control:
        parsed = _parse_host_port(control)
        if parsed:
            return parsed
    parsed = _parse_host_port(get_proxy())
    if not parsed:
        return None
    # Tor's control port is conventionally SOCKS port + 1 (9050 -> 9051).
    return parsed[0], parsed[1] + 1


def _read_tor_control_cookie(host: str, port: int) -> bytes | None:
    """Read Tor's control-port auth cookie if one is available.

    A local ``tor`` process with ``ControlPort`` + ``CookieAuthentication``
    writes a group-readable cookie. Common locations are probed in order.
    """
    candidates = (
        "/run/tor/control.authcookie",
        "/var/run/tor/control.authcookie",
        f"/run/user/{os.getuid()}/tor/control.authcookie",
    )
    for path in candidates:
        try:
            return Path(path).read_bytes()
        except OSError:
            continue
    # Fallback: Tor's own data directory cookie, next to the data dir.
    data_dir = os.environ.get("LOCALCAPTION_TOR_DATADIR")
    if data_dir:
        try:
            return Path(data_dir, "control.authcookie").read_bytes()
        except OSError:
            return None
    return None


def rotate_tor_circuit() -> bool:
    """Ask Tor for a fresh exit circuit (``SIGNAL NEWNYM``). Best-effort.

    YouTube's "Sign in to confirm you're not a bot" wall fires on the Tor
    *exit IP*, not the player client. Rotating clients therefore does not
    unblock it — the exit IP must change. This drives the Tor control port
    when reachable (cookie auth when available, else plaintext); returns
    ``False`` silently otherwise so the caller falls back to cookies / a
    non-Tor proxy.

    Protocol: connect to the control port, authenticate (hex-cookie when
    Tor's cookie auth is on), then ``SIGNAL NEWNYM``.
    """
    proxy = get_proxy()
    parsed = _parse_host_port(proxy)
    # Refuse to touch a non-loopback proxy: only a *local* Tor instance has
    # a reachable control port. A remote SOCKS5/HTTP proxy has no Tor to ask.
    if parsed and parsed[0] not in ("127.0.0.1", "localhost", "::1"):
        return False

    host_port = _tor_control_host_port()
    if not host_port:
        return False
    host, port = host_port
    cookie = _read_tor_control_cookie(host, port)
    try:
        s = socket.create_connection((host, port), timeout=2.0)
    except OSError:
        return False
    try:
        with s:
            if cookie:
                s.sendall(f"AUTHENTICATE {cookie.hex()}\r\n".encode())
                resp = s.recv(1024).decode("utf-8", "replace")
                if "250" not in resp:
                    return False
            else:
                # Plaintext / no-auth control port.
                s.sendall(b"AUTHENTICATE\r\n")
                s.recv(1024)
            s.sendall(b"SIGNAL NEWNYM\r\n")
            resp = s.recv(1024).decode("utf-8", "replace")
            return "OK" in resp
    except OSError:
        return False


def _looks_like_bot_block(msg: str) -> bool:
    """Heuristic: does this yt-dlp error mean YouTube flagged the IP/client?"""
    lowered = msg.lower()
    return any(
        token in lowered
        for token in (
            "sign in to confirm",
            "confirm you're not a bot",
            "sign in to confirm you’re not a bot",
            "bot check",
            "bot-check",
            "too many requests",
            "403",
        )
    )


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
    # Let the CUDA caching allocator grow in-place so a partial GPU/CPU split
    # (accelerate ``device_map``) does not fragment VRAM or pre-reserve more
    # than the free budget.
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    env["CUDA_MODULE_LOADING"] = "LAZY"
    return env
