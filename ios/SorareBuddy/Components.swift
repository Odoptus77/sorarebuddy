import SwiftUI

/// Coloured start-probability chip (the Startelf score), e.g. "94%".
struct StartChip: View {
    let prob: Double?
    var body: some View {
        if let p = prob {
            Text(Fmt.pct(p))
                .font(.system(size: 10, weight: .heavy))
                .foregroundColor(.white)
                .padding(.horizontal, 5).padding(.vertical, 1)
                .background(Theme.startColor(p))
                .clipShape(RoundedRectangle(cornerRadius: 5))
        }
    }
}

/// Recent-minutes trail, colour-coded: green ≥60, amber 30–59, red <30.
struct MinutesTrail: View {
    let mins: [Double?]?
    var body: some View {
        if let mins = mins, !mins.isEmpty {
            HStack(spacing: 4) {
                Text("Min").font(.system(size: 10)).foregroundColor(.secondary)
                ForEach(Array(mins.enumerated()), id: \.offset) { _, m in
                    Text(label(m)).font(.system(size: 10, weight: .semibold))
                        .foregroundColor(color(m))
                }
            }
        }
    }
    private func label(_ m: Double?) -> String { m == nil ? "·" : "\(Int(m!.rounded()))" }
    private func color(_ m: Double?) -> Color {
        guard let m = m else { return Theme.loss }
        return m >= 60 ? Theme.gain : (m >= 30 ? Theme.warn : Theme.loss)
    }
}

/// Small badge (Classic, C for captain, format, ...).
struct Tag: View {
    let text: String
    var bg: Color = Theme.accent
    var body: some View {
        Text(text)
            .font(.system(size: 9.5, weight: .heavy))
            .foregroundColor(.white)
            .padding(.horizontal, 5).padding(.vertical, 1)
            .background(bg).clipShape(RoundedRectangle(cornerRadius: 5))
    }
}

/// KPI tile used on both screens.
struct KPICard: View {
    let label: String
    let value: String
    var meta: String? = nil
    var hero: Bool = false
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.system(size: 12, weight: .semibold))
                .foregroundColor(hero ? Color.white.opacity(0.8) : .secondary)
            Text(value).font(.system(size: 24, weight: .heavy))
                .foregroundColor(hero ? .white : .primary)
                .minimumScaleFactor(0.6).lineLimit(1)
            if let meta = meta {
                Text(meta).font(.system(size: 11))
                    .foregroundColor(hero ? Color.white.opacity(0.8) : .secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(hero ? AnyView(Theme.pitch) : AnyView(Color(.secondarySystemGroupedBackground)))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

let SLOT_DE: [String: String] = [
    "Goalkeeper": "TW", "Defender": "ABW", "Midfielder": "MF",
    "Forward": "ST", "EXTRA": "Extra", "Extra": "Extra"
]

let SOFA_DE: [String: (String, Color)] = [
    "confirmed_start": ("bestätigt: Start", Theme.gain),
    "confirmed_bench": ("bestätigt: Bank", Theme.loss),
    "confirmed_out":   ("nicht im Kader", Theme.loss),
    "pred_start":      ("voraussichtl. Start", Theme.warn),
    "pred_bench":      ("voraussichtl. Bank", Theme.loss),
]
