# Cookie sources

Status: Research note
Date: 2026-09-22
Deciders: Maintainer
Researcher: Maintainer
Purpose: How an authenticated session for yt-dlp is found and passed through.
Feeds into: [03-bot-check-mitigation.md](03-bot-check-mitigation.md),
[../design/04-batch-and-playlists.md](../design/04-batch-and-playlists.md)

## Flow

`src/localcaption/network.py::get_ytdlp_cookies()` resolves the cookie source
in order, first match wins:

1. `LOCALCAPTION_YTDLP_COOKIES` — a Netscape cookie file path (used as-is).
2. `~/.localcaption/yt-dlp-cookies.txt` — if the file exists.
3. Logged-in browser jars — browser names from
   `LOCALCAPTION_YTDLP_COOKIE_BROWSERS` (comma-separated, tried in order;
   default `chrome,firefox`); the first browser whose `yt_dlp.cookies`
   extraction returns a non-empty jar wins.
4. `None` — no cookies.

The CLI `--cookies BROWSER_OR_FILE` overrides any of this for one run. The
resolution is also consulted by playlist expansion (`playlist.py`).

### Browser-name detection

A value is treated as a browser name (→ yt-dlp `cookiejar`) only when it is a
known browser, lowercase, and contains no path separators or extension:
`chrome, chromium, edge, firefox, brave, bravebrowser, vivaldi, opera,
safari, konqueror, ie, silk`. Anything else is a cookie file path (→ yt-dlp
`cookiefile`, `~` expanded). Detection is by name only — a stray Netscape jar
in the CWD cannot shadow it.

## Constants

| Constant | Value |
|---|---|
| env vars | `LOCALCAPTION_YTDLP_COOKIES`, `LOCALCAPTION_YTDLP_COOKIE_BROWSERS` |
| default file | `~/.localcaption/yt-dlp-cookies.txt` |
| default browsers | `chrome`, `firefox` |
| known browser names | `chrome chromium edge firefox brave bravebrowser vivaldi opera safari konqueror ie silk` |
| yt-dlp mapping | file path → `cookiefile`; browser → `cookiejar` |

## Failure modes

- Empty browser jar → treated as "no cookies" (no `cookiefile`/`cookiejar`
  key set).
- No cookie source found → `None`; the download proceeds anonymous (and may
  hit the bot wall — see [03-bot-check-mitigation.md](03-bot-check-mitigation.md)).