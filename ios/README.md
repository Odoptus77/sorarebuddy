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

Claude can't compile Swift in its **cloud** (Linux, no Xcode). Two ways to build,
both on a Mac.

### Option A — one command with XcodeGen (recommended)

`ios/project.yml` describes the whole app, so you don't drag files by hand:

```bash
brew install xcodegen        # once
cd ios
xcodegen generate            # creates SorareBuddy.xcodeproj from project.yml
open SorareBuddy.xcodeproj   # then Run (⌘R) in Xcode
```

Or build/run from the command line without opening Xcode:

```bash
cd ios && xcodegen generate
xcodebuild -project SorareBuddy.xcodeproj -scheme SorareBuddy \
  -destination 'platform=iOS Simulator,name=iPhone 15' build
# launch in the simulator:
xcrun simctl boot "iPhone 15" 2>/dev/null; open -a Simulator
xcodebuild -project SorareBuddy.xcodeproj -scheme SorareBuddy \
  -destination 'platform=iOS Simulator,name=iPhone 15' -derivedDataPath build
xcrun simctl install booted "$(find build -name 'SorareBuddy.app' -maxdepth 4 | head -1)"
xcrun simctl launch booted com.sorarebuddy.app
```

To run on a real iPhone, set your Team ID in `project.yml`
(`DEVELOPMENT_TEAM`) and re-run `xcodegen generate`.

### Option B — manual Xcode project

1. **Xcode → File → New → Project → iOS → App** (Product Name `SorareBuddy`,
   Interface **SwiftUI**, deployment **iOS 16.0+**).
2. Delete the generated `ContentView.swift` and the `…App.swift` stub.
3. Drag the files from `ios/SorareBuddy/` in (check "Copy items if needed",
   add to the app target). `SorareBuddyApp.swift` is `@main`.
4. Build & run.

## Building it *with Claude Code* (locally on the Mac)

The Claude Code **cloud** can't build iOS apps, but the Claude Code **CLI on
your Mac** can drive `xcodegen`/`xcodebuild`/the simulator. To have Claude build
and iterate on the app for you:

1. Install Claude Code locally and open this repo on your Mac
   (`npm i -g @anthropic-ai/claude-code`, then `claude` in the repo folder — see
   https://code.claude.com/docs).
2. Ask it, e.g.: *"cd ios, run xcodegen, build SorareBuddy for the iPhone 15
   simulator and fix any compile errors."* It has Xcode/simulator access there.

A "new Claude Code project" = a session pointed at a repo. You can either keep
using this repo (scope work to `ios/` and `backend/`) or split the app into its
own repo; the app only depends on the backend's HTTP JSON, nothing else in here.

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
