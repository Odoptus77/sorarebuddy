import SwiftUI

@main
struct SorareBuddyApp: App {
    @StateObject private var config: AppConfig
    @StateObject private var store: Store

    init() {
        let cfg = AppConfig()
        _config = StateObject(wrappedValue: cfg)
        _store = StateObject(wrappedValue: Store(config: cfg))
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(store)
                .environmentObject(config)
        }
    }
}
