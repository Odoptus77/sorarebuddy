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

## Sicherheit

- Wurde der Key jemals geteilt (z. B. im Chat), **rotiere** ihn in den
  Sorare-Einstellungen und trage den neuen Wert erneut ein.
- Bei Weg B ist `.env.local` nicht nötig und kann leer bleiben/entfernt werden.

Quellen: <https://code.claude.com/docs/en/cloud-environments>,
<https://code.claude.com/docs/en/claude-code-on-the-web>
