# CLAUDE.md — sorarebuddy Account-Assistent

Dieses Repo unterstützt **Nick** (Sorare-Manager `nicktd7`) beim Managen seines
Sorare-Fantasy-Football-Accounts. Wenn du (Claude) in diesem Repo arbeitest,
bist du sein persönlicher Sorare-Assistent. Antworte standardmäßig auf
**Deutsch**.

## 🛑 GRUNDREGEL #0 (gilt IMMER, für ALLES): Datum zuerst

**Bevor irgendeine News/Quelle verwendet wird — egal wofür (Verletzung, Sperre,
Startelf, Transfer, Form, Preis, Regeln, irgendwas) — ZUERST das Datum prüfen,
dann erst verwenden oder verwerfen.** Kein Fakt aus einer Quelle wird genutzt,
ohne dass Veröffentlichungs- UND Ereignisdatum (inkl. **Jahr**) geklärt sind.

- Gilt auch für News, die **reinkommen** (PR-Events, Nachrichten), nicht nur für
  aktiv gesuchte.
- WebSearch-**Zusammenfassungen zeigen das Datum oft NICHT** → dann die Quelle
  öffnen (WebFetch) oder ein **datiertes Spiel-Log** nutzen, um das Datum zu
  bestätigen. Niemals aus einer undatierten Zusammenfassung schließen.
- Für zeitkritische Aussagen (Verletzung/Sperre/Startelf): nur nutzen, wenn
  **≤ 7 Tage alt** und von einer **zweiten** datierten Quelle bestätigt.
- Häufige Fallen: Vorsaison-Artikel (gleiches Kalenderdatum, falsches Jahr);
  Tweet-Zeitstempel/Snowflake; ein „X ist gesperrt/verletzt/zurück"-Artikel aus
  einem früheren Jahr. (Bereits passiert: eine Van-Dijk-„Sperre" aus 2024 als
  2026 gewertet — genau das verhindert diese Regel.)
- Im Zweifel: **nicht verwenden**, Spieler/Fakt unverändert lassen, als
  „unbestätigt" markieren.

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
  **OAuth ist seit 29.09.2026 eingerichtet:** `SORARE_CLIENT_ID/SECRET` als
  Umgebungsvariablen der Cloud-Umgebung; Access-Token (~1 Tag) + rotierender
  Refresh-Token nur in `.env.local`, **nie angezeigt**. `ensure_user_token()`
  erneuert automatisch. Nach Container-Neustart fehlt der Token → Nick den Link
  aus `python3 sorare_client.py authurl` schicken, Code mit `token <code>`
  tauschen (~1 Min). Mit Login lesbar: `so5Fixture.mySo5Lineups` (Nicks
  gesetzte Aufstellungen, nach Lock), `mySo5Rankings`, Rewards. Sorare-Startquoten
  bleiben auch mit Login `null` (#693). Ein abgelaufener Token fällt automatisch
  auf öffentliche Abfragen zurück.
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
| … für eine bestimmte GW (z. B. MLS-Hot-Streak in Länderspielpause) | `python3 lineup_suggest.py nicktd7 --fixture football-25-29-sep-2026` |
| … mit Ausschluss verletzter/gesperrter Spieler | `python3 lineup_suggest.py nicktd7 --exclude "slug-oder-name,…" --json lineups.json` |
| … Matchup-Gewichtung (Gegnerstärke) | standardmäßig AN: liest `team_strength.json`, `--matchup-weight 0.20` (0 = aus) |
| … National-Abstellungen (Länderspielpause) | UEFA automatisch aus dem Fixture; Nicht-UEFA in `international_callups.json` (per Fixture-Slug); s. u. |
| Verletzungen/Sperren (API-Football) | `python3 injuries_feed.py status` · `date YYYY-MM-DD` · `selftest` (Einrichtung: `docs/network-setup.md`) |
| Rewards je Spieler | `python3 rewards_by_player.py nicktd7 --json rewards.json` |
| **Treffer-Bilanz + Lernkreislauf** | `python3 evaluate.py` (Log vs. echte Startelf/Minuten/Punkte → `logs/evaluation.json` + gelernte `calibration.json`) |
| **GW-Bilanz (echte Aufstellungen, OAuth)** | `python3 lineup_review.py [--last 4] [--gw 716]` (Nicks gesetzte Lineups + Platz/Score/Rewards, Ausfälle, Kapitäns-Verlust, Prognose vs. Ergebnis je Position × Spieltyp; braucht Login, s. u.) |
| Backtest/Kalibrierung des Modells | `python3 backtest.py nicktd7 [--players "slug,…"] [--json backtest.json]` (misst Start-Kalibrierung/Brier + Projektions-Fehler retrospektiv aus Spiel-Logs) |
| Scouting: Ersatz/Ziel-Spieler bewerten | `python3 scout.py --like <slug> --candidates "slug1,slug2,…" [--budget 40] [--position Defender]` (Matchup-Gewichtung standardmäßig an, `--matchup-weight 0`=aus) |
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

### Eigene Startelf-Prognose für Länderspiele (Gegenpol zu Sorare)

- Mein Modell rechnet Startquoten aus **Vereins**-Minuten — bei **Länderspielpausen**
  (Gegner = Nationalteam) ist das unbrauchbar (Vereins-Stammspieler ≠ Nationalelf-
  Starter). Deshalb eigene, recherchierte Startquoten in **`start_overrides.json`**
  (`{player_slug: 0..1}`), die das Modell überschreiben (`--start-override`,
  standardmäßig an).
- **Methodik (Pflicht bei Länderspiel-GWs):** pro betroffenem Nationalteam
  **3–4 voraussichtliche Aufstellungen** (WhoScored, Sports Mole, GiveMeSport,
  FotMob, Sofascore …) heranziehen, Quellen-Aktualität nach den ≤7-Tage-Regeln
  prüfen (Falle: veraltete Elf mit zurückgetretenen Spielern), dann eine **eigene
  Wahrscheinlichkeit** je Spieler bilden. Darf Sorare bewusst widersprechen —
  aber nur gut belegt. Auch **Sperren** zählen (mein Verletzungsfeed übersieht sie).
- 0 % / ganz niedrige Werte (gesperrt, klarer Ersatz) fliegen aus dem Pool
  (kein Fielden von Nicht-Startern).
- **Overrides verfallen automatisch (seit 29.09.2026):** Jeder Wert ist an **eine
  GW** gebunden — Datei-Standard `"_fixture": "<fixture-slug>"` (+ `"_researched":
  "YYYY-MM-DD"`), oder je Eintrag `{"p": 0.5, "fixture": "…", "researched": "…"}`.
  Nur Overrides der gebauten GW greifen; andere gelten als verfallen, Einträge ohne
  Bindung werden ignoriert. Für eine neue GW: `_fixture`/`_researched` auf die neue
  GW setzen und **nur neu recherchierte** Werte übernehmen (alte als Objekt mit
  echtem `researched`-Datum, falls bewusst weiterverwendet).
- **Veraltet-Alarm:** Hat ein Spieler **nach** dem Recherchedatum erneut gespielt,
  meldet der Optimierer „Override älter als letztes Spiel (neu prüfen)" → vor der
  Deadline datiert neu bewerten (Froholdt-Fall: 90 % vom 24.09., dann 3' am 27.09.).

### Manuell deklarierte Wettbewerbe (API-unsichtbar) — nur je 1 GW

- Manche Wettbewerbe gibt die Sorare-API **nicht** aus (z. B. „Europäische
  Nationen" = SO5-Hot-Streak für UEFA-Nationalspieler, 4 In-Season + 1 Classic).
- **Grundregel:** Solche Wettbewerbe gelten **immer nur für die eine GW**, für
  die Nick sie nennt — nicht dauerhaft. Umgesetzt über **`manual_competitions.json`**,
  **gekeyt per Fixture-Slug** (z. B. `football-23-25-sep-2026`); nach der GW
  veralten sie automatisch (anderes Fixture). `lineup_suggest.py` liest die Datei
  standardmäßig. **Single-Use-Pool über ALLE Wettbewerbe:** Jede Karte darf pro GW
  nur **einmal** eingesetzt werden — auch manuelle Hot Streaks ziehen aus dem
  gemeinsamen, schrumpfenden Pool und verbrauchen ihn (kein Mehrfacheinsatz einer
  Karte über verschiedene Wettbewerbe). Hot Streaks werden zuerst befüllt (beste
  In-Season-Karten), danach der Rest nach projizierter Stärke.
- **Mehrere Karten desselben Spielers** (z. B. Classic + In-Season): jede ist
  **separat einsetzbar**. Derselbe Spieler darf **nicht zweimal in einem Lineup
  oder innerhalb eines Wettbewerbs** stehen, aber **je einmal in verschiedenen**
  Wettbewerben (z. B. In-Season-Pavlidis in der HS, Classic-Pavlidis in All-Star).
- Felder je Eintrag: `rarity, label, format, size, teams_cap, max_classic,
  hotstreak, national_confederation` (`"europe"` = nur UEFA-Nationalspieler).

### National-Abstellungen in Länderspielpausen (Optimierer erkennt sie)

**Problem, das das behebt:** In einer FIFA-Pause laufen manche Klub-Ligen weiter
(MLS, K-League …). Ist ein Spieler zu seiner Nationalmannschaft abgestellt, spielt
er sein **Klub**-Spiel im Fenster **nicht** (Sorare zeigt ~0 %) — mein
Vereins-Minuten-Modell würde ihn aber als Starter werten. (Genau das ging schief:
Bouanga/Son/Blake standen mit hoher Klub-Quote im Entwurf, obwohl abgestellt.)

- **Automatische Erkennung (UEFA):** `lineup_suggest.py` liest per **1 Query** alle
  Länderspiele des Fixtures (`anyGames`) und merkt sich pro Nation das **letzte**
  Spiel im Fenster. Ein Klubspieler wird als „auf National-Abstellung" markiert,
  wenn seine **Nation** im Fenster spielt **und** sein **Klubspiel ≤ 24 h nach**
  dem letzten Länderspiel seiner Nation liegt (sonst ist er zurück und spielt). Er
  wird dann **stark abgewertet** (×0,12) und geflaggt (`intl_duty`, `start_src:
  intl_duty_auto`) — kein harter Ausschluss, damit ein researched Override oder ein
  bestätigter Klub-Start ihn zurückholt. Selbst-abschaltend: reine Klub-GW → keine
  Länderspiele im Fixture → keine Abwertung. Ausgabe-Feld `international_break: true/false`.
- **Grenze der API:** Sorares Fixture führt **nur die Länderspiele, die es selbst
  austrägt** (praktisch **UEFA**). **Nicht-UEFA**-Abstellungen (viele
  CAF/AFC/CONCACAF/CONMEBOL — z. B. Gabun/Korea/Jamaika mit Klub in MLS/K-League)
  sind für die API **unsichtbar** → **manuell** deklarieren.
- **Manuelle Liste `international_callups.json`** (öffentlich, kein Secret; wird
  committet): **gekeyt per Fixture-Slug**, gilt nur für diese GW und veraltet danach
  automatisch. Format: `{ "<fixture>": ["player-slug", …] }`. Gelistete Spieler gelten
  fürs Klubspiel als **abwesend** (`start_prob 0` → aus dem Pool). `lineup_suggest.py`
  liest die Datei standardmäßig (`--international-callups`).
- **Präzedenz:** manuelle Callup-Liste (harter Drop) → **researched
  `start_overrides.json`** (schlägt die Auto-Erkennung; hier trägst du „spielt Klub
  doch, Quote X" ein) → automatische Erkennung. GRUNDREGEL #0 gilt: pro
  Callup/Override das Datum + die Sorare-% datiert gegenchecken.
- **Beim Sync-/Deadline-Check:** die `intl_duty`-Flags bzw. die stderr-Zeile
  „Länderspiel-Verdacht … Sorare-% prüfen" ernst nehmen und die Sorare-Prozente der
  betroffenen Klubspieler gegenchecken; Nicht-UEFA-Abgestellte in
  `international_callups.json` nachtragen.
- **National-Bank-Detektor (automatisch, `national_bench_signal`):** Spielt ein
  Spieler als Nächstes ein **Länderspiel** und hat seine Nation im selben Fenster
  schon gespielt, prüft der Optimierer sein Spiel-Log: **0 Minuten in ALLEN schon
  gespielten Fenster-Länderspielen → unbenutzte Bank → automatisch abgewertet**
  (×0,12, `start_src: natl_bench_auto`). Ersetzt die manuelle „für sein Land
  gebenchte"-Recherche (Geertruida-Fall). Ein researched Override schlägt das,
  falls jemand fürs nächste Spiel doch startet. Braucht Team-Typ im Log →
  `PLAYER_FIELDS` liest `homeTeam/awayTeam.__typename` je Spiel.

### Modell-Qualität messen & kalibrieren (`backtest.py`)

- **Projektion = „Score, wenn er spielt"** (`played_projection`): Blend aus den
  letzten 5 und 15 **gespielten** Spielen (Minuten>0), ohne DNP/Bank-Nullen.
  Backtest-belegt: MAE 18,5 → 14,6, Bias −9 → ~0.
- **Startquote leicht rekalibriert:** `p' = 0,9·p + 0,1·0,48` (Shrink Richtung
  Basisrate, Backtest-optimiert) — de-biast die Extreme, ändert die Rangfolge
  praktisch nicht.
- **Sperren-Erkennung (`suspension_signal`):** Rote Karte (glatt oder Gelb-Rot,
  `red_card`-Stat) im **letzten** Spiel desselben Wettbewerb-Streams (Klub vs.
  Nationalteam) wie das kommende → sehr wahrscheinlich gesperrt → abgewertet
  (×0,10, `start_src: suspension_risk`, stderr „Sperren-Verdacht … prüfen").
  Fängt die Sperren, die der Verletzungs-Feed übersieht. Gelb-Sperren (Schwellen
  je Liga) sind so **nicht** abgedeckt → dafür der API-Football-Feed (s. u.).
- **Sorare-eigene Signale** (`... on Player` in `PLAYER_FIELDS`):
  - **Sorare-% = `nextClassicFixturePlayingStatusOdds.starterOddsBasisPoints`**
    (/10000). Liefert seit **14.09.2026 `null`** ([sorare/api #693](https://github.com/sorare/api/issues/693),
    Stand 29.09. offen). Der Optimierer nutzt die Werte **automatisch**, sobald sie
    wieder kommen: Vorrang **vor allen Automatik-Signalen** (Modell, Sperre,
    Abstellung, Bank), aber **hinter** manueller Callup-Liste und recherchiertem
    Override (`start_src: sorare_odds`). Nur für die nächste GW (nicht bei
    `--fixture`); abschaltbar mit `--no-sorare-odds`.
  - **`playingStatus`** (STARTER/REGULAR/SUBSTITUTE/SUPER_SUBSTITUTE/NOT_PLAYING/
    RETIRED) = Klub-Rolle. Stimmt fast immer mit dem Modell überein (Kader-Check
    29.09.) → verschiebt **keine** Quote, sondern löst nur den Alarm „Sorare-Status
    widerspricht Startquote (prüfen)" aus (Bank-Status bei ≥55 %, oder Klub-STARTER
    bei ≤35 % in einem Klubspiel). Fängt v. a. **veraltete Overrides** (Froholdt-Fall).
  - **Vorhersage-Log** `logs/predictions.jsonl` (**wird committet**, s. Konventionen;
    `--log`, `''` = aus): je Lauf eine Zeile pro Spieler (Modell-%, Sorare-Status/-%,
    finale Quote + Quelle) → Grundlage, um Quellen später gegen echte Aufstellungen
    zu kalibrieren. **Test-/Experiment-Läufe immer mit `--log ''`**, damit das Log
    nur echte Vorhersagen enthält.
- **API-Football-Feed (`injuries_feed.py`)**: Verletzungs- **und Sperr**meldungen
  (inkl. **Gelbsperren**) je Spiel, Abruf pro Tag des GW-Fensters (Cache 3 h in
  `.cache/`, Free-Plan ~100 Anfragen/Tag). Zuordnung zu Sorare-Spielern über
  Name (auch „M. Nachname"/Rufname) + Team + Anstoß ±36 h; mehrdeutig → ignoriert.
  „Missing Fixture" → ×0,10 (`apif_out`), „Questionable" → ×0,60 (`apif_doubtful`),
  stderr „API-Football meldet (prüfen)". Vorrang: nach recherchiertem Override und
  Sorare-%, **vor** den eigenen Heuristiken (Rot-Karte, Abstellung, Bank). Ohne
  Host/Key: automatischer Rückfall. **Seit 29.09.2026 eingerichtet** (Cloud-API-
  Credential, Free-Plan).
  - **Free-Plan-Grenze (live geprüft 29.09.):** aktuelle Meldungen nur für Spiele
    **von gestern bis morgen**; spätere Tage des GW-Fensters werden übersprungen
    (stderr „Tage außerhalb des Plans übersprungen") → diese Spiele weiter manuell
    prüfen. Liga/Saison-Abfragen nur für 2022–2024. Abgelehnte Anfragen kosten
    kein Kontingent. Pro-Plan (~19 $/Monat) würde die Grenze aufheben.
  - **Meldet auch Länderspiel-Abstellungen** („Missing Fixture: International
    duty") für **alle** Verbände → schließt die Nicht-UEFA-Lücke (Bouanga/Son/
    Blake-Fall) für Spiele im Free-Fenster; `international_callups.json` nur noch
    für Spiele außerhalb des Fensters nötig. Flag `intl_duty`.
  - Nations-League-Spiele hatten am 29.09. **keine** Meldungen (Abdeckung v. a.
    Klubligen, z. B. MLS).
- **Treffer-Bilanz & Lernkreislauf (`evaluate.py`, seit 29.09.2026):** gleicht je
  Spieler & Spiel die **letzte Vorhersage vor Anpfiff** aus `logs/predictions.jsonl`
  mit dem Ergebnis ab — Startelf exakt über Sorares `gameStarted` (nicht über
  Minuten), dazu Minuten/Punkte. Bericht: Brier gesamt + **je Quelle** (Modell,
  Override, Sorare-%, API-Football, Abstellung/Bank/Rot), Trefferquote der
  Ausfall-Signale, reale Startquote je `playingStatus`, Projektions-MAE/Bias.
  **Lernen:** schreibt `calibration.json` = regularisierte Platt-Skalierung je
  Quelle (geschrumpft zur Gesamtkalibrierung, diese zu „keine Änderung") + ein
  Projektions-Faktor. `lineup_suggest.py` wendet sie automatisch an, **sobald ≥ 30
  Spiele ausgewertet** sind (`active`); gelernt wird aus der **Rohquote**
  (`start_prob_raw` im Log), damit sich der Kreislauf nicht selbst verstärkt.
  `logs/evaluation.json` und `calibration.json` werden **committet** (nötig im
  nächsten Container). Tägliche Routine „Sorare Treffer-Bilanz" fährt das + meldet.
  **Projektions-Faktoren je Position × Spieltyp** (`proj_scale_groups`, z. B.
  `Defender|national`, ab 8 Spielen je Gruppe, zur globalen Skala geschrumpft):
  GW715 zeigte, dass Verteidiger in Länderspielen deutlich unter ihrer Klub-Form
  punkten. Gelernt aus `proj_raw` (Log-Feld, vor Skalierung), Position aus `pos`.
- **Log-Reihenfolge:** `playerGameScores` kommt **most-recent-first** (Index 0 =
  neuestes Spiel) — Recency-Gewichtung und `played_projection` nutzen genau diese
  Reihenfolge (kein Umdrehen).
- `python3 backtest.py nicktd7` misst Start-Kalibrierung + Projektions-MAE
  retrospektiv — nach jeder Modelländerung vorher/nachher vergleichen.

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

### B) Scouting-Report (Aufgabe 2) — `scout.py`
1. Suchraum/Anlass wählen (z. B. Ersatz für Kristensen = RV; oder offene Position,
   Nicks Ligen). Ggf. Benchmark-Spieler mit `--like <slug>`.
2. **Kandidaten-Namen** sammeln (WebSearch: formstarke/aufstrebende Spieler der
   passenden Position/Liga; Grundregel #0 fürs Datum). Slugs = firstname-lastname.
3. `python3 scout.py --like <slug> --candidates "slugA,slugB,…"` liefert je
   Kandidat: Form (L15/L5), **Matchup-adjustierte Form** (Form × Gegnerstärke
   des nächsten Spiels, gleiche `team_strength.json` wie der Optimierer),
   Einsatzrate, Verletzung, Marktpreis (Sales-Median) und P/L-Score +
   Empfehlung (Kaufen/Watchlist/Skip) + Zielpreis (−10 %). Rangierung nach der
   adjustierten Form. Unbekannter Gegner → neutral (×1,0).
   **Standardmäßig nur Kandidaten, die in der aktuellen GW auch spielen** (ein
   Ersatz „für jetzt" muss im Fenster antreten; `--all-games` hebt das auf).
   In Länderspiel-GWs also nur nominierte Nationalspieler mit Spiel im Fenster.
4. **Preis-Caveat:** der Median mischt Saisons und ist nur ein grober „ab-Preis";
   vor einem Kauf den echten aktuellen Floor der einsetzbaren Karte auf Sorare
   gegenprüfen (und `--season` für Präzision nutzen).
5. Ergebnis: ranked Watchlist mit klarer Empfehlung.

### C) Nächste-GW-Vorplanung — Pflicht, sobald die Classic-Deadline durch ist
Sobald eine Classic-Deadline (Di/Fr 16:00 CET/CEST) durch und die GW gelockt ist,
**sofort einen ersten Lineup-Entwurf für die KOMMENDE GW** erstellen (nicht warten,
bis Nick fragt):
1. `python3 lineup_suggest.py nicktd7 --json <scratchpad>/next.json` (das Skript
   ermittelt nach dem Lock automatisch die nächste GW).
2. **Overrides der alten GW verfallen automatisch** (GW-Bindung, s. o.) → in einer
   reinen Club-GW greift ohne Zutun wieder das Vereinsmodell. Länderspiel-GW →
   neu recherchierte Overrides mit `_fixture` der neuen GW anlegen.
   **⚠️ Achtung Länderspielpause:** Eine Woche hat zwei Nationalspiel-Runden
   (Matchday 1 + 2). Auch die **Wochenend-GW** enthält dann noch Nationalspiele
   (Matchday 2, ~Sa–Mo) → NICHT als Club-GW behandeln, Overrides **behalten**;
   nur die **Gegner ändern sich** → `team_strength.json` für die neuen Gegner
   auffrischen. Erst die GW NACH der Pause ist wieder reine Club-GW.
3. Entwurf als Tabellen zeigen (mit Kapitän), offene Startelf-/Verfügbarkeitsfragen
   markieren; **final** beim nächsten Deadline-Check (~1,5 h vorher) datiert prüfen
   (GRUNDREGEL #0). Baseline erst nach Nicks Sorare-Bestätigung nachziehen.

## Konventionen

- Entwicklungszweig für Änderungen: `claude/sorare-account-management-4vdfzk`.
- Laufzeit-Ausgaben (`club.json`, `rewards.json`, `lineups.json`, `dashboard.html`,
  `*.csv`) sind Wegwerf-Artefakte — **nicht** committen, wenn sie Account-Daten
  enthalten; im Scratchpad oder als gitignored Dateien halten.
- **Ausnahme (Nicks Entscheidung, 29.09.2026):** `logs/predictions.jsonl` wird
  **bewusst committet**, obwohl das Repo **öffentlich** ist (Spielernamen +
  meine Startquoten werden sichtbar; Nick hat das akzeptiert). Grund: Der
  Container ist flüchtig, ohne Commit ginge das Log für die Kalibrierung verloren.
  Nach jedem echten `lineup_suggest.py`-Lauf das Log mit committen + pushen.
  Ebenso `logs/evaluation.json` + `calibration.json` nach jedem `evaluate.py`-Lauf.
- Neue Recherche-/Scouting-Tools als eigenständige Stdlib-Skripte im gleichen
  Stil ergänzen (Docstring mit Usage, `graphql`/`load_env` aus `sorare_client`).
