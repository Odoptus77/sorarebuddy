# sorarebuddy iOS App (SwiftUI)

A native SwiftUI client for the sorarebuddy dashboard. It renders the same data
as the web dashboard — club valuation, rewards, and the lineup suggestions with
the **Startelf-Prediction-Score** — by fetching JSON from `backend/server.py`.
No Sorare key lives in the app.

## What's here

```
ios/SorareBuddy/
  SorareBuddyApp.swift   @main entry, wires Store + AppConfig
  AppConfig.swift        backend URL / slug / token (persisted, editable in-app)
  Models.swift           Codable structs matching the backend JSON
  APIClient.swift        async URLSession client + Store (ObservableObject)
  Theme.swift            colours + de-DE number/currency/date formatting
  Components.swift       StartChip, MinutesTrail, Tag, KPICard
  ClubView.swift         "Verein" tab: KPIs + searchable/sortable card list
  SuggestionsView.swift  "Vorschläge" tab: competitions, teams, Startelf score
  RootView.swift         TabView, loading/error states, Settings sheet
```

## Build it (needs a Mac + Xcode 15+)

Claude can't compile Swift in its cloud (Linux, no Xcode), so build locally:

1. **Xcode → File → New → Project → iOS → App.**
   - Product Name: `SorareBuddy`
   - Interface: **SwiftUI**, Language: **Swift**
   - Minimum deployment: **iOS 16.0** or later
2. Delete the auto-generated `ContentView.swift` and the `…App.swift` stub.
3. **Drag the files from `ios/SorareBuddy/` into the project** (check "Copy items
   if needed" and add to the app target). `SorareBuddyApp.swift` is the `@main`.
4. Build & run on the Simulator or your iPhone.

## Connect it

Open the app → gear icon (**Einstellungen**):

- **Backend-URL:** where `server.py` runs.
  - Simulator: `http://localhost:8080`
  - iPhone on the same Wi-Fi: `http://<your-mac-LAN-ip>:8080`
  - Deployed: your `https://…` URL
- **App-Token:** the `APP_TOKEN` you set on the backend (leave empty if none).
- **Slug:** your Sorare manager slug (e.g. `nicktd7`).
- **Seltenheiten:** `limited,rare` (or add `super_rare,unique`).

Tap **Speichern & neu laden**. Pull-to-refresh reloads any screen.

> The **first** load can take 1–2 minutes if the backend cache is cold — the app
> shows a spinner and waits (600 s timeout). Prewarm the backend (see
> `backend/README.md`) so loads are instant.

## Notes / next steps

- App Transport Security blocks plain `http://` to non-local hosts — use HTTPS
  for a deployed backend (or a `localhost`/LAN address during development).
- This is a scaffold covering both main screens and the full Startelf score. A
  reward-lineup detail sheet (tap a card to see the winning lineups) and native
  charts are easy follow-ons; the data (`Rewards.rewardLineups`) is already
  fetched and modelled.
