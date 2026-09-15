import SwiftUI

struct ClubView: View {
    @EnvironmentObject var store: Store
    @State private var search = ""
    @State private var sort: SortKey = .saleNow

    enum SortKey: String, CaseIterable, Identifiable {
        case saleNow = "Verkauf jetzt", value = "Wert", reward = "Reward"
        case purchase = "Kaufpreis", delta = "Δ %"
        var id: String { rawValue }
    }

    private var rows: [ClubRow] {
        let all = store.club?.rows ?? []
        let filtered = search.isEmpty ? all :
            all.filter { $0.player.localizedCaseInsensitiveContains(search) }
        return filtered.sorted { a, b in
            switch sort {
            case .saleNow:  return saleNow(a) > saleNow(b)
            case .value:    return (a.valueEur ?? 0) > (b.valueEur ?? 0)
            case .reward:   return store.cardReward(a.cardSlug) > store.cardReward(b.cardSlug)
            case .purchase: return (a.purchaseEur ?? 0) > (b.purchaseEur ?? 0)
            case .delta:    return (a.deltaPct ?? -999) > (b.deltaPct ?? -999)
            }
        }
    }

    /// value + reward − purchase (what the card is worth if sold now)
    private func saleNow(_ r: ClubRow) -> Double {
        (r.valueEur ?? 0) + store.cardReward(r.cardSlug) - (r.purchaseEur ?? 0)
    }

    var body: some View {
        List {
            Section { kpis }.listRowInsets(EdgeInsets())
                .listRowBackground(Color.clear)
            Section {
                Picker("Sortieren", selection: $sort) {
                    ForEach(SortKey.allCases) { Text($0.rawValue).tag($0) }
                }.pickerStyle(.segmented)
            }
            Section("\(rows.count) Karten") {
                ForEach(rows) { row in CardRow(row: row, reward: store.cardReward(row.cardSlug),
                                               saleNow: saleNow(row)) }
            }
        }
        .listStyle(.insetGrouped)
        .searchable(text: $search, prompt: "Spieler suchen")
        .navigationTitle("Verein")
    }

    private var kpis: some View {
        let all = store.club?.rows ?? []
        let invested = all.compactMap { $0.purchaseEur }.reduce(0, +)
        let value = all.compactMap { $0.valueEur }.reduce(0, +)
        let reward = store.rewards?.totals?.totalRewardEur ?? 0
        return LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            KPICard(label: "Investiert", value: Fmt.money(invested), meta: "gekaufte Karten")
            KPICard(label: "Rewards erhalten", value: Fmt.money(reward),
                    meta: "\(store.rewards?.totals?.rewardLineups ?? 0) Lineups")
            KPICard(label: "Reward − Kauf", value: Fmt.money(reward - invested),
                    meta: "bisher eingespielt")
            KPICard(label: "Verkauf jetzt", value: Fmt.money(reward - invested + value),
                    meta: "+ Kartenwert", hero: true)
        }
        .padding(.horizontal).padding(.vertical, 8)
    }
}

private struct CardRow: View {
    let row: ClubRow
    let reward: Double
    let saleNow: Double
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(row.player).font(.system(size: 15, weight: .semibold))
                Spacer()
                Text(Fmt.money(saleNow))
                    .font(.system(size: 15, weight: .heavy))
                    .foregroundColor(saleNow >= 0 ? Theme.gain : Theme.loss)
            }
            HStack(spacing: 6) {
                Tag(text: row.rarity.capitalized,
                    bg: row.rarity == "rare" ? Theme.warn : Theme.accent)
                if let s = row.season { Text("\(String(s))").font(.caption2).foregroundColor(.secondary) }
                Spacer()
            }
            HStack(spacing: 12) {
                metric("Kauf", Fmt.money(row.purchaseEur))
                metric("Wert", Fmt.money(row.valueEur))
                metric("Reward", reward > 0 ? Fmt.money(reward) : "–")
            }.font(.system(size: 11)).foregroundColor(.secondary)
        }
        .padding(.vertical, 2)
    }
    private func metric(_ k: String, _ v: String) -> some View {
        HStack(spacing: 3) { Text(k + ":"); Text(v).foregroundColor(.primary) }
    }
}
