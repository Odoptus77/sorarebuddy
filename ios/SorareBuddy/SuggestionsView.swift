import SwiftUI

struct SuggestionsView: View {
    @EnvironmentObject var store: Store

    private var rarities: [String] {
        var seen = [String]()
        for c in store.lineups?.competitions ?? [] where !seen.contains(c.rarity) {
            seen.append(c.rarity)
        }
        return seen
    }

    var body: some View {
        List {
            if let l = store.lineups {
                Section { header(l) }.listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                if l.sofascore == true { Section { sofaBanner } }
                if let hso = l.hotstreakOverview, !hso.isEmpty {
                    Section("Hot-Streak-Überblick (4 nötig + 1 Classic)") {
                        ForEach(hso) { h in hsRow(h) }
                    }
                }
                ForEach(rarities, id: \.self) { rar in
                    Section(rar.capitalized) {
                        ForEach(l.competitions.filter { $0.rarity == rar }) { comp in
                            CompetitionCard(comp: comp)
                        }
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Vorschläge")
    }

    private func header(_ l: Lineups) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Spieltag \(l.fixture.gameWeek.map(String.init) ?? "–") · \(Fmt.date(l.fixture.start))–\(Fmt.date(l.fixture.end))")
                .font(.system(size: 18, weight: .heavy))
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                KPICard(label: "Projiziert", value: "Σ \(Fmt.num(l.totalProjected, 0))", meta: "wenn alle spielen")
                KPICard(label: "Erwartung (× Startelf)", value: "Σ \(Fmt.num(l.totalExpected, 0))", meta: "Punkte × P(Start)")
                KPICard(label: "Karten", value: "\(l.cardsUsed ?? 0)", meta: "jede nur einmal")
                KPICard(label: "Aufstellungen",
                        value: "\(l.competitions.reduce(0) { $0 + $1.teams.count })",
                        meta: "nach Ertrag priorisiert", hero: true)
            }
        }
        .padding(.horizontal).padding(.vertical, 8)
    }

    private var sofaBanner: some View {
        Label("Voraussichtliche Aufstellungen (SofaScore) aktiv", systemImage: "checkmark.seal.fill")
            .font(.system(size: 13, weight: .semibold)).foregroundColor(Theme.gain)
    }

    private func hsRow(_ h: HotStreak) -> some View {
        HStack {
            Text(h.label.replacingOccurrences(of: "Pro · ", with: "")
                .replacingOccurrences(of: " (Hot Streak)", with: ""))
                .font(.system(size: 13, weight: .medium))
            Spacer()
            Text("\(h.inSeason)/\(h.needed ?? 4)").font(.system(size: 13, weight: .heavy))
            Image(systemName: h.fieldable ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundColor(h.fieldable ? Theme.gain : Theme.warn)
        }
    }
}

struct CompetitionCard: View {
    let comp: Competition
    @State private var expanded = true

    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            ForEach(Array(comp.teams.enumerated()), id: \.element.id) { idx, team in
                TeamCard(comp: comp, team: team, index: idx)
                    .padding(.top, 6)
            }
        } label: {
            VStack(alignment: .leading, spacing: 4) {
                Text(comp.label).font(.system(size: 15, weight: .bold))
                HStack(spacing: 6) {
                    Tag(text: "\(comp.format) · \(comp.size)")
                    if let pw = comp.prizeWeight {
                        Tag(text: "Pool ×\(Fmt.num(pw, 1))", bg: Theme.gain)
                    }
                    Text("bis \(comp.teamsCap) Team\(comp.teamsCap > 1 ? "s" : "")")
                        .font(.system(size: 11)).foregroundColor(.secondary)
                }
                if let dl = comp.deadlineFirst {
                    Text("⏱ ab \(Fmt.dateTime(dl))").font(.system(size: 11)).foregroundColor(.secondary)
                }
            }
        }
    }
}

struct TeamCard: View {
    let comp: Competition
    let team: Team
    let index: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Team \(index + 1)").font(.system(size: 14, weight: .heavy))
                if index == 0 { Tag(text: "sicher", bg: Theme.gain) }
                else if (team.riskFloor ?? 1) < 0.5 { Tag(text: "Risiko", bg: Theme.warn) }
                Spacer()
                Text("Σ \(Fmt.num(team.projectedTotal, 0))")
                    .font(.system(size: 14, weight: .heavy)).foregroundColor(Theme.accent)
            }
            // safety line
            HStack(spacing: 10) {
                if let a = team.avgStart {
                    label("Startelf-Schnitt", Fmt.pct(a), Theme.startColor(a))
                }
                if let m = team.minStart {
                    label("schwächster", Fmt.pct(m), Theme.startColor(m))
                }
                if let e = team.expectedTotal {
                    label("Erwartung", "Σ \(Fmt.num(e, 0))", .primary)
                }
            }.font(.system(size: 11))
            if let cap = comp.cap {
                Text("Cap \(Fmt.num(team.capUsed, 0)) / \(cap)")
                    .font(.system(size: 11)).foregroundColor((team.overCap == true) ? Theme.loss : .secondary)
            }
            if !team.complete {
                Text("⚠ Unvollständig – nicht genug spielende Karten (\(team.cards.count)/\(comp.size))")
                    .font(.system(size: 11)).foregroundColor(Theme.loss)
            }
            Divider()
            ForEach(team.cards) { card in PlayerRow(card: card) }
        }
        .padding(10)
        .background(Color(.tertiarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func label(_ k: String, _ v: String, _ c: Color) -> some View {
        HStack(spacing: 3) {
            Text(k).foregroundColor(.secondary)
            Text(v).fontWeight(.bold).foregroundColor(c)
        }
    }
}

struct PlayerRow: View {
    let card: LineupCard
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 6) {
                Text(SLOT_DE[card.slot ?? ""] ?? (card.slot ?? "–"))
                    .font(.system(size: 10, weight: .heavy)).foregroundColor(.secondary)
                    .frame(width: 34, alignment: .leading)
                Text(card.player).font(.system(size: 14, weight: .semibold))
                if card.captain == true { Tag(text: "C") }
                if card.classic == true || card.isClassic == true { Tag(text: "Classic", bg: .gray) }
                StartChip(prob: card.startProb)
                Spacer()
                VStack(alignment: .trailing, spacing: 0) {
                    Text(Fmt.num(card.proj, 1)).font(.system(size: 15, weight: .heavy))
                    if let ev = card.ev {
                        Text("EV \(Fmt.num(ev, 1))").font(.system(size: 10, weight: .semibold))
                            .foregroundColor(.secondary)
                    }
                }
            }
            HStack(spacing: 8) {
                Text("L5 \(Fmt.num(card.l5, 1)) · \(card.opponent ?? "?") (\(card.home == true ? "H" : "A"))")
                    .font(.system(size: 11)).foregroundColor(.secondary)
                MinutesTrail(mins: card.recentMins)
            }
            if let s = card.sofaStatus, let info = SOFA_DE[s] {
                Text("SofaScore: \(info.0)").font(.system(size: 10, weight: .semibold))
                    .foregroundColor(info.1)
            }
        }
        .padding(.vertical, 3)
    }
}
