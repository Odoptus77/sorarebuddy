import SwiftUI

// User-editable connection settings, persisted in UserDefaults via @AppStorage.
// The Sorare API key is NOT here — it lives only on the backend.
final class AppConfig: ObservableObject {
    @AppStorage("baseURL") var baseURL: String = "http://localhost:8080"
    @AppStorage("managerSlug") var managerSlug: String = "nicktd7"
    @AppStorage("rarities") var rarities: String = "limited,rare"
    @AppStorage("appToken") var appToken: String = ""   // optional Bearer token

    var normalizedBase: String {
        var b = baseURL.trimmingCharacters(in: .whitespaces)
        if b.hasSuffix("/") { b.removeLast() }
        return b
    }
}
