# Netzwerk-Setup: Sorare-API in Claude Code on the web freigeben

Sitzungen auf claude.ai/code laufen mit dem Netzwerk-Level **Trusted**, das nur
eine feste Allowlist (Paket-Registries, GitHub, …) erlaubt. `api.sorare.com`
steht nicht darauf, daher schlagen Live-Abfragen mit einem Proxy-`403` fehl.

Diese Anleitung beschreibt **Weg B (empfohlen, Pro/Max)**: den Sorare-Key als
**API-Credential** in der Cloud-Umgebung hinterlegen. Der Anthropic-Proxy hängt
den Key dann automatisch an Anfragen an `api.sorare.com` an — nachdem die
Anfrage die Sitzung verlassen hat. Vorteile:

- Der Host wird erreichbar, **ohne** das Netzwerk-Level zu ändern.
- Der Key liegt **nicht** im Repo und ist für die Sitzung (und Claude) unsichtbar.

## Voraussetzungen

- Pro- oder Max-Plan (auf Team/Enterprise gibt es API-Credentials noch nicht —
  dort stattdessen **Weg A** unten nutzen).
- Admin-Rolle in der eigenen Organisation (auf Pro/Max automatisch gegeben).

## Schritte (Weg B)

1. Auf **claude.ai/code** oben über dem Eingabefeld auf das **Wolken-Icon**
   klicken (zeigt den Umgebungsnamen, z. B. „Default").
2. Über die Umgebung fahren → **Zahnrad-Icon** (Bearbeiten).
3. Abschnitt **API credentials** → **Add credential**.
4. Felder ausfüllen:
   - **Credential type:** `Bearer` (oder generisch)
   - **Allowed websites:** `api.sorare.com`
   - **Custom headers:** Header-**Name** auf `APIKEY` ändern, **Prefix leeren**,
     als **Value** den Sorare-Key einfügen.
5. **Connect** klicken. Der Wert lässt sich danach nicht mehr anzeigen.
6. **Neue** Sitzung starten (laufende Sitzungen übernehmen die Änderung nicht).

## Testen

In der neuen Sitzung:

```bash
python3 sorare_client.py ping
```

Der Client sendet **keinen** Key mehr selbst; der Proxy hängt den `APIKEY`-Header
an. Erwartete Antwort: der `currentUser`-Block mit deinem Nickname.

## Weg A – Alternative (alle Pläne)

Wenn API-Credentials nicht verfügbar sind:

1. Umgebung bearbeiten → **Network access** auf **Custom** stellen.
2. Im Feld **Allowed domains** eine Zeile hinzufügen: `api.sorare.com`
3. Häkchen bei **„Also include default list of common package managers"** setzen.
4. Speichern → neue Sitzung starten.

Bei Weg A muss der Key lokal vorliegen (`.env.local`, siehe `.env.example`),
weil der Proxy dann nichts injiziert.

## SofaScore – voraussichtliche Aufstellungen freigeben

Für die **predicted-lineup**-Anreicherung des Startelf-Scores muss zusätzlich
`api.sofascore.com` erreichbar sein. SofaScore braucht **keinen** API-Key.

**Variante 1 (empfohlen — ändert das Netzwerk-Level nicht):** eine zweite
API-Credential nur zum Freischalten der Domain anlegen (analog zur Sorare-Einrichtung):

1. Umgebung bearbeiten → **API credentials** → **Add credential**.
2. **Allowed websites:** `api.sofascore.com`.
3. Falls das Formular einen Header verlangt: einen harmlosen setzen, z. B.
   Name `X-Client`, Value `sorarebuddy` (SofaScore ignoriert ihn). Ein echter
   Key ist **nicht** nötig.
4. **Connect** → **neue** Sitzung starten. Die Sorare-Credential bleibt bestehen.

**Variante 2 (Custom-Netzwerk):**

1. Umgebung bearbeiten → **Network access** auf **Custom** stellen.
2. Unter **Allowed domains** eine Zeile hinzufügen: `api.sofascore.com`.
3. Häkchen bei **„Also include default list of common package managers"** gesetzt lassen.
4. Speichern → **neue** Sitzung starten. Die Sorare-Credential injiziert den
   `APIKEY` weiterhin, `api.sorare.com` bleibt also erreichbar.

Testen (neue Sitzung):

```bash
python3 sofascore_lineups.py --ping                 # -> OK
python3 sofascore_lineups.py "Real Madrid"          # zeigt die nächste (voraussichtl.) Elf
```

Danach zieht `lineup_suggest.py` die Aufstellungen automatisch (ohne Flag) ein;
mit `--no-sofascore` lässt sich das abschalten. Hinweise:

- Die **voraussichtliche** Elf erscheint bei SofaScore meist erst **1–2 Tage**
  vor Anpfiff, die **bestätigte** ~1 h vorher. Vorher liefert die Quelle nichts
  und der Score nutzt weiter die Sorare-Signale.
- Die API ist **inoffiziell** und nur für Privatnutzung gedacht; sie kann sich
  ändern oder die Server-IP zeitweise per Cloudflare (403) blocken. Der Code
  fällt in dem Fall geräuschlos auf das Sorare-Modell zurück.

## API-Football – Verletzungen & Sperren (inkl. Gelbsperren)

`injuries_feed.py` holt pro Spieltag des GW-Fensters die Verletzungs- und
Sperrmeldungen von **API-Football** (`v3.football.api-sports.io`); der
Optimierer nutzt sie automatisch, sobald der Host erreichbar ist.

1. Kostenloses Konto direkt bei **api-sports** anlegen (dashboard.api-football.com,
   **nicht** über RapidAPI — dort gelten anderer Host und Header). Im Dashboard
   den **API-Key** kopieren. Free-Plan: ca. 100 Anfragen/Tag.
2. Umgebung bearbeiten → **API credentials** → **Add credential**:
   - **Allowed websites:** `v3.football.api-sports.io`
   - **Custom headers:** Name `x-apisports-key`, **Prefix leeren**, Value = Key
   - **Connect**
   (Ohne API-Credentials: **Network access** → Custom → `v3.football.api-sports.io`
   erlauben und den Key als Umgebungsvariable `APIFOOTBALL_KEY` setzen.)
3. **Neue** Sitzung starten.

Testen (neue Sitzung):

```bash
python3 injuries_feed.py status            # Plan + Anfragen heute
python3 injuries_feed.py date 2026-10-03   # Meldungen eines Tages
```

Meldet `status`/`date` einen Fehler wie „Free plans do not have access to this
season", ist der Free-Plan auf alte Saisons beschränkt → dann entscheiden, ob
der Pro-Plan (ca. 19 $/Monat) sich lohnt. Ohne Freigabe fällt der Optimierer
geräuschlos auf die Sorare-Signale zurück (`--no-injuries-feed` schaltet ab).

## Sicherheit

- Wurde der Key jemals geteilt (z. B. im Chat), **rotiere** ihn in den
  Sorare-Einstellungen und trage den neuen Wert erneut ein.
- Bei Weg B ist `.env.local` nicht nötig und kann leer bleiben/entfernt werden.

Quellen: <https://code.claude.com/docs/en/cloud-environments>,
<https://code.claude.com/docs/en/claude-code-on-the-web>
