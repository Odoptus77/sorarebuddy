# OAuth-Setup: als dein Sorare-Konto einloggen

Der API-Key allein liefert nur **öffentliche** Daten. Für deine eigenen Karten
(Verein) meldet sich das Tool per **OAuth** als du an — dein Passwort kommt dabei
nie in den Code.

## Was OAuth abdeckt (und was nicht)

- ✅ Basis-Konto-Infos, **deine Karten**, Achievements, Notifications
- ✅ laut Sorare-Doku auch Favoriten, eigene Auktionen/Angebote
- ❌ Keine zukünftigen Lineups/Rewards, kein Kaufen/Verkaufen/Bieten, kein
  Rewards-Claim, keine E-Mail-Adresse

> **Hinweis Kaufpreis:** Da Transaktionsdaten außen vor sind, ist der tatsächlich
> gezahlte Kaufpreis pro Karte über OAuth evtl. nicht verfügbar. Das prüfen wir
> live am Schema, sobald ein Token vorliegt. Der *aktuelle Schätzwert* wird aus
> den letzten Verkäufen vergleichbarer Karten berechnet.

## Schritt 1 – OAuth-App anlegen (self-service)

1. Auf **sorare.com/settings/developer** eine OAuth-Anwendung anlegen.
2. Callback-/Redirect-URL: `http://localhost:3000/auth/sorare/callback`
   (muss später exakt übereinstimmen; sonst `SORARE_REDIRECT_URI` setzen).
3. Du erhältst **Client ID** und **Client Secret** — nie in den Chat kopieren.

## Schritt 2 – Zugangsdaten hinterlegen

**Claude Code Web (empfohlen):** Cloud-Umgebung → Menü in der Titelleiste →
*Edit* → **Umgebungsvariablen**:

```
SORARE_CLIENT_ID=deine_client_id
SORARE_CLIENT_SECRET=dein_client_secret
```

Eine **neue Session** (bzw. ein neuer Container) übernimmt die Werte.
Lokal alternativ in `.env.local` (gitignored).

## Schritt 3 – Autorisieren (einmalig, im Browser)

`python3 sorare_client.py authurl` gibt den Login-Link aus (enthält nur die
Client ID). Öffnen, Zugriff bestätigen → Weiterleitung auf
`http://localhost:3000/auth/sorare/callback?code=…`. Die Seite lädt nicht — nur
der `code`-Wert aus der Adresszeile zählt. Der Code ist einmalig, läuft nach
Minuten ab und ist ohne Client Secret wertlos.

## Schritt 4 – Code gegen Token tauschen

```bash
python3 sorare_client.py token <code>
```

Access- und Refresh-Token werden direkt in `.env.local` (Modus 600) geschrieben
und **nie angezeigt**. Ausgegeben werden nur Ablaufdatum und Scope.

## Schritt 5 – Testen

`python3 sorare_client.py me` → dein Nickname statt `null`.

## Token dauerhaft machen / erneuern

- **Live geprüft 29.09.2026:** Access-Token gilt nur **~1 Tag**, Scope `public`;
  jeder `refresh` liefert einen **neuen** Refresh-Token (der alte wird ersetzt).
  Deshalb Tokens **nicht** als Umgebungsvariablen hinterlegen (echte Env-Werte
  schlagen `.env.local` und wären nach dem ersten Refresh veraltet). Nach einem
  Container-Neustart einfach neu einloggen (`authurl` → Code → `token`, ~1 Min).
- Mit Login abrufbar (live geprüft): `so5Fixture.mySo5Lineups` (deine gesetzten
  Aufstellungen inkl. Kapitän, nach dem Lock), `mySo5Rankings` (Score/Platz),
  `currentUser.unclaimedSo5Rewards`. `nextClassicFixturePlayingStatusOdds` bleibt
  auch mit Login `null` (sorare/api #693).
- Abgelaufen: `python3 sorare_client.py refresh` (nutzt `SORARE_REFRESH_TOKEN`).
- Ein abgelaufener/ungültiger Token legt nichts lahm: Sorare antwortet mit
  „Unauthorized“, der Client wiederholt die Anfrage dann ohne Token (öffentliche
  Daten) und warnt einmal auf stderr.

## Sicherheit

- `.env.local` niemals committen (steht in `.gitignore`).
- Client Secret und Tokens sind wie Passwörter zu behandeln.
- Läuft am sichersten auf deinem eigenen Rechner. In einer Cloud-Sitzung
  brauchst du die Werte nur, wenn du dort abfragen willst; Schritt 3 (Browser)
  machst du ohnehin lokal.

Quelle: <https://github.com/sorare/api>
