# sorarebuddy Dashboard (Next.js)

Grafische Oberfläche für die sorarebuddy-Pipeline: nächste Gameweek mit
Deadline-Countdown, alle Aufstellungen mit Startquoten und Warnungen, Kader mit
Wertentwicklung, GW-Bilanz (echte Aufstellungen/Plätze via OAuth) und
Modellqualität (Treffer-Bilanz, Projektionsfehler je Position × Spieltyp).

| Seite | Inhalt | Datenquelle |
|---|---|---|
| `/` Übersicht | Countdown, erwartete Punkte, EV je Team, Kapitäne, Warnungen, unsichere Starter | `lineups` |
| `/aufstellungen` | alle Teams mit Startquote, Projektion, EV, Hinweisen | `lineups` |
| `/kader` | alle Karten, Kaufpreis vs. Wert, Suche/Sortierung | `club` |
| `/bilanz` | echte Aufstellungen je GW: Platz, Punkte, Rewards, Ausfälle, Kapitäns-Verlust | `review` (OAuth) |
| `/modell` | Brier je Quelle, Projektions-Bias je Position × Spieltyp, Fehlgriffe | `model` |

## Sicherheit / Daten

- Alle Daten werden **serverseitig** geladen (Server Components, `server-only`).
  Der Browser bekommt nur fertiges HTML — weder Sorare-Key noch Backend-Token.
- Das Repo ist öffentlich: **keine Account-Daten committen**. Die JSON-Dateien
  sind im Hauptrepo gitignored; `.env.local` ebenso.
- Gehostet **immer** `DASHBOARD_PASSWORD` setzen (HTTP Basic Auth über
  `src/proxy.ts`).

## Datenquellen

**A) Backend (empfohlen für Hosting):** `backend/server.py` rechnet und cached
die Pipeline (`/api/lineups`, `/api/club`, `/api/model`, `/api/review`).
`SORAREBUDDY_API_URL` + `SORAREBUDDY_API_TOKEN` (= `APP_TOKEN` des Backends)
setzen. Ein kalter Pipeline-Lauf kann Minuten dauern; danach kommt der Cache.

**B) Lokal (ohne Backend):** im Repo-Root die Skripte laufen lassen, dann liest
das Dashboard die Dateien direkt:

```bash
python3 lineup_suggest.py nicktd7 --rarities limited --json lineups.json
python3 club_overview.py nicktd7 --rarities limited --json club.json --out /dev/null
python3 evaluate.py            # logs/evaluation.json + calibration.json
python3 lineup_review.py       # logs/lineup_review.json (braucht Sorare-Login)
```

## Start

```bash
cd dashboard
cp .env.example .env.local     # ausfüllen
npm install
npm run dev                    # http://localhost:3000
# Produktion:
npm run build && npm run start
```

Auf dem VPS (siehe `deploy/`) läuft das Dashboard z. B. als zweiter
systemd-Dienst auf Port 3000 hinter Caddy, mit dem Backend auf `127.0.0.1:8080`
als `SORAREBUDDY_API_URL`.

## Design

Farben aus einer validierten Chart-Palette: eine Akzentfarbe (Blau) für
Mengen, Blau/Rot nur für Abweichungen um null, Status-Farben (grün/gelb/orange/
rot) nur zusammen mit Icon + Text. Hell- und Dunkelmodus folgen dem System.
Jede Grafik hat eine Tabellenansicht („Als Tabelle“).
