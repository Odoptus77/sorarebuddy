# sorarebuddy Backend

A tiny, dependency-free HTTP API in front of the existing Python pipeline. The
SwiftUI app talks only to this backend, so the **Sorare API key never ships in
the app** — it lives here as an environment variable.

```
App (SwiftUI)  ──HTTPS──▶  backend/server.py  ──▶  club_overview.py
                                               ──▶  rewards_by_player.py
                                               ──▶  lineup_suggest.py  ──▶  api.sorare.com
```

## Endpoints

| Route           | Returns                                   |
|-----------------|-------------------------------------------|
| `GET /health`   | `{"ok": true}`                            |
| `GET /api/club?slug=…&rarities=limited,rare`    | club valuation JSON |
| `GET /api/rewards?slug=…`                       | reward attribution  |
| `GET /api/lineups?slug=…&rarities=limited,rare` | lineup suggestions  |
| `GET /api/bundle?slug=…`                        | all three combined  |

Responses carry `X-Cache-Age` (seconds since the data was computed).

## Run locally

```bash
# key: either set it here, or leave it to a proxy/.env.local like the CLI does
export SORARE_API_KEY=sr128_...           # your Sorare API key
export APP_TOKEN=$(openssl rand -hex 16)  # optional shared secret (recommended)
export DEFAULT_SLUG=nicktd7
python3 backend/server.py                 # listens on :8080
```

Point the app's **Backend-URL** at `http://<your-computer-ip>:8080` (a phone on
the same Wi-Fi reaches your Mac by its LAN IP, e.g. `http://192.168.1.20:8080`).
`localhost` only works in the iOS Simulator.

## Caching & prewarming

Each result is cached on disk (`CACHE_DIR`, default `backend/cache`) for
`CACHE_TTL` seconds (default 1800). A **stale** entry is served instantly while
a fresh copy is computed in the background; only a **cold** cache blocks.

A cold `rewards`/`club` run scans hundreds of players/fixtures and can take
several minutes. **Prewarm** so the app never waits:

```bash
curl -s "http://localhost:8080/api/bundle?slug=nicktd7" -H "Authorization: Bearer $APP_TOKEN" >/dev/null
```

Run that on startup and, say, hourly via cron so the cache is always warm.

## Environment variables

| Var              | Default          | Meaning                                   |
|------------------|------------------|-------------------------------------------|
| `SORARE_API_KEY` | –                | Sorare key (required on a real server)    |
| `APP_TOKEN`      | – (auth off)     | if set, requests need `Authorization: Bearer <token>` |
| `PORT`           | 8080             | listen port                               |
| `CACHE_TTL`      | 1800             | seconds a cache entry stays fresh         |
| `CACHE_DIR`      | backend/cache    | cache location                            |
| `DEFAULT_SLUG`   | –                | slug used when `?slug=` is omitted        |
| `JOB_TIMEOUT`    | 600              | max seconds for one pipeline run          |

## Deploy (any host that runs Python 3, no dependencies)

- **Fly.io / Render / Railway / a small VPS:** run `python3 backend/server.py`
  behind their TLS. Set `SORARE_API_KEY` and `APP_TOKEN` as secrets. Attach a
  persistent volume at `CACHE_DIR` so the cache survives restarts.
- Put it behind **HTTPS** (the platform's built-in TLS or a reverse proxy);
  iOS App Transport Security blocks plain HTTP to non-local hosts.
- Keep `APP_TOKEN` set in production so only your app can trigger the (costly)
  Sorare fetches.

> Security: never bake `SORARE_API_KEY` into the app or commit it. It stays a
> server-side secret. If it was ever shared, rotate it in Sorare settings.
