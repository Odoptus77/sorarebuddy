import SwiftUI

struct RootView: View {
    @EnvironmentObject var store: Store
    @State private var showSettings = false
    @State private var didLoad = false

    var body: some View {
        TabView {
            NavigationStack {
                content { ClubView() }
                    .toolbar { settingsButton }
            }
            .tabItem { Label("Verein", systemImage: "person.3.fill") }

            NavigationStack {
                content { SuggestionsView() }
                    .toolbar { settingsButton }
            }
            .tabItem { Label("Vorschläge", systemImage: "sparkles") }
        }
        .sheet(isPresented: $showSettings) { SettingsView() }
        .task {
            if !didLoad { didLoad = true; await store.refresh() }
        }
    }

    @ViewBuilder
    private func content<V: View>(@ViewBuilder _ view: () -> V) -> some View {
        ZStack {
            view()
            if store.loading && store.lineups == nil && store.club == nil {
                loadingOverlay
            }
            if let err = store.error, store.lineups == nil {
                errorOverlay(err)
            }
        }
        .refreshable { await store.refresh() }
    }

    private var settingsButton: some ToolbarContent {
        ToolbarItem(placement: .topBarTrailing) {
            Button { showSettings = true } label: { Image(systemName: "gearshape") }
        }
    }

    private var loadingOverlay: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text("Lade Daten…").font(.subheadline).foregroundColor(.secondary)
            Text("Der erste Abruf kann 1–2 Minuten dauern\n(danach aus dem Cache sofort).")
                .font(.caption).foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(24).background(.regularMaterial).clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private func errorOverlay(_ err: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "wifi.exclamationmark").font(.largeTitle).foregroundColor(Theme.warn)
            Text("Verbindung fehlgeschlagen").font(.headline)
            Text(err).font(.caption).foregroundColor(.secondary).multilineTextAlignment(.center)
            Button("Erneut versuchen") { Task { await store.refresh() } }
                .buttonStyle(.borderedProminent)
            Button("Einstellungen") { showSettings = true }
        }
        .padding(24)
    }
}

struct SettingsView: View {
    @EnvironmentObject var store: Store
    @Environment(\.dismiss) var dismiss
    // Same UserDefaults keys as AppConfig, so edits here update the shared values.
    @AppStorage("baseURL") private var baseURL = "http://localhost:8080"
    @AppStorage("managerSlug") private var managerSlug = "nicktd7"
    @AppStorage("rarities") private var rarities = "limited,rare"
    @AppStorage("appToken") private var appToken = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Backend") {
                    TextField("Backend-URL", text: $baseURL)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                        .keyboardType(.URL)
                    SecureField("App-Token (optional)", text: $appToken)
                }
                Section("Manager") {
                    TextField("Slug (z. B. nicktd7)", text: $managerSlug)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                    TextField("Seltenheiten", text: $rarities)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                }
                Section {
                    Button("Speichern & neu laden") {
                        dismiss(); Task { await store.refresh() }
                    }
                }
                Section {
                    Text("Der Sorare-API-Key liegt ausschließlich auf dem Backend, "
                         + "nie in der App.")
                        .font(.footnote).foregroundColor(.secondary)
                }
            }
            .navigationTitle("Einstellungen")
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Fertig") { dismiss() } } }
        }
    }
}
