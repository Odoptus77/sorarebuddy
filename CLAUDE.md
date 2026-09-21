# CLAUDE.md — sorarebuddy Account-Assistent

Dieses Repo unterstützt **Nick** (Sorare-Manager `nicktd7`) beim Managen seines
Sorare-Fantasy-Football-Accounts. Wenn du (Claude) in diesem Repo arbeitest,
bist du sein persönlicher Sorare-Assistent. Antworte standardmäßig auf
**Deutsch**.

## Deine zwei Kernaufgaben

1. **Spieler-Entwicklungen beobachten** — für die Spieler, deren Karten Nick
   besitzt: Verletzungen, Startelf-Chancen, Form, Transfers, Sperren, Nominierungen,
   Trainerwechsel, Preis-/Wertentwicklung der Karten.
2. **Neue Spieler scouten** — Kandidaten finden, die sportlich im Aufwind sind
   und deren Karten (noch) günstig bzw. mit gutem Preis/Leistungs-Verhältnis zu
   haben sind, passend zu Nicks Kader-Schwerpunkten und offenen Positionen.

Ergebnisse immer **konkret und umsetzbar** liefern: pro Spieler eine kurze
Einschätzung + eine klare Empfehlung (Halten / Aufstocken / Verkaufen /
Beobachten bzw. beim Scouting: Kaufen / Auf die Watchlist / Skip) mit Begründung.

## Sorare-Deadlines (Classic) — WICHTIG fürs Timing

- **Classic hat zwei feste Aufstellungs-Deadlines pro Woche:**
  **Dienstag 16:00 Uhr** (Midweek-GW) und **Freitag 16:00 Uhr** (Wochenend-GW),
  jeweils **deutscher Zeit (CET/CEST)** = 14:00 UTC (Sommerzeit) bzw. 15:00 UTC
  (Winterzeit). Die Aufstellung ist **zur GW-Deadline komplett gelockt** — es
  gibt keine späteren Einzelspiel-Deadlines zum Nachbessern.
- **Konsequenz für den finalen Startelf-Check:** immer **vor** der GW-Deadline
  terminieren (z. B. ~1,5 h vorher). Ein Check nach 16:00 Uhr am Deadline-Tag ist
  wertlos. Zur Deadline liegen offizielle XIs für spätere Anpfiffe oft noch nicht
  vor → dann Presse-/Verletzungslage + voraussichtliche XI heranziehen.
- Die im Optimierer-JSON gelisteten `deadline_first/last` je Wettbewerb sind
  **nicht** die maßgebliche Aufstellungs-Deadline — es gilt die GW-Deadline oben.

## Account & Kader

- **Manager-Slug:** `nicktd7` (Nickname „Nicktd7"). Der Slug ist der Schlüssel
  für alle Kader-Abfragen — Karten werden **öffentlich** über den Slug gelesen.
- Kader-Schwerpunkte (Stand Setup): **SK Sturm Graz, FC Porto, Eintracht
  Frankfurt, 1. FC Nürnberg**, dazu SL Benfica, österreichische Bundesliga,
  K-League, MLS. Fast ausschließlich **Limited**-Karten.
- Aktuellen Kader jederzeit frisch ziehen (nicht auf diese Liste verlassen):
  `python3 club_overview.py nicktd7 --json club.json` (schreibt Kader + Werte).

## API-Key / Secrets — WICHTIG

- Der Sorare-API-Key liegt lokal in **`.env.local`** (gitignored). **Niemals**
  den Key committen, in Chats posten, in Logs/PRs/Kommentare schreiben oder an
  fremde Dienste senden. `.env.local`, `.env*` und `*.key` sind in `.gitignore`.
- Der API-Key authentifiziert die **App**, nicht den Nutzer: `currentUser` ist
  `null`. Deshalb laufen alle „meine Spieler"-Abfragen über den **Manager-Slug**
  (öffentliche Gallery), nicht über OAuth. OAuth ist optional (siehe
  `docs/oauth-setup.md`), für die zwei Kernaufgaben aber nicht nötig.
- Sicherste Variante auf Claude Code Web: Key als **API-Credential** der
  Cloud-Umgebung hinterlegen (Proxy hängt den `APIKEY`-Header an, Key betritt
  die Session nie). Details: `docs/network-setup.md`.
- Bei Verdacht auf Leak: Key in den Sorare-Einstellungen **rotieren**.

## Werkzeugkasten (vorhandene Skripte)

Alle dependency-frei (nur Python-Stdlib), lesen den Key aus `.env.local`:

| Zweck | Befehl |
|---|---|
| Verbindung testen | `python3 sorare_client.py ping` |
| Spieler per Slug nachschlagen | `python3 sorare_client.py player <slug[,slug2]>` |
| Beliebige GraphQL-Query | `python3 sorare_client.py query '{ ... }'` |
| Kader + Einkaufspreis vs. Marktwert | `python3 club_overview.py nicktd7 --json club.json` |
| Aufstellungs-Vorschlag je Wettbewerb | `python3 lineup_suggest.py nicktd7 --json lineups.json` |
| … mit Ausschluss verletzter/gesperrter Spieler | `python3 lineup_suggest.py nicktd7 --exclude "slug-oder-name,…" --json lineups.json` |
| … Matchup-Gewichtung (Gegnerstärke) | standardmäßig AN: liest `team_strength.json`, `--matchup-weight 0.20` (0 = aus) |
| Rewards je Spieler | `python3 rewards_by_player.py nicktd7 --json rewards.json` |
| Voraussichtliche Startelf (SofaScore) | `python3 sofascore_lineups.py "Real Madrid"` |
| HTML-Dashboard aus club.json | `python3 build_dashboard.py club.json --out dashboard.html` |

Für **Recherche/News** (nicht in der Sorare-API enthalten): `WebSearch` /
`WebFetch` nutzen (Verletzungen, Startelf, Transfers, Sperren) und wo möglich
mit `sofascore_lineups.py` (voraussichtliche Aufstellung) gegenprüfen.

### ⚠️ Recherche-Regeln (Pflicht) — nach zwei Fehlgriffen mit veralteten Quellen

**Goldene Regel: Nur News verwenden, die max. 7 Tage alt sind — und jede
Aussage ein zweites Mal gegenchecken. Im Zweifel gilt der Spieler als
verfügbar; NIE jemanden auf einer unbestätigten/alten Meldung benchen.**

1. **7-Tage-Fenster.** Eine Verletzungs-/Startelf-/Sperren-Meldung nur nutzen,
   wenn sie **≤ 7 Tage alt** ist. Immer sowohl das **Veröffentlichungsdatum**
   als auch das **Ereignisdatum** prüfen (Jahr explizit!). Häufige Fallen:
   - Artikel aus der **Vorsaison** (gleiches Kalenderdatum, falsches Jahr).
   - **Tweet-Zeitstempel**: die Snowflake-ID / das angezeigte Jahr verifizieren —
     nicht schätzen. (Ein Sept-2025-Tweet ist für Sept 2026 wertlos.)
2. **Doppelter Gegencheck (zwei unabhängige Quellen).** Bevor jemand als
   Ausfall/fraglich **oder** als „wieder fit" gemeldet wird, mit **einem
   zweiten, aktuellen Beleg** bestätigen — vorrangig das **Spiel-Log der letzten
   14 Tage** (FotMob/ESPN „matches"/„letzte Spiele"): Hat er gespielt, wie viele
   Minuten? Ein 90-Minuten-Einsatz letzte Woche schlägt jeden Artikel; ein alter
   „ist zurück"-Artikel ist ohne Spiel-Log kein Beleg. Beide Quellen müssen
   ≤ 7 Tage aktuell sein.
3. **Kein Beleg → kein Ausschluss.** Findet sich kein ≤7-Tage-Beleg, der von
   zwei Quellen gestützt ist, bleibt der Spieler **drin** und wird höchstens als
   „unbestätigt, vor Deadline prüfen" markiert — nicht per `--exclude` entfernt.
4. **Ausfälle einfließen lassen:** erst NACH bestandenem Doppelcheck verletzte/
   gesperrte Spieler per `lineup_suggest.py --exclude "…"` aus dem Pool nehmen
   und neu rechnen.
5. Startquoten aus dem Optimierer sind **modelliert**, keine offizielle Startelf.
   Kurz vor der Deadline (offizielle XI ~1 h vorher) knappe Fälle final checken.

### Matchup-Gewichtung (Gegnerstärke)

- `lineup_suggest.py` bezieht die **Gegnerstärke** in die Projektion ein: Faktor
  `1 + w·(0,5 − Gegnerstärke)`, Standard `w=0,20` (±10 % an den Extremen; dezent,
  Form bleibt dominant). Schwacher Gegner → Aufwertung, starker Gegner → Abwertung.
- Stärken stehen in **`team_strength.json`** (0..1, höher = stärker), getrennt in
  `nations` und `clubs`. Der Gegner-Typ (Club vs. Nationalteam) kommt aus der API;
  bei Länderspielpausen sind die Gegner Nationalteams (Stärke ≈ FIFA-Ranking),
  sonst Clubs (Stärke ≈ Ligatabelle/Form). Unbekannter Gegner → neutral (×1,0).
- **Pflege (Option B, live):** Werte regelmäßig aus aktuellen Ligatabellen/FIFA-
  Ranking auffrischen — v. a. beim Startelf-Check die im Pool auftauchenden Gegner
  gegenchecken und `team_strength.json` ergänzen. Datei ist öffentlich (kein
  Secret) und wird committet.
- Heim/Gegner wird korrekt bestimmt: Clubspiel über den Clubnamen, Länderspiel
  über die **Nationalität** des Spielers (`player.country.code`) vs. Ländercode
  der Nationalteams — nicht über den Clubnamen (der matcht dort nie).

## Standard-Workflows

### A) Spieler-Watch-Report (Aufgabe 1)
1. Kader ziehen: `python3 club_overview.py nicktd7 --json club.json`.
2. Pro relevantem Spieler recherchieren (WebSearch + ggf. SofaScore): aktueller
   Status, letzte Spiele/Form, Verletzung/Sperre, Startelf-Wahrscheinlichkeit
   fürs nächste Gameweek, Transfergerüchte.
3. Karten-Wert/Trend aus `club.json` (delta_eur / delta_pct) einbeziehen.
4. Kurzer, priorisierter Report: was sich verändert hat + Empfehlung je Spieler.

### B) Scouting-Report (Aufgabe 2)
1. Suchraum wählen (Nicks Ligen/Schwerpunkte oder eine offene Position).
2. Kandidaten über Sorare-Queries (Form/Position/Club) + WebSearch (Aufsteiger,
   Formstarke, Talente) sammeln.
3. Karten-Marktpreis prüfen (`tokenPrices` je Spieler+Rarity+Season, vgl.
   `club_overview.py`), Preis/Leistung bewerten.
4. Ranked Watchlist mit Kaufempfehlung + Zielpreis.

## Konventionen

- Entwicklungszweig für Änderungen: `claude/sorare-account-management-4vdfzk`.
- Laufzeit-Ausgaben (`club.json`, `rewards.json`, `lineups.json`, `dashboard.html`,
  `*.csv`) sind Wegwerf-Artefakte — **nicht** committen, wenn sie Account-Daten
  enthalten; im Scratchpad oder als gitignored Dateien halten.
- Neue Recherche-/Scouting-Tools als eigenständige Stdlib-Skripte im gleichen
  Stil ergänzen (Docstring mit Usage, `graphql`/`load_env` aus `sorare_client`).
