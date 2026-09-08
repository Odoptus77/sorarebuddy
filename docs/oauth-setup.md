# OAuth-Setup: als dein Sorare-Konto einloggen

Der API-Key allein liefert nur **öffentliche** Daten. Für deine eigenen Karten
(Verein) meldet sich das Tool per **OAuth** als du an — dein Passwort kommt dabei
nie in den Code.

## Was OAuth abdeckt (und was nicht)

- ✅ Basis-Konto-Infos, **deine Karten**, Achievements, Notifications
- ❌ Keine Transaktions-/Handelsdaten, keine zukünftigen Lineups, keine
  E-Mail-Adresse

> **Hinweis Kaufpreis:** Da Transaktionsdaten außen vor sind, ist der tatsächlich
> gezahlte Kaufpreis pro Karte über OAuth evtl. nicht verfügbar. Das prüfen wir
> live am Schema, sobald ein Token vorliegt. Der *aktuelle Schätzwert* wird aus
> den letzten Verkäufen vergleichbarer Karten berechnet.

## Schritt 1 – OAuth-App anlegen

1. Auf **sorare.com/settings/developer** eine OAuth-Anwendung anfragen
   (verifizierte Identität nötig).
2. Als Callback-URL eintragen: `http://localhost:3000/auth/sorare/callback`
   (oder eine eigene; muss später exakt übereinstimmen).
3. Du erhältst **Client ID** und **Client Secret**.

## Schritt 2 – Zugangsdaten hinterlegen

In `.env.local` (gitignored):

```
SORARE_CLIENT_ID=deine_client_id
SORARE_CLIENT_SECRET=dein_client_secret
SORARE_REDIRECT_URI=http://localhost:3000/auth/sorare/callback
```

## Schritt 3 – Autorisieren (einmalig, im Browser)

```bash
python3 sorare_client.py authurl
```

Öffne die ausgegebene URL im Browser, bestätige den Zugriff. Du wirst auf die
Callback-URL umgeleitet:

```
http://localhost:3000/auth/sorare/callback?code=DEIN_CODE
```

Kopiere den Wert von `code` (die Seite selbst muss nicht laden — es geht nur um
den Code in der Adresszeile).

## Schritt 4 – Code gegen Token tauschen

```bash
python3 sorare_client.py token DEIN_CODE
```

Das gibt `access_token` und `refresh_token` aus. Trage das Access-Token in
`.env.local` ein:

```
SORARE_ACCESS_TOKEN=das_access_token
```

## Schritt 5 – Testen

```bash
python3 sorare_client.py me
```

Erwartet: dein Nickname statt `null`. Danach lassen sich deine Karten abrufen.

## Token erneuern

Access-Tokens laufen ab. Mit dem `refresh_token` ein neues holen (POST an
`https://api.sorare.com/oauth/token` mit `grant_type=refresh_token`).

## Sicherheit

- `.env.local` niemals committen (steht in `.gitignore`).
- Client Secret und Tokens sind wie Passwörter zu behandeln.
- Läuft am sichersten auf deinem eigenen Rechner. In einer Cloud-Sitzung
  brauchst du die Werte nur, wenn du dort abfragen willst; Schritt 3 (Browser)
  machst du ohnehin lokal.

Quelle: <https://github.com/sorare/api>
