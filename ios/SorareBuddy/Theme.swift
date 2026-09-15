import SwiftUI

enum Theme {
    static let pitch = Color(red: 0.13, green: 0.35, blue: 0.22)
    static let accent = Color(red: 0.11, green: 0.42, blue: 0.30)
    static let gain = Color(red: 0.11, green: 0.55, blue: 0.30)
    static let loss = Color(red: 0.78, green: 0.20, blue: 0.20)
    static let warn = Color(red: 0.79, green: 0.54, blue: 0.0)

    /// colour for a start probability (0...1)
    static func startColor(_ p: Double) -> Color {
        p >= 0.75 ? gain : (p >= 0.5 ? warn : loss)
    }
}

enum Fmt {
    static let eur: NumberFormatter = {
        let f = NumberFormatter(); f.numberStyle = .currency
        f.currencyCode = "EUR"; f.locale = Locale(identifier: "de_DE")
        f.maximumFractionDigits = 2; return f
    }()
    static func money(_ v: Double?) -> String {
        guard let v = v else { return "–" }
        return eur.string(from: NSNumber(value: v)) ?? "–"
    }
    static func num(_ v: Double?, _ digits: Int = 1) -> String {
        guard let v = v else { return "–" }
        let f = NumberFormatter(); f.locale = Locale(identifier: "de_DE")
        f.minimumFractionDigits = 0; f.maximumFractionDigits = digits
        return f.string(from: NSNumber(value: v)) ?? "–"
    }
    static func pct(_ p: Double?) -> String {
        guard let p = p else { return "–" }
        return "\(Int((p * 100).rounded()))%"
    }
    /// ISO date -> "Sa. 20. Sep, 15:30"
    static func dateTime(_ iso: String?) -> String {
        guard let iso = iso, let d = isoDate(iso) else { return "" }
        let f = DateFormatter(); f.locale = Locale(identifier: "de_DE")
        f.dateFormat = "EE d. MMM, HH:mm"; return f.string(from: d)
    }
    static func date(_ iso: String?) -> String {
        guard let iso = iso, let d = isoDate(iso) else { return "" }
        let f = DateFormatter(); f.locale = Locale(identifier: "de_DE")
        f.dateFormat = "d. MMM"; return f.string(from: d)
    }
    private static func isoDate(_ s: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.date(from: s) ?? ISO8601DateFormatter().date(from: s)
    }
}
