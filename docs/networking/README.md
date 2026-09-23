# Networking layer

How every byte leaves (or stays on) your machine. The common rule: all
outbound traffic goes through the SOCKS5 proxy defined by
`LOCALCAPTION_PROXY`, loopback excluded. This folder contains the mechanism
design notes; the decisions behind them live in
[../adr/03-proxy-first-networking.md](../adr/03-proxy-first-networking.md).

| # | Page | What it covers |
|---|---|---|
| [01-socks5-proxy-policy](01-socks5-proxy-policy.md) | Proxy defaults, env propagation, `--no-proxy` | How the proxy is applied everywhere |
| [02-tor-circuit-rotation](02-tor-circuit-rotation.md) | Tor control port, `SIGNAL NEWNYM`, cookie auth | How a fresh exit is requested |
| [03-bot-check-mitigation](03-bot-check-mitigation.md) | "Sign in to confirm…" handling, player clients, rotate-on-block | How YouTube walls are survived |
| [04-cookie-sources](04-cookie-sources.md) | Cookie resolution order, browser names, `cookiefile` vs `cookiejar` | Where authenticated requests come from |

Template: [template.md](template.md) (canonical copy: [../template.md](../template.md)).