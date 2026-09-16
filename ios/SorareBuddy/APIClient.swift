import Foundation

enum APIError: LocalizedError {
    case badURL, http(Int), decoding(String), server(String)
    var errorDescription: String? {
        switch self {
        case .badURL: return "Ungültige Backend-URL"
        case .http(let c): return "HTTP \(c)"
        case .decoding(let m): return "Antwort nicht lesbar: \(m)"
        case .server(let m): return m
        }
    }
}

struct APIClient {
    let config: AppConfig

    private func decoder() -> JSONDecoder {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }

    private func request(_ path: String, query: [String: String]) async throws -> Data {
        guard var comps = URLComponents(string: config.normalizedBase + path) else {
            throw APIError.badURL
        }
        comps.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        guard let url = comps.url else { throw APIError.badURL }
        var req = URLRequest(url: url)
        req.timeoutInterval = 600   // cold pipeline runs can take several minutes
                                    // (prewarm the backend cache to avoid this)
        if !config.appToken.isEmpty {
            req.setValue("Bearer \(config.appToken)", forHTTPHeaderField: "Authorization")
        }
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw APIError.server("Keine Antwort") }
        guard (200..<300).contains(http.statusCode) else {
            if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let msg = obj["error"] as? String {
                throw APIError.server("\(http.statusCode): \(msg)")
            }
            throw APIError.http(http.statusCode)
        }
        return data
    }

    private func commonQuery(force: Bool) -> [String: String] {
        var q = ["slug": config.managerSlug.lowercased(), "rarities": config.rarities]
        if force { q["refresh"] = "1" }   // bypass the backend cache, refetch from Sorare
        return q
    }

    func health() async -> Bool {
        (try? await request("/health", query: [:])) != nil
    }

    func club(force: Bool = false) async throws -> Club {
        let data = try await request("/api/club", query: commonQuery(force: force))
        do { return try decoder().decode(Club.self, from: data) }
        catch { throw APIError.decoding(String(describing: error)) }
    }

    func rewards(force: Bool = false) async throws -> Rewards {
        let data = try await request("/api/rewards", query: commonQuery(force: force))
        do { return try decoder().decode(Rewards.self, from: data) }
        catch { throw APIError.decoding(String(describing: error)) }
    }

    func lineups(force: Bool = false) async throws -> Lineups {
        let data = try await request("/api/lineups", query: commonQuery(force: force))
        do { return try decoder().decode(Lineups.self, from: data) }
        catch { throw APIError.decoding(String(describing: error)) }
    }

    func bundle(force: Bool = false) async throws -> Bundle {
        let data = try await request("/api/bundle", query: commonQuery(force: force))
        do { return try decoder().decode(Bundle.self, from: data) }
        catch { throw APIError.decoding(String(describing: error)) }
    }
}

// Observable store the views bind to.
@MainActor
final class Store: ObservableObject {
    @Published var club: Club?
    @Published var rewards: Rewards?
    @Published var lineups: Lineups?
    @Published var loading = false
    @Published var error: String?

    let config: AppConfig
    init(config: AppConfig) { self.config = config }

    /// force = true bypasses the backend cache and refetches from Sorare
    /// (the explicit Refresh button); false uses the cache (launch / pull).
    func refresh(force: Bool = false) async {
        loading = true; error = nil
        let api = APIClient(config: config)
        do {
            // fetch in parallel; each endpoint is independently cached server-side
            async let c = api.club(force: force)
            async let r = api.rewards(force: force)
            async let l = api.lineups(force: force)
            let (club, rewards, lineups) = try await (c, r, l)
            self.club = club; self.rewards = rewards; self.lineups = lineups
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        loading = false
    }

    /// reward attributed to a specific card slug (from the rewards payload)
    func cardReward(_ slug: String) -> Double {
        rewards?.cards?[slug]?.rewardEur ?? 0
    }
}
