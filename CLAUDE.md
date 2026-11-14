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
| Voraussichtliche Startelf (SofaScore) | `python3 sofascore_lineups.py "Real Madrid"` — im Optimierer **standardmäßig an** (`--no-sofascore` = aus), s. u. |
| HTML-Dashboard aus club.json | `python3 build_dashboard.py club.json --out dashboard.html` |
| **Web-Dashboard (Next.js)** | `dashboard/` — Übersicht/Aufstellungen/Kader/GW-Bilanz/Modell; Daten serverseitig vom Backend (`SORAREBUDDY_API_URL`) oder aus den lokalen JSONs; Hosting auf dem Hostinger-VPS: `deploy/hostinger.md` §8 (`deploy/install-dashboard.sh`) |

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
- **Sorare-App-% von Nick als eigene Quelle (seit 02.10.2026):** Nennt Nick
  Prozente aus der App, als Override mit `"src": "sorare_app"` eintragen
  (`{"p": 0.3, "fixture": "…", "researched": "YYYY-MM-DD", "src": "sorare_app"}`)
  und **sofort** einen geloggten Lauf machen. Nur so landet die Zahl im
  Vorhersage-Log und die Treffer-Bilanz misst sie getrennt. Bei der GW717-Deadline
  lag die App **4 von 4** richtig, wo meine Recherche danebenlag (Vagiannidis,
  Schlotterbeck, Pickford, Thiaw). Die Werte waren aber nie geloggt, weil ich nur
  die Aufstellung umgebaut hatte. Beim Deadline-Check deshalb Nick **gezielt nach
  den App-% der knappen Fälle fragen**; App-% schlägt meine Recherche.
  **Bestätigt am 02.10. (Lacroix):** App 10 % gegen vier datierte Vorschauen + Spiel-Log
  (2× Start) → Ergebnis: 3 Min. als Joker. Die App lag damit **5 von 5** richtig, wo sie
  meiner Recherche widersprach. Bei Widerspruch App-% übernehmen, nicht die Recherche.
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
- **Von Nick bereits gesetzte Teams (`"fixed"`, seit 08.10.2026):** Hat Nick in
  einem API-unsichtbaren Wettbewerb schon eine Aufstellung gesetzt (Anlass:
  Champions' Inferno, Stufe 1, GW720), dann `"fixed": ["player-slug", …]` (+
  `"captain"`) in den Eintrag. Der Optimierer rechnet dort nichts, nimmt die Karten
  aber **zuerst aus dem Single-Use-Pool** und zeigt das Team als `[gesetzt]` —
  sonst würde er z. B. Guirassy nochmal als All-Star-Kapitän verplanen. Spieler
  ohne Spiel im Fenster / mit Startquote < 10 % lösen eine WARNING aus. Karten-
  Slug statt Spieler-Slug, wenn Nick mehrere Karten des Spielers hat.
  **Lehre GW720 (10.10.2026):** Beim Zusammenstellen eines solchen Teams **jede**
  Karte (auch die Classic-Karten, nicht nur die neu gescouteten) vor der Deadline
  einzeln datiert prüfen (Presse ≤ 7 Tage + SofaScore-XI). Dmitrović (TW, 93 %
  Modell) stand nicht im Tor — ein Artikel vom 03.10. hatte den Wechsel zu
  Fortuño angedeutet, ich hatte nur die Inferno-Karten recherchiert. Das
  Inferno-Team kam so auf ~182 statt 320 Punkte.

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
  bestätigter Klub-Start ihn zurückholt. **Seit 05.10.2026 nur noch, wenn er laut
  Spiel-Log in diesem Fenster in einem Länderspielkader stand** (auch 0 Minuten):
  Buksa und Aitor Fraga wurden nur wegen ihres Landes geflaggt (4–6 %) und
  starteten ihr Klubspiel (nicht nominiert). Grenze: Wer nominiert ist, aber noch
  kein Länderspiel im Fenster hatte, wird nicht erkannt → `international_callups.json`.
  Selbst-abschaltend: reine Klub-GW → keine
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
  (seit 03.10.2026 ×0,4, `start_src: natl_bench_soft`; 02.10. ×0,6; vorher ×0,12 =
  `natl_bench_auto`). Bilanz 03.10.: insgesamt 2 von 11 Markierten gestartet, Brier
  zwischen ×0,3 und ×0,5 flach, Optimum ×0,4. Die Treffer-Bilanz vom 02.10. zeigte: 2 von 6 Markierten
  starteten trotzdem (Krejčí, Baribo), Nationaltrainer rotieren zwischen den
  Spieltagen stark. Ersetzt die manuelle „für sein Land
  gebenchte"-Recherche (Geertruida-Fall). Ein researched Override schlägt das,
  falls jemand fürs nächste Spiel doch startet. Braucht Team-Typ im Log →
  `PLAYER_FIELDS` liest `homeTeam/awayTeam.__typename` je Spiel.

### Voraussichtliche Aufstellungen aus SofaScore (seit 07.10.2026, Nicks Auftrag)

- **Anlass:** Meine Recherche-Quoten im Mittelbereich waren Münzwurf-Qualität
  (Bilanz 07.10.). Die voraussichtliche Elf 1–2 Tage vor dem Spiel ist für
  Klub-GWs das stärkste verfügbare Signal. `api.sofascore.com` ist vom
  Cloud-Container aus **erreichbar** (am 07.10. geprüft; der alte Hinweis
  „blockt Datacenter-IPs" stimmte nicht mehr) → **kein VPS-Umweg nötig**. Fällt
  die Erreichbarkeit weg, läuft der Optimierer automatisch ohne (Ping-Check).
- **Was passiert:** `lineup_suggest.py` löst je Team (Feld `team_name`, also auch
  Nationalteams) die nächste Partie auf SofaScore auf und übernimmt die
  XI **nur, wenn es dieselbe Partie ist** (Anstoß ±3 h; sonst z. B. Pokalspiel
  dazwischen → kein Signal). Quellen im Log/`start_src`:
  - `sofa_pred_start` (in der voraussichtlichen XI): `max(p, 0,2·p + 0,8·0,80)` —
    zwei übereinstimmende Signale senken die Quote nie (bis 11.10.2026:
    `0,35·p + 0,65·0,85`, s. Bilanz 11.10.);
  - `sofa_pred_bench` (explizit Bank; voraussichtliche XIs haben meist keine Bank):
    `0,35·p + 0,65·0,18`;
  - `sofa_pred_out` (volle XI ≥ 11 Namen veröffentlicht, Spieler fehlt):
    `0,5·p + 0,5·0,18` — schwächer, weil hier auch **Namens-Fehlabgleiche** landen;
  - `sofa_conf_start/bench/out` (offizieller Spielberichtsbogen, ~1 h vor Anpfiff):
    0,95 / 0,08 / max. 0,10.
- **Vorrang:** Callup-Liste → recherchierter Override / App-% → **bestätigte XI** →
  Sorare-% → **voraussichtliche XI** (verliert aber gegen API-Football „Missing
  Fixture" und Rot-Karten-Sperre, weil voraussichtliche XIs Sperren oft ignorieren)
  → Abstellung/Bank → Modell. In reinen Klub-GWs gibt es keine Overrides → SofaScore
  ist dort praktisch die Hauptquelle.
- **Namensabgleich:** normalisiert (Akzente, ß→ss, ø→o …), exakt oder über
  Namens-Tokens (deckt „Minjae Kim" vs „Kim Min-jae", „Alejandro" vs „Álex
  Grimaldo"). Teamnamen: Sorares lange Namen werden um Sponsor-/Rechtsform-Tokens
  gekürzt („SK Puntigamer Sturm Graz" → „Sturm Graz", „Trabzonspor Kulübü");
  Aliase in `sofascore_lineups._ALIASES` (Inter, Sanse, Sporting CP, South Korea)
  + deutsche Nationsnamen (`_NATION_DE`: „Deutschland" → Germany …). Testlauf
  07.10.: 140 Teams alle gefunden, 102 mit XI, 268 Spieler mit Signal.
- **Team-Auflösung nach Popularität (seit 10.10.2026, Anlass Dmitrović):** Der
  Cache-Audit nach der Bilanz 10.10. fand **22 von 140 Teams falsch aufgelöst**:
  Frauenteams (Chelsea, Villarreal, Sporting, Standard, Nice, Rio Ave, Marítimo,
  Racing), Reserve-/Jugendteams (Espanyol **B**, Leeds U21, Bologna U19, Chicago
  Fire II, Mechelen Reserve) und Namensvettern mit einer Handvoll Followern
  („Arsenal FC" aus Guinea-Bissau, „Juventus FC" mit 45 Nutzern, Boca, River,
  Beşiktaş, Toulouse, Aston Villa, QPR statt Rangers, Benfica-Nebenverein). Der
  exakte Namensabgleich war die Falle. Jetzt: alle Treffer der Namensvarianten
  werden gesammelt, Frauen- und Reserveteams fliegen raus (außer der Sorare-Name
  ist selbst ein B-Team), Nationalteams nur bei exaktem Namen, dann gewinnt das
  Team mit den meisten SofaScore-Followern (`userCount`); ein exakter Name nur,
  wenn er mindestens ein Drittel so populär ist. **`python3 sofascore_lineups.py
  --audit`** listet den Cache mit Name/Geschlecht/Followern und markiert
  Verdachtsfälle — nach jeder Änderung an der Auflösung laufen lassen. Ergebnis
  10.10.: 87 Teams, 0 markiert; GW721-Pool 72 Teams, 55 mit XI (vorher 48).
  Folge für die Bilanz: Für die betroffenen Klubs gab es bis 10.10. **kein**
  SofaScore-Signal (Dmitrović 93 % Modell → spielte nicht; Espanyol war als
  Espanyol B aufgelöst), Fehlsignale sind wegen des Anstoß-Abgleichs (±3 h)
  nicht aufgetreten.
- **Namens-Token-Abgleich (seit 20.10.2026, Anlass GW723-Deadline-Check):** Die
  Popularitätsregel hatte eine neue Lücke: Die Einzelwort-Suchen („Madrid",
  „United", „Club") holten berühmte Namensvettern in den Pool, die dann auf
  Popularität gewannen. Beim finalen Check fiel auf: Athletic Club → Atlético
  Madrid, Atlético → Real Madrid (Unai Simón, Laporte, Grimaldo, Baena ohne
  SofaScore-Signal). Ein Neuaufbau über alle 176 bekannten Teamnamen fand
  **20 falsche Zuordnungen**, u. a. Manchester United → Man City, Newcastle/Leeds/
  DC United/Incheon → Man United, Chicago Fire → Chicago Bulls, LAFC → Lakers,
  FC Dallas → Mavericks, Pohang → Pittsburgh Steelers, Sporting KC → Sporting CP,
  Paris FC → PSG, Monaco → Bayern, Sparta/Excelsior → Feyenoord. `--audit` hatte
  das nicht markiert. Wegen des Anstoß-Abgleichs gab es keine Fehlsignale, aber
  diese Teams hatten **kein** Signal. Jetzt gilt:
  - Treffer unter 1000 Followern fliegen raus, sobald es größere gibt.
  - Nur die Treffer mit der besten Namens-Token-Überschneidung bleiben (Jaccard,
    tolerant für „Olympiakos"/„Olympiacos" und „Çorum"/„Çorumspor").
  - Danach entscheidet die Popularität.
  - „2" zählt als Reserve-Kennung („OGC Nice 2").

  Ergebnis des Neuaufbaus: 11 Korrekturen gegenüber dem (schon von Hand
  bereinigten) Cache, keine Verschlechterung. GW724-Pool: 135 Teams, 107 mit XI.
  Kein Backtest möglich (kein XI-Archiv), es ist ein reiner Datenfix.
- **Beim Deadline-Check:** die stderr-Zeile „SofaScore sieht nicht in der Startelf
  (prüfen, auch Namensabgleich)" durchgehen — v. a. Spieler mit Sorare-Status
  STARTER (erscheinen zusätzlich unter „Sorare-Status widerspricht Startquote").
  Audit 07.10.: alle geprüften `pred_out`-Fälle waren echt (Krejčí, Kristensen,
  Kim Min-jae, Grimaldo, Moura nicht in der XI), nur Groß/Gross war ein ß-Fehler
  (behoben).
- **Kalibrierung:** sofa_*-Quellen gelten in `evaluate.py` als **extern** (Prior
  „keine Änderung", kein Status-Offset) und werden erst ab n ≥ 20 je Spieltyp
  separat gelernt; `sofa_pred_bench/out`, `sofa_conf_bench/out` zählen als
  Ausfall-Signale. **Noch nicht backgetestet** (kein historisches XI-Archiv) → GW720
  liefert die erste Messung; Gewichte 0,65/0,5 sind Startwerte.
- Cache: `.cache/sofa_teams.json` (Team-IDs, dauerhaft) und `.cache/sofa_xi.json`
  (XIs, 30 Min.) — gitignored.

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
  **Seit 16.10.2026 je Wettbewerb:** geprüft wird das letzte Spiel im **selben
  Wettbewerb** wie das kommende (`competition.slug` aus `nextGame` und Spiel-Log),
  nicht mehr nur das letzte Spiel überhaupt. Anlass: Elmas' Serie-A-Rot wurde
  gegen sein Conference-League-Spiel gezählt (8 %, er spielte 90 Minuten) und
  danach für die Serie A vergessen, wo er gesperrt war; Olises CL-Rot hätte ihn
  in der Bundesliga gesperrt. Ohne bekannten Wettbewerb gilt die alte Regel.
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
- **API-Football-Account am 02.10.2026 gesperrt** („Your account is suspended“):
  Der Feed fällt automatisch zurück (kein Absturz), bis Nick den Account im
  API-Football-Dashboard klärt. Bis dahin Verletzungen/Sperren manuell prüfen.
- **Treffer-Bilanz & Lernkreislauf (`evaluate.py`, seit 29.09.2026):** gleicht je
  Spieler & Spiel die **letzte Vorhersage vor Anpfiff** aus `logs/predictions.jsonl`
  mit dem Ergebnis ab — Startelf exakt über Sorares `gameStarted` (nicht über
  Minuten), dazu Minuten/Punkte. Bericht: Brier gesamt + **je Quelle** (Modell,
  Override, Sorare-%, API-Football, Abstellung/Bank/Rot), Trefferquote der
  Ausfall-Signale, reale Startquote je `playingStatus`, Projektions-MAE/Bias.
  **Lernen:** schreibt `calibration.json` mit:
  - einer regularisierten Platt-Skalierung je Quelle, **getrennt je Spieltyp**
    (`by_type.national` / `by_type.club`, seit 02.10.2026), damit eine
    Länderspielpause die Klub-Quoten nicht verbiegt;
  - optional einem Offset je `playingStatus`;
  - Projektions-Faktoren.

  **Out-of-sample-Sperre (seit 02.10.2026):** Ein Teil der Kalibrierung wird nur
  `active`, wenn er die Rohwerte im **Leave-one-out**-Test schlägt (Brier bzw.
  Projektions-MAE). Ein Spieltyp braucht dafür ≥ 20 Spiele. Anlass: Am 02.10. sah
  die Kalibrierung auf den Trainingsdaten gut aus (Brier 0,1995 → 0,189), war aber
  out-of-sample **schlechter** (0,204), also reines Lernen von Rauschen.
  **Hysterese beim An-/Abschalten (seit 13.10.2026, Nicks Freigabe vom 12.10.):**
  Die Klub-Kalibrierung sprang bei Leave-one-out-Gewinnen um 0,001 täglich zwischen
  aktiv und neutral hin und her und baute dabei jedes Mal den halben Entwurf um.
  Jetzt schaltet ein Spieltyp nur **ein**, wenn er die Rohquoten um ≥ 0,002 Brier
  schlägt (`CALIB_ON_GAIN`), und erst wieder **aus**, wenn er klar schlechter ist
  (Gewinn < −0,001, `CALIB_OFF_GAIN`). Projektions-Faktoren analog (ein ab 0,05,
  aus unter −0,02 MAE-Punkten). Der Vorzustand kommt aus der alten
  `calibration.json` (`loo.was_active`, `loo.gain`). Nachgespielt auf der Historie
  02.–13.10.: Klub hätte 10.→13.10. durchgehend aktiv bleiben (statt an/aus/an),
  Länderspiele schalten einen Tag später ein (04.10. statt 03.10. mit Gewinn 0,0003).
  `lineup_suggest.py` wendet nur die aktiven Teile an. Gelernt wird aus der **Rohquote**
  (`start_prob_raw` im Log), damit sich der Kreislauf nicht selbst verstärkt.
  `logs/evaluation.json`, `logs/outcomes.json` (ermittelte Ergebnisse, seit
  30.10.2026) und `calibration.json` werden **committet** (nötig im nächsten
  Container). Tägliche Routine „Sorare Treffer-Bilanz" fährt das + meldet.
  **Projektions-Faktoren je Position × Spieltyp** (`proj_scale_groups`, z. B.
  `Defender|national`, ab 8 Spielen je Gruppe, zur globalen Skala geschrumpft):
  GW715 zeigte, dass Verteidiger in Länderspielen deutlich unter ihrer Klub-Form
  punkten. Gelernt aus `proj_raw` (Log-Feld, vor Skalierung), Position aus `pos`.
- **Bilanz 03.10.2026 (83 Spiele):** Das Vereinsmodell ist in **Länderspielen** zu
  sicher. Spieler mit Klub-Status STARTER: Modell 85 %, real gestartet 65 % (n=34).
  6 von 34 standen nicht einmal im Kader (z. B. Wanner, Bolla). Die Kalibrierung
  für Länderspiele ist seitdem aktiv (b≈0,71, zieht die Quoten zur Mitte, gewinnt
  knapp im Leave-one-out-Test). Lehre für Deadline-Checks: Bei Länderspielen jeden
  aufgestellten Spieler mit Modell-Quote auf **Kader/Abreise** prüfen, nicht nur
  die recherchierten.
- **Bilanz 04.10.2026 (106 Spiele):** **Torhüter in Länderspielen** sind mit reiner
  Modell-Quote unbrauchbar: 76 % vorhergesagt, 25 % gestartet (n=4, z. B. Unai Simón
  95 % → nicht gespielt, Kovář 79 % → nicht gespielt). Recherchierte Torhüter lagen
  dagegen genau richtig (34 % vs. 33 %, n=9). Umsetzung: kein Eingriff in die Quote
  (n zu klein), aber der Optimierer meldet „Torwart im Länderspiel nur mit
  Modell-Quote (Nummer 1 prüfen / App-%)“. Beim Deadline-Check jeden solchen
  Torwart recherchieren oder Nick nach den App-% fragen.
- **Bilanz 07.10.2026 (169 Spiele, davon 25 neu aus GW719, Brier dort 0,168):**
  Recherchierte Quoten im Mittelbereich (0,15–0,8, n=20) treffen im Schnitt
  (vorhergesagt ≈ 0,49, real ≈ 0,50), sind aber **innerhalb** dieses Bereichs nicht
  geordnet: 0,35–0,6 → 71 % gestartet, 0,6–0,8 → 38 %. Ein „unklarer“ Recherche-Fall
  ist also praktisch ein Münzwurf. Keine Modelländerung (n zu klein, nicht monoton).
  **Prozess-Lehre:** Beim letzten Check (14:50) standen Laporte und Baena in zwei
  datierten Vorschauen in der Startelf, der Override blieb aber bei 0,5. Beide
  starteten. Neue Belege beim finalen Check deshalb **sofort** in
  `start_overrides.json` übernehmen und einen geloggten Lauf machen, nicht nur im Chat
  nennen. GK-Alarm (Dúbravka → Greif spielte), Bank-Detektor (Wilson) und App-% (Noah
  Allen 0 %) lagen richtig.
- **Bilanz 10.10.2026 (208 Spiele, davon 37 neu = Freitag GW720, erste Klub-GW
  mit SofaScore):** `sofa_pred_start` **12 von 14 gestartet** (vorhergesagt 79 %,
  real 86 %, Brier 0,13) — hob Bidstrup (31 → 66 %), Mads (33 → 67 %), Openda
  (43 → 70 %) und Kovář (51 → 73 %) richtig in die Startelf; Sané und Haidara
  kamen nur von der Bank. Startwert 0,85 bleibt (passt). `sofa_pred_out` 1 von 1
  daneben (Schlotterbeck 22 % → 90 Min.; Sorare-Status-Alarm hatte gewarnt) →
  n=1, keine Änderung, Gewicht 0,5 bleibt. **Reines Klub-Modell** (n=29) ist an
  den Rändern falsch: ≥ 90 % vorhergesagt → 71 % gestartet, < 50 % → 60 %
  gestartet. Die **Klub-Kalibrierung ist seit diesem Lauf aktiv** (n=53,
  b≈0,63, Leave-one-out 0,238 → 0,228) und zieht genau das zur Mitte.
  **Torhüter im Klubspiel** werden in der Projektion um ~21 Punkte unterschätzt
  (n=5: Kovář 85 vs. 41, Brey 74 vs. 29, Park 68 vs. 49) → noch kein Eingriff,
  `proj_scale_groups` lernt es ab 8 Spielen selbst. **Fehlgriffe:** Dmitrović
  93 % Modell → 0 Min. (El Gol Digital hatte am 03.10. den Torwartwechsel zu
  Fortuño angedeutet; Espanyol war bei SofaScore falsch aufgelöst, s. o.), Lee
  You-hyeon 93 % → Joker, Hwang Seo-woong 79 % → nicht im Kader (K-League nur
  Modell, keine SofaScore-Abdeckung geprüft). Recherche-Overrides (Dest 0,5 →
  Start, Perišić 0,5 → Joker, Geertruida 0,35 → fehlte, Wanner 0,05 → fehlte)
  lagen im Rahmen.
- **Bilanz 11.10.2026 (437 Spiele, davon 229 neu = Wochenende GW720):** Brier
  gesamt 0,186 (Basisrate 0,247). **SofaScore trägt:** `sofa_pred_start` n=105,
  vorhergesagt 82 %, real 81 %; gegenüber dem Modell allein Brier 0,178 → 0,149.
  `sofa_pred_out` n=69, vorhergesagt 30 %, real 25 %; Modell allein 0,222 → 0,183.
  Ausfall-Signale 72 von 95 richtig. **Innerhalb der voraussichtlichen XI sagt
  das Modell kaum noch etwas:** Modell < 50 % → 88 % gestartet, 50–70 % → 52 %.
  Schwachpunkt: Klub-Status REGULAR + `pred_start` (n=17) 77 % vorhergesagt, 53 %
  real. **Geändert:** `pred_start`-Gewicht 0,65 → 0,80, Zielwert 0,85 → 0,80
  (`SOFA_PRED_START_W`). Brier dieser Quelle 0,1490 → 0,1449, in beiden
  Zeithälften besser (0,136 → 0,130 und 0,162 → 0,160). Das Optimum im Raster
  (Gewicht 1,0, Ziel 0,70) gewinnt nur in der frühen Hälfte → bewusst nicht
  genommen. **Nicht geändert:** `pred_out` (10-fach-Kreuzvalidierung der
  gefitteten Werte 0,193 schlechter als die aktuellen 0,183). Die
  **Klub-Kalibrierung ist wieder neutral** (n=282, im Leave-one-out kein Gewinn
  mehr, weil die SofaScore-Quoten jetzt den Großteil tragen); der
  **Projektions-Faktor ist erstmals aktiv** (0,976, LOO-MAE 14,37 → 14,28;
  Klub-Torhüter 0,93). **Fehlgriff-Muster:** 6 von 32 Fehlgriffen standen gar
  nicht im Kader (Laporte, Vallci, Latte Lath, Laimer, Evander, Ayodele Thomas),
  Laporte und Laimer standen trotzdem in SofaScores voraussichtlicher XI.
  Die voraussichtliche Elf erkennt kurzfristige Kaderausfälle also nicht — beim
  Deadline-Check Spieler ohne Kaderplatz im letzten Spiel (`onGameSheet` false)
  trotz `pred_start` einzeln prüfen. Celentano (89 %, Stamm-Torwart) saß 90
  Minuten auf der Bank; Grund ungeklärt.
- **Bilanz 12.10.2026 (528 Spiele, davon 91 neu = Sonntag GW720 + MLS):** Brier
  gesamt 0,183. Neue Spiele: `sofa_pred_start` 0,143 (Modell allein 0,173),
  `sofa_pred_out` 0,162 (Modell allein 0,210), reines Modell 0,195. Die
  **Klub-Kalibrierung ist wieder aktiv** (n=373, b≈0,93, a≈−0,17, LOO 0,1782 →
  0,1772; senkt die Quoten leicht). **Die neuen `pred_start`-Gewichte vom 11.10.
  sind noch nicht gemessen:** Für die Wochenendspiele einer GW stammt die letzte
  geloggte Vorhersage vom Freitag vor dem Lock (danach rechnen die Syncs schon die
  nächste GW) — erste Messung erst mit GW721. **Fehlgriffe:** Szoboszlai (95 %,
  SofaScore-XI) und Zorgane (75 %) nicht im Kader; Becker, Aouchiche, Ebimbe gegen
  Freiburg alle drei auf der Bank (Vorhersage 2 Tage vor Anpfiff). Hohe Quoten
  (≥ 70 %) ohne Kaderplatz insgesamt 16 von 250 (6 %). **Nicht geändert:**
  `pred_out` liegt weiter etwas zu hoch (30 % vorhergesagt, 23 % real, n=94).
  Zielwert 0,18 → 0,12 wäre in beiden Zeithälften besser, in der späten aber nur
  um 0,0007 → zu wenig Beleg, nach GW721 erneut prüfen.
- **Bilanz 15.10.2026 (666 Spiele, davon 82 neu = GW721 Mittwoch + MLS):** Neue
  Spiele Brier 0,158. `sofa_pred_start` in Europacup-Wochen (Di–Do, n=37)
  vorhergesagt 81 %, real 78 %, also kaum schlechter als am Wochenende. Die
  Ausfälle dort waren Rotation von Stammspielern (Van Dijk, Guirassy,
  Schlotterbeck, Gulácsi), die keine Quelle vorher hatte. **`pred_out`-Zielwert
  0,12 statt 0,18 geprüft und verworfen:** roh in beiden Hälften besser, mit der
  aktiven Klub-Kalibrierung (die `pred_out` schon absenkt) aber kein Gewinn
  (0,1732 → 0,1731, späte Hälfte schlechter). **Offen:** Ein Joker-Einsatz im
  Europacup zählt fürs Wochenende als Nicht-Start (Van Dijk/Guirassy 95 → 81 %).
  Für GW722 per Override gelöst, n zu klein für eine Regel.
- **Bilanz 16.10.2026 (744 Spiele, davon 78 neu = Europa/Conference League Do
  15.10.):** Neue Spiele Brier 0,203, deutlich schlechter als am Wochenende.
  Europacup-Spiele (Di–Do) gesamt: `pred_start` 0,81 → 80 % gestartet (Brier
  0,16–0,17 vs. 0,147 am Wochenende), `pred_out` 0,24–0,27 → 28–32 % (am
  Wochenende 23 %). Die voraussichtliche Elf ist im Europacup also unschärfer
  (Rotation: Freuler, Kamada, Schick, Pulisic, Šulc auf der Bank). Im Mittel
  kalibriert → keine Änderung. **Rot-Karten-Heuristik ist wettbewerbsblind:**
  Elmas (Serie-A-Rot) wurde für den Europacup auf 8 % gesetzt und spielte 90
  Minuten; umgekehrt galt er danach für die Serie A als frei, obwohl gesperrt.
  Olise (CL-Rot) galt für die Bundesliga als gesperrt. Fix (Sperre nur im
  selben Wettbewerb) am 16.10. nach dem GW722-Lock umgesetzt (s. Sperren-Erkennung).
- **Bilanz 17.10.2026 (786 Spiele, davon 42 neu = Freitag GW722):** Neue Spiele
  Brier 0,115. Erste Wochenend-Messung der `pred_start`-Gewichte vom 11.10.:
  vorhergesagt 80 %, 91 % gestartet (n=23, Brier 0,084); `pred_out` 24 % → 24 %.
  Fehlgriffe: Trippier (74 %, nicht im Kader), Van der Brempt, Götze, Chaïbi
  (je ~25 %, gestartet). Keine Änderung (n zu klein, eher zu vorsichtig als zu
  sicher).
- **Bilanz 18.10.2026 (942 Spiele, davon 156 neu = Samstag GW722):** Neue Spiele
  Brier 0,141. `pred_start` 80 % → 91 % gestartet (n=46), Modell allein 55 % →
  55 %. `pred_start`-Zielwert 0,80 gegen 0,85/0,88/0,90 geprüft (n=293): 0,80
  bleibt am besten (0,1356 vs. 0,1364+), am Wochenende wie unter der Woche →
  keine Änderung. **Startsignal aus `gameStarted` statt Minuten geprüft und
  verworfen** (Anlass: Kane 59 Min. als Starter → Wochenquote 89 → 79 %):
  Backtest über 350 Spieler / 3823 Spiele, Brier 0,1840 (Minuten) gegen 0,1858
  (`gameStarted` = 1,0), in beiden Hälften schlechter. Früh ausgewechselte
  Starter fehlen offenbar öfter beim nächsten Spiel; die Minuten-Regel bleibt.
- **Bilanz 19.10.2026 (1064 Spiele, davon 122 neu = Sonntag GW722 + MLS):** Neue
  Spiele Brier 0,163. `pred_start` 79 % → 84 % (n=51), `pred_out` 26 % → 33 %
  (n=43, höher als sonst). Fehlgriffe gehäuft in der Eredivisie (Groningen:
  Tsygankov, Arokodare nicht in der Startelf, Janse startete) und bei Sturm
  Graz–GAK (Hödl 90 % → Bank, Helać 12 % → Start). Keine Änderung: alle Quellen
  über die gesamte Historie kalibriert, Tagesschwankung.
- **Bilanz 20.10.2026 (1073 Spiele, davon 9 neu = Montag GW722):** Neue Spiele
  Brier 0,158. Fehlgriffe: David Martínez (Sorare SUPER_SUBSTITUTE, `pred_start`
  72 %) nicht gestartet; Kristensen (46 %) und Marmoush (42 %) trotz `pred_out`
  in der Startelf. n zu klein → keine Änderung. Gesamt `pred_start` 81 % → 83 %
  (n=348), `pred_out` 28 % → 27 % (n=264), beide kalibriert.
- **Bilanz 21.10.2026 (1104 Spiele, davon 31 neu = Dienstag GW723, Europacup):**
  Neue Spiele Brier 0,149. `pred_start` 84 % → 88 % (n=17), `pred_out`
  32 % → 30 % (n=10). Fehlgriffe: Wirtz und Obispo (je 90 %, `pred_start`) auf
  der Bank (Rotation, keine Quelle hatte es); Krejčí, Gulácsi (Sorare STARTER,
  `pred_out` 31–39 %) und Peprah Oppong (15 %) gestartet. **Geprüft und
  verworfen:** `playingStatus`-Offset auch für die SofaScore-Quellen (bisher
  ausgenommen). Auffällig sind `pred_out`+SUBSTITUTE (23 % vorhergesagt, 12 %
  real, n=80) und `pred_out`+SUPER_SUBSTITUTE (28 % → 43 %, n=30). Im
  Leave-one-out über 949 Klubspiele aber kein Gewinn (0,1636 → 0,1634–0,1635),
  in der frühen Hälfte schlechter → nicht übernommen.
- **Bilanz 22.10.2026 (1156 Spiele, davon 52 neu = Mittwoch GW723 + MLS):**
  Neue Spiele Brier 0,169. `pred_start` 82 % → 84 % (n=25), `pred_out` 35 % →
  47 % (n=17, zu niedrig, aber kleine Zahl). Fehlgriffe: Kimmich (94 %, Todesfall
  in der Familie, erst am Spieltag bekannt), Lisandro Martínez (79 %, nicht im
  Kader). **Bayern-Torwart erneut falsch:** SofaScore hatte Urbig (78 %), Neuer
  (31 %) stand im Tor. Keine Modelländerung (n zu klein).
  **Prozess-Fehler behoben:** Ohne `APIKEY`-Header (Container-Neustart, Key-
  Injektion fehlte) lehnt Sorare jede Abfrage über Komplexität 500 ab.
  `evaluate.py` hat die Fehler verschluckt und jedes Spiel als Nicht-Start
  gewertet (Brier 0,41, Kalibrierung auf Müll neu gefittet). Die Dateien habe ich
  verworfen, nichts davon ist committet. `fetch_outcomes` verkleinert die Batches
  jetzt bis auf 1 und bricht ab, statt leere Daten zu schreiben.
  `lineup_suggest.py` geht seit 21.10. ebenfalls bis Batchgröße 1 herunter.
- **Bilanz 23.10.2026 (1233 Spiele, davon 77 neu = Donnerstag GW723, Europa/
  Conference League):** Neue Spiele Brier 0,176. `pred_start` 81 % → 71 %
  (n=42, Brier 0,20): Rotation in Hoffenheim, Benfica, Leverkusen, Atalanta
  (Abner, Dahl, Flekken nicht eingesetzt; Maza, Sudakov, Hložek als Joker).
  `pred_out` 29 % → 26 %. **Geprüft, nicht geändert:** `pred_start` nach Wochentag
  über die ganze Historie: Di 82 % → 90 % (n=39), Mi 83 % → 76 % (n=42), Do 81 % →
  76 % (n=86), Wochenende 81 % → 85 % (n=265). Unter der Woche zusammen nur
  ~3 Punkte zu hoch, Di und Mi widersprechen sich. Ein Donnerstag-Abschlag von
  0,05 brächte gesamt etwa 0,0002 Brier. Zu wenig für ein neues Feature.
- **Bilanz 24.10.2026 (1267 Spiele, davon 34 neu = Freitag GW724):** Erste
  Spiele ohne SofaScore (seit 21.10. blockt SofaScore den Container mit HTTP 403,
  auch nach Container-Neustart). Nur Modell: Brier 0,142, vorhergesagt 48 %,
  gestartet 59 %. Fehlgriffe vor allem bei Vitória Guimarães–Santa Clara
  (Tavares 18 %, Vieites 28 %, Dominguez 42 % gestartet). Tavares stand vor der
  Sperre in SofaScores voraussichtlicher XI. Keine Änderung (n=34).
- **Bilanz 25.10.2026 (1437 Spiele, davon 170 neu = Samstag GW724 + MLS, nur
  Modell):** Brier 0,151, vorhergesagt 59 %, gestartet 67 %. Ohne SofaScore ist
  das Modell bei Sorare-STARTERN zu vorsichtig: 78 % vorhergesagt, 92 % gestartet
  (n=92); Quoten ≥ 85 % → 95 % gestartet (n=41). Die Kalibrierung lernt das schon
  selbst: Status-Offsets STARTER +0,19, SUBSTITUTE −0,35 (Klub-LOO 0,164 → 0,161).
  Keine Handänderung. Fehlgriffe: Messi (91 %, Joker 34'), Trapp und Karaman
  (91/74 %, nicht im Kader), Collins und Theate (17/24 %, 90' gestartet).
- **Bilanz 26.10.2026 (1584 Spiele, davon 147 neu = Sonntag GW724 + MLS, nur
  Modell):** Brier 0,183 (schlechtester Tag seit SofaScore-Ausfall). Fehlgriffe
  mit Kader-Ausfällen ohne Vorwarnung: Lautaro Blanco und Martínez Quarta (je
  93 %, beide nicht im Kader, beide im GW724-Entwurf All Star #1), Elvedi (91 %,
  nicht im Kader). Newcastle-Abwehr komplett anders als erwartet: Schär (6 %) und
  Burn (12 %) 90' gestartet, Thiaw (86 %) 1'. Ohne voraussichtliche Elf sind
  solche Ausfälle nicht zu sehen. Die Kalibrierung verstärkt die Status-Offsets
  weiter (STARTER +0,26, REGULAR −0,25; Klub-LOO 0,165 → 0,162). Keine
  Handänderung.
- **Bilanz 27.10.2026 (1603 Spiele, davon 19 neu = Montag GW724):** Brier 0,195.
  Morton, Abner und Bidstrup (je ~60 %) bei PSG nicht im Kader, Samuel Soares
  (22 %, Sorare NOT_PLAYING) stand 90' im Benfica-Tor. n=19 → keine Änderung.
- **Bilanz 28.10.2026 (1606 Spiele, davon 3 neu = Dienstag GW725):** Alle drei
  nicht gestartet. Die Recherche beim finalen Check lag richtig: Murić (Modell 53 %
  → recherchiert 30 %, Turati im Tor) und Van der Brempt (61 % → 45 %,
  Cinquegrano) saßen auf der Bank, Omoruyi (22 %) ebenfalls. Klub-Kalibrierung
  weiter aktiv (LOO 0,1656 → 0,1622). n=3 → keine Änderung.
- **Bilanz 29.10.2026 (1659 Spiele, davon 53 neu = Mittwoch GW725, v. a. MLS, nur
  Modell):** Brier 0,205, vorhergesagt 65 %, gestartet 57 %. Fehlgriffe:
  - Nashville hatte am 24.10. den Supporters' Shield sicher und rotierte gegen
    Philadelphia (SixOneFive, 28.10.): Surridge und Mukhtar (je 94–96 %) nur Joker,
    Corcoran (93 %) nicht im Kader.
  - Damiani (94 %) fehlte wegen Gelbsperre (PhillySoccerPage, 28.10.). Gelbsperren
    deckt nur API-Football ab, und der Free-Plan sieht das Spiel erst einen Tag
    vorher.
  - Freese: recherchiert 36 % nach der Schulterverletzung vom 24.10. (keine
    Diagnose), Modell 71 %. Er spielte 90 Minuten, die Recherche war zu vorsichtig.
  - Baribo (80 %) nicht im Kader.

  **Muster:** MLS unter der Woche starten Spieler mit ≥ 80 % nur zu 83 % (n=35),
  am Wochenende zu 94 % (n=36); im Mittel kalibriert (62 % vs. 60 %).
  **Nicht geändert:** Für einen MLS-Wochentagsabschlag ist n zu klein, und bis zum
  Saisonende (Decision Day 07.11.) gibt es keine MLS-Wochentagsrunde mehr.
  **Prozess-Lehre:** Beim Deadline-Check gegen Saisonende Teams mit fixem
  Tabellenplatz (Titel/Shield sicher oder ausgeschieden) auf Rotation prüfen, die
  Gelbsperren-Liste der Liga abfragen, und bei Verletzung ohne Diagnose nicht
  unter ~50 % gehen, solange kein zweiter Beleg für einen Ausfall vorliegt.
- **Bilanz 30.10.2026 (1660 Spiele, 1 neu = Elmas, Do 29.10.) und Datenfix in
  `evaluate.py`:** Elmas' Länderspiel vom 29.09. (90 Minuten) wurde plötzlich als
  „nicht im Kader“ gewertet. Ursache: `evaluate.py` holte je Spieler nur die
  letzten 8 Spiele und bewertete jeden Tag alle Vorhersagen neu. Fällt ein Spiel
  aus diesem Fenster, sieht es aus wie „nicht beteiligt“. Betroffen waren bisher
  5 Einträge, 2 davon falsch (Elmas 29.09., Aitor Fraga 04.10., der laut Log
  startete). Das Problem wäre mit jeder Woche größer geworden. **Fix:**
  - Reicht das Fenster nicht bis zum Anstoß zurück, gilt das Ergebnis als
    „unbekannt“, und der Spieler wird mit 40 Spielen neu abgefragt (`LAST_DEEP`).
  - Einmal ermittelte Ergebnisse stehen in **`logs/outcomes.json`** (wird
    committet, inkl. Position) und werden nie neu bewertet.
  - Was trotzdem unklar bleibt, zählt nicht mit (Bericht: „nicht ermittelbar“).

  Ergebnis: Brier 0,1700 → 0,1701, `intl_duty_auto` jetzt 2 von 2 gestartet
  (vorher 1 von 2), Länderspiel-LOO wieder 0,1939 → 0,1916 (mit dem Fehler
  0,1988 → 0,1955). Ein zweiter Lauf nur aus dem Cache liefert dieselben Zahlen.
  Reiner Datenfix, keine Modelländerung.
- **Bilanz 31.10.2026 (1695 Spiele, davon 35 neu = Freitag GW726, nur Modell):**
  Brier 0,173, vorhergesagt 50 %, gestartet 57 %. Fehlgriffe: Issa Doumbia (92 %,
  Sporting) nur Joker (28'), Camara (14 %) gestartet. Mittelbereich (40–52 %)
  fast durchweg gestartet (Gabriel, Boudaoui, Luis Guilherme, Krattenmacher,
  Fortuño). Die Klub-Kalibrierung bleibt aktiv (LOO 0,1677 → 0,1644) und deckt
  das mit ab. n=35 → keine Änderung.
- **Bilanz 01.11.2026 (1860 Spiele, davon 165 neu = Samstag GW726 + MLS, nur
  Modell):** Brier 0,139 (bester Tag seit dem SofaScore-Ausfall), Quoten ≥ 80 % →
  92 % gestartet (n=51). Mittelbereich 35–65 % weiter zu niedrig: vorhergesagt
  52 %, gestartet 67 % (n=42). Fehlgriffe: Lacroix, Jean-Jacques, Wilson,
  Kalajdžić (63–88 %) nicht im Kader; Kim Min-jae (18 %), Elvedi (26 %), Karaman
  (24 %) 90' gestartet. **Geprüft, nicht geändert:** Ein Platt-Fit nur auf den
  letzten 7 Tagen (Test ab 24.10. bzw. 28.10.) schlägt die geloggten,
  kalibrierten Quoten nicht (0,1587 gegen 0,1569 ab 28.10.). Die aktive
  Kalibrierung mit Status-Offsets ist also schon die beste Variante; eine
  eigene Korrektur nur für den Mittelbereich wäre Kurvenanpassung.
- **Bilanz 02.11.2026 (2008 Spiele, davon 148 neu = Sonntag GW726 + MLS, nur
  Modell):** Brier 0,121, vorhergesagt 61 %, gestartet 61 %; Quoten ≥ 80 % → 92 %
  (n=60). Fehlgriffe: Burgess (96 %, Trainingsverletzung am 31.10.) und
  Franculino (90 %, Oberschenkel, Meldungen ab 29.10.) nicht im Kader. Bei
  Franculino war die Meldung vor dem GW726-Lock da, ich hatte sie beim finalen
  Check nicht gesucht. Kim Jin-su (94 %) nicht im Kader, Trapp (4 %) und Malić
  (9 %, Rot-Verdacht) 90' gestartet. `suspension_risk` gesamt 6 von 8 richtig
  (vorhergesagt 8 %, real 25 %). Bei n=8 bleibt der Faktor ×0,10.
  **Prozess-Lehre:** Beim finalen Check für jeden aufgestellten Spieler mit
  hoher Quote auch eine Verletzungssuche der letzten 3 Tage machen, nicht nur
  für die bekannten Wackelkandidaten.
- **Bilanz 03.11.2026 (2036 Spiele, davon 28 neu = Montag GW726, nur Modell):**
  Brier 0,178, vorhergesagt 46 %, gestartet 43 %. Zwei Muster wiederholen sich
  (beide schon am 26./27.10. gesehen):
  - Newcastle-Abwehr: Schär (27 %) und Burn (36 %) erneut 90 Minuten von Beginn
    an, Thiaw (66 %) wieder auf der Bank.
  - Benfica-Tor: Samuel Soares (31 %) erneut 90 Minuten, Trubin (32 %) auf der
    Bank.

  Das Modell zieht solche Stammplatzwechsel nur langsam nach, weil die
  Recency-Gewichtung die älteren Einsätze noch mitzählt. n=28 → keine Änderung.
  Beim Deadline-Check aber bei Newcastle und beim Benfica-Torwart der letzten
  2–3 Partien folgen, nicht der Modellquote.
- **Bilanz 04.11.2026 (2071 Spiele, davon 35 neu = Dienstag GW727, Europacup):**
  Brier 0,182, vorhergesagt 58 %, gestartet 57 %. Die zwei recherchierten Quoten
  lagen richtig: Urbig 14 % (Neuer stand im Tor) und Olise 63 % (90 Minuten). Neuer
  selbst hatte nur die Modellquote (27 %, NOT_PLAYING) und startete. Die übrigen
  Fehlgriffe kamen vor allem von Sporting:
  - Rui Borges war am 02.11. entlassen worden, Interimstrainer Tiago Fernandes
    stellte gegen Shakhtar fast die ganze Elf um (O Jogo, 03.11.).
  - Torwart Rui Silva (15 %, NOT_PLAYING) spielte 90 Minuten, Fresneda (89 %)
    kam nur als Joker (7'), Luis Guilherme (60 %) gar nicht.

  Kim Min-jae (61 %) saß zugunsten von Tah (45 %) auf der Bank. n=35 → keine
  Änderung. **Prozess-Lehre:** Nach einem Trainerwechsel (auch Interimstrainer)
  gelten die Klubquoten fürs erste Spiel als unsicher. Beim Deadline-Check die
  datierte voraussichtliche Elf des neuen Trainers suchen, vor allem für Torwart
  und Außenverteidiger.
- **Bilanz 05.11.2026 (2110 Spiele, davon 39 neu = Mittwoch GW727, Europacup):**
  Brier 0,156, vorhergesagt 66 %, gestartet 69 %. Fehlgriffe sind erneut
  Europacup-Rotation bei Stammspielern: Wirtz (92 %, geschont, 24' als Joker),
  Freuler (86 %), Havertz (80 %) und Bruno Guimarães (78 %) ohne Einsatz. Umgekehrt
  starteten Szoboszlai (22 %, nach Oberschenkelverletzung zurück), Rüdiger (29 %)
  und Peprah Oppong (40 %). Kein Modelleingriff: Rotation vor dem Wochenende ist
  ohne voraussichtliche Elf nicht vorherzusagen, und n=39 ist zu klein. Für die
  **Wochenendquote** gilt die Lehre vom 15.10.: Wer im Europacup nur geschont
  wurde, bekommt fürs Wochenende einen Override statt der abgesenkten Modellquote
  (GW728: Wirtz 85 %, Quellen 04.11.).
- **Bilanz 06.11.2026 (2188 Spiele, davon 78 neu = Donnerstag GW727, Europa/
  Conference League):** Brier 0,183, vorhergesagt 52 %, gestartet 54 %. Benfica
  rotierte gegen Lech fast komplett: Pavlidis (82 %), Bah (85 %), Dahl (69 %) und
  Aursnes (86 %) nicht in der Startelf, dafür Trubin (26 %), Sudakov (32 %) und
  Manuel Silva (14 %). Dazu Hložek (81 %), Hödl (86 %) und Wilson (76 %) ohne
  Startelfeinsatz. **Geprüft, nicht übernommen:** Abschlag für reine Modellquoten
  in Klubspielen Di–Do (n=276). Quoten ≥ 80 % starten dort nur zu 82 % (vorhergesagt
  90 %, n=95), am Wochenende zu 93 % (vorhergesagt 89 %, n=277). Ein Shrink
  `0,9·p + 0,1·0,55` verbessert den Brier in beiden Zeithälften (0,1920 → 0,1917
  und 0,1751 → 0,1731, gesamt 0,1836 → 0,1824), in der frühen Hälfte aber kaum.
  Bewusst nicht umgesetzt: Gewinn klein, Deadline am selben Tag, und die nächste
  Midweek-GW liegt in der Länderspielpause. Nach der Pause mit mehr Europacup-Daten
  erneut prüfen. Fürs Wochenende gelten Overrides für die geschonten Spieler
  (Pavlidis, Bah 80 %, Quellen 05.11.).
- **Bilanz 07.11.2026 (2202 Spiele, davon 14 neu = Freitag GW728):** Brier 0,049,
  vorhergesagt 70 %, gestartet 71 %, kein Fehlgriff. n=14 → keine Änderung.
- **Bilanz 08.11.2026 (2386 Spiele, davon 183 neu = Samstag GW728 + MLS Decision
  Day, nur Modell):** Brier 0,150, vorhergesagt 59 %, gestartet 58 %. Auffällig
  viele Stammspieler nur als Joker oder gar nicht, darunter Nicks Karten:
  - Nusa (96 %, 25'), Ndoye (95 %, PL-HS-Kapitän, 25'), Ebnoutalib (86 %, 26',
    Burkardt startete; die Vorschauen waren geteilt), Demirović (86 %, 7'),
    Eze (72 %, 21'), R. Taylor (89 %, 28').
  - Nashville rotierte trotz Punkterekord teilweise: Palacios (93 %) 0', dagegen
    starteten Mukhtar (recherchiert 69 %) und Corcoran (recherchiert 42 %).
  - Ohne Einsatz: Tate Johnson (96 %), Hagglund (81 %), Lloris (95 %), A. Long
    (67 %), Guirassy (87 %), Vermeeren (93 %).

  **Muster, nicht umgesetzt:** Am letzten Klub-Spieltag vor der Länderspielpause
  starteten Quoten ≥ 80 % nur zu 84 % (n=67, vorhergesagt 90 %), an den drei
  Wochenenden davor zu 92–95 %. Vor der Oktober-Pause gibt es nur n=2, also kein
  zweiter Beleg. Vor der nächsten Pause (März) erneut prüfen; bis dahin beim
  Deadline-Check vor einer Pause Nationalspieler mit hoher Quote auf
  Schonung prüfen.
- **Bilanz 09.11.2026 (2550 Spiele, davon 159 neu = Sonntag GW728) und Datenfix
  in `evaluate.py`:** Brier 0,137, vorhergesagt 57 %, gestartet 59 %. Alle acht
  recherchierten Quoten lagen richtig: Wirtz 89 % (90'), Pavlidis und Bah je 78 %
  (90'/84'), Samuel Soares 66 % (90', Trubin 18 % auf der Bank), Burgess,
  Franculino und Khudyakov 0–17 % (nicht im Kader). `researched` gesamt jetzt
  Brier 0,135 (n=89), bestes eigenes Signal. Fehlgriffe: Kristensen (95 %, 45'),
  Becker (90 %, 0'), Bischoff (93 %, 21'), Perišić (89 %, 0'), Aursnes (75 %, 0').
  **Datenfehler behoben:** Estoril–Marítimo (08.11.) wurde verlegt, `evaluate.py`
  wertete alle Marítimo-Spieler als „nicht im Kader“ (Butzke, Romain Correia,
  Paulo Henrique, Rodrigo Andrade, Vieites, je 63–88 %). `OUTCOME_QUERY` liest
  jetzt `statusTyped`; ein Spiel mit Status ≠ `played` gilt als „ausgefallen/
  verlegt“ (`void`, wird nicht gewertet, Bericht zählt es separat), `playing` als
  „pending“. Nachprüfung aller 347 gecachten „nicht im Kader“-Einträge: 16 waren
  in Wahrheit verlegte bzw. abgebrochene Spiele, darunter **Laporte 10.10.**
  (Spiel `suspended`, in der Bilanz 11.10. als Kaderausfall gezählt) und
  **Wilson 31.10.** (verlegt, Bilanz 01.11.). Ergebnis: Brier gesamt 0,1626 →
  0,1617, Klub-LOO 0,1632 → 0,1580 vorher, jetzt 0,1620 → 0,1569. Ein zweiter
  Lauf liefert dieselben Zahlen. Reiner Datenfix, keine Modelländerung.
- **Bilanz 13.11.2026 (2567 Spiele, davon 17 neu = GW729 Länderspiele vom
  12.11., alle mit recherchierter Quote):** Brier 0,187, vorhergesagt 42 %,
  gestartet 53 %. Die klaren Fälle lagen richtig: Kane, Olise, Pickford, Krejčí
  gestartet; Perišić, Jakić, Restes, Eze, Grimaldo, Theate nicht. Daneben lag der
  Mittelbereich (25–50 %): 5 von 9 gestartet, darunter Baena (42 %, 95 Punkte),
  Porro (30 %), Hložek (34 %) und zwei Torhüter, bei denen die Vorschauen einen
  anderen erwarteten (Unai Simón 42 % statt Raya, Kovář 30 % statt Horníček).
  Laporte (65 %) stand nicht im Kader. Über alle recherchierten Quoten (n=106)
  liegt der Bereich 0,15–0,6 im Schnitt rund 13 Punkte zu niedrig (0,15–0,35:
  24 % → 35 %, 0,35–0,6: 43 % → 59 %, je n=17). Die Ränder stimmen (< 0,15 und
  ≥ 0,8). **Nicht geändert:** n=34 im betroffenen Bereich, Deadline am selben
  Tag. **Prozess-Lehre:** Ohne klaren Beleg für die Bank (Trainer-Aussage,
  Spiel-Log) bei Recherche-Quoten nicht unter ~0,45 gehen. Das gilt auch für
  Torhüter, bei denen sich die Vorschauen nur auf einen Wechsel einigen. Krejčí
  sah in der 72. Minute Rot (Spiel-Log) und ist für Kroatien gegen Tschechien
  (GW730) sehr wahrscheinlich gesperrt.
- **Bilanz 14.11.2026 (2593 Spiele, davon 23 neu = GW730 Freitag, Länderspiele
  13.11.):** Brier 0,159, vorhergesagt 57 %, gestartet 52 %. Die 13 recherchierten
  Quoten lagen 11-mal richtig. Gestartet wie erwartet: Kimmich (86 Punkte), Wirtz,
  Tah, Elvedi, Pavlidis, Ndoye, ter Stegen, Elmas. Nicht gestartet wie erwartet:
  Geertruida, Nübel, Füllkrug (Joker 16'). Daneben: Schlotterbeck (79 %, in beiden
  Vorschauen, 0'; Thiaw startete) und Embolo (32 %, 59'). Embolo stand in keiner
  Vorschau, war aber auch nicht als Bank genannt. Das bestätigt die Lehre vom
  13.11.: Ohne ausdrücklichen Bank-Beleg nicht unter ~0,45 gehen. Keine
  Modelländerung (n klein).
- **Laufende Spiele zählen nicht (Fix 15.10.2026):** Sorare führt ein laufendes Spiel
  schon mit den bisherigen Minuten im Spiel-Log. Der Sync um 02:45 lief während der
  MLS-Mittwochsspiele: Jeder MLS-Spieler verlor dadurch ~15 Prozentpunkte Startquote
  fürs Wochenende (Karic 0,91 → 0,70, obwohl er auf dem Platz stand), der Entwurf
  wurde quer umgebaut. `fetch_players` verwirft jetzt Spiele mit `statusTyped` ≠
  `played`. Reiner Datenfehler, kein Modelleingriff (historische Spiele sind alle
  beendet, Backtest unverändert).
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
   **Spieler, deren nächstes Spiel noch in der laufenden GW liegt** (z. B.
   Länderspiel am Mi, dann wieder am Sa), sucht der Optimierer seit 29.09.2026
   über `so5Fixture.anyGames` ihr erstes Spiel im geplanten Fenster (Nation, wenn
   er gerade bei der Nation ist, sonst Klub) — vorher fielen sie aus dem Entwurf.
   **Fix 03.10.2026:** Ist der Spieler nicht bei seiner Nation, zählt nur sein
   Klubspiel. Vorher fiel der Optimierer auf das Länderspiel seines Landes zurück
   und plante Klubspieler ohne Nominierung ein (Ortuño/Albacete und Aitor Fraga
   standen für Spanien – Kroatien im GW719-Entwurf).
3. Entwurf als Tabellen zeigen (mit Kapitän), offene Startelf-/Verfügbarkeitsfragen
   markieren; **final** beim nächsten Deadline-Check (~1,5 h vorher) datiert prüfen
   (GRUNDREGEL #0). Baseline erst nach Nicks Sorare-Bestätigung nachziehen.

### D) Jede Treffer-Bilanz hinterfragen → Learnings umsetzen (Nicks Auftrag, 02.10.2026)

Nach **jedem** `evaluate.py`-Lauf (tägliche Routine oder manuell) nicht nur die
Zahlen melden, sondern das Modell **aktiv verbessern**:

1. **Fehlgriffe einzeln untersuchen**, nicht nur zählen. Pro Miss die letzte
   Vorhersage im Log ansehen: Quelle, Modell-%, `playingStatus`, Override-Datum,
   Kader (`onGameSheet`). Frage: war das **vermeidbar**, und wenn ja, durch
   welches Signal?
2. **Muster suchen**, aufgeschlüsselt je Quelle × Spieltyp, je `playingStatus`,
   je Quotenbereich und je Position × Spieltyp bei der Projektion. Fragen: Ist
   eine Quelle systematisch zu hoch oder zu niedrig? Bringt ein Signal
   überhaupt Information gegenüber dem Modell allein?
3. **Prozess-Fehler prüfen:** Ist jede Information, die ich vor Anpfiff hatte
   (z. B. Nicks App-%), auch im Log gelandet? Wenn nein, den Prozess reparieren.
4. **Jede Änderung vorher backtesten** (Leave-one-out bzw. `backtest.py`) und nur
   übernehmen, wenn sie **out-of-sample** besser ist. Bei wenigen Spielen
   konservativ bleiben: lieber eine Konstante abschwächen als ein neues
   Feature mit 6 Datenpunkten.
5. **Umsetzen:** Code ändern, CLAUDE.md dokumentieren (mit Datum und Anlass),
   committen und pushen, Nick kurz berichten:
   - was ich gelernt habe;
   - was ich geändert habe;
   - Backtest vorher → nachher;
   - was ich bewusst **nicht** geändert habe und warum.
6. **Timing:** Keine Modelländerung in den letzten ~3 h vor einer
   Classic-Deadline (Di/Fr 16:00). Dann nur notieren und nach dem Lock umsetzen.
   Ausnahme: Nick gibt ausdrücklich grünes Licht.

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
  Ebenso `logs/evaluation.json`, `logs/outcomes.json` + `calibration.json` nach
  jedem `evaluate.py`-Lauf.
- Neue Recherche-/Scouting-Tools als eigenständige Stdlib-Skripte im gleichen
  Stil ergänzen (Docstring mit Usage, `graphql`/`load_env` aus `sorare_client`).
