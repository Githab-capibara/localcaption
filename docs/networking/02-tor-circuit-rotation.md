# Tor circuit rotation

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: How a fresh Tor exit circuit is requested over the control port and
when the downloader does it.
Feeds into: [adr/03-proxy-first-networking.md](../adr/03-proxy-first-networking.md),
[03-bot-check-mitigation.md](03-bot-check-mitigation.md)

## Flow

`src/localcaption/network.py::rotate_tor_circuit` talks to the Tor control
port with a raw TCP socket (2 s timeout):

1. Resolve control host/port: `LOCALCAPTION_TOR_CONTROL` if set, else the
   proxy host with **port + 1** (`9050` → `9051`).
2. Refuse non-loopback proxies — rotating an external proxy is not Tor and
   returns `False`.
3. Locate the control cookie (first existing of):
   `/run/tor/control.authcookie`,
   `/var/run/tor/control.authcookie`,
   `/run/user/<uid>/tor/control.authcookie`,
   or `<LOCALCAPTION_TOR_DATADIR>/control.authcookie`; absent cookie → send a
   bare `AUTHENTICATE`.
4. Send `AUTHENTICATE <hex>\r\n` (expect `250`) then `SIGNAL NEWNYM\r\n`
   (expect `OK`).

The downloader (`download.py`) calls this before the first attempt, always
when `--rotate-tor` is passed, and again mid-retry after a detected bot
block.

## Constants

| Constant | Value |
|---|---|
| control port derivation | proxy port + 1 (default 9051) |
| env vars | `LOCALCAPTION_TOR_CONTROL`, `LOCALCAPTION_TOR_DATADIR` |
| socket timeout | 2 s |
| commands | `AUTHENTICATE <hex>` then `SIGNAL NEWNYM` |
| success checks | `250` (authenticate), `OK` (newnym) |

## Failure modes

All non-fatal: rotation returns `False` and the caller logs/hints when the
control port is unreachable, the proxy is not loopback Tor, or auth fails.
`doctor` reports the `tor-rotate` check with a hint about the control port
(9051?). Downloads proceed — unrotated or direct — and surface the real
failure if YouTube blocks.