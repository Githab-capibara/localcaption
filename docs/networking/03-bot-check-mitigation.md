# Bot-check mitigation

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: How the downloader survives YouTube's "Sign in to confirm you're not
a bot" wall on Tor exit IPs.
Feeds into: [adr/03-proxy-first-networking.md](../adr/03-proxy-first-networking.md),
[02-tor-circuit-rotation.md](02-tor-circuit-rotation.md),
[04-cookie-sources.md](04-cookie-sources.md)

## Flow

`src/localcaption/download.py` runs yt-dlp with a rotating player-client
list and a retry loop with Tor rotation:

1. **Fresh exit on start** — rotate the Tor circuit before the first attempt,
   so the download starts on a clean exit IP (unless `--no-proxy`/direct run).
2. **Player-client rotation** — `DEFAULT_PLAYER_CLIENTS =
   ("tv","mweb","android","ios","web")`; each retry drops the previously-first
   client, so different answer sets (clients) are tried.
3. **Re-rotate on block** — if a retry still hits the bot wall, the exit is
   rotated again (SIGNAL NEWNYM) before the next attempt.
4. **Cookies** — if a cookie source is available it is attached (see
   [04-cookie-sources.md](04-cookie-sources.md)), which usually bypasses the
   wall outright.

Bot-block detection (`network._looks_like_bot_block`, case-insensitive over
the error text): `sign in to confirm`, variants with the curly apostrophe
`you’re not a bot`, `bot check`, `bot-check`, `too many requests`, and the
plain `403` substring.

## Constants

| Constant | Value |
|---|---|
| player clients | `("tv","mweb","android","ios","web")` |
| recognized block tokens | `sign in to confirm`, `you’re not a bot`, `bot check`, `bot-check`, `too many requests`, `403` |
| downloader retries | `retries=5`, `fragment_retries=5`, `concurrent_fragment_downloads=4` |
| audio format | `bestaudio[acodec=opus]/bestaudio/best` |

## Behavior

When the final error is a bot block, the raised `DownloadError` message lists
three options: place a Netscape cookie jar at
`~/.localcaption/yt-dlp-cookies.txt` (or `LOCALCAPTION_YTDLP_COOKIES`), retry
to grab a fresh Tor exit, or point `LOCALCAPTION_PROXY` at an un-flagged exit.
The note also mentions `pip install -U yt-dlp` — most "YouTube is broken"
reports are upstream extractor regressions, not this bug.

## Failure modes

- Persistent bot block with no cookies → `DownloadError` containing the
  "Tor exit IP" guidance.
- Non-bot failures (e.g. `connection reset by peer`) → plain `DownloadError`
  without the Tor guidance.