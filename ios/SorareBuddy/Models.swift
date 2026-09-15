import Foundation

// Codable models matching the backend JSON. The decoder uses
// .convertFromSnakeCase, so JSON keys like "purchase_eur" map to purchaseEur.
// Card slugs (dictionary keys, hyphenated) are unaffected by that strategy.

// MARK: - Club overview

struct Club: Codable {
    let nickname: String?
    let rows: [ClubRow]
}

struct ClubRow: Codable, Identifiable {
    var id: String { cardSlug }
    let player: String
    let rarity: String
    let season: Int?
    let cardSlug: String
    let transferType: String?
    let purchaseEur: Double?
    let valueEur: Double?
    let deltaEur: Double?
    let deltaPct: Double?
    // reward fields are merged in by the dashboard; the API exposes them via
    // the rewards payload keyed by card slug (see Rewards.cards).
}

// MARK: - Rewards

struct Rewards: Codable {
    let slug: String?
    let totals: RewardTotals?
    let players: [RewardPlayer]
    let cards: [String: CardReward]?
    let rewardLineups: [RewardLineup]?
}

struct RewardTotals: Codable {
    let fixtures: Int?
    let lineups: Int?
    let rewardLineups: Int?
    let totalRewardEur: Double?
}

struct RewardPlayer: Codable, Identifiable {
    var id: String { slug }
    let player: String
    let slug: String
    let rewardEur: Double
    let rewardLineups: Int
}

struct CardReward: Codable {
    let rewardEur: Double
    let rewardLineups: Int
}

struct RewardLineup: Codable, Identifiable {
    let id = UUID()
    let fixture: String?
    let leaderboard: String?
    let eur: Double?
    let ranking: Int?
    let score: Double?
    let players: [RewardLineupPlayer]?
    let cards: [String]?

    private enum CodingKeys: String, CodingKey {
        case fixture, leaderboard, eur, ranking, score, players, cards
    }
}

struct RewardLineupPlayer: Codable, Identifiable {
    var id: String { slug ?? displayName ?? UUID().uuidString }
    let slug: String?
    let displayName: String?
    let score: Double?
}

// MARK: - Lineup suggestions

struct Lineups: Codable {
    let fixture: Fixture
    let generated: String?
    let eligible: [String: Int]?
    let competitions: [Competition]
    let hotstreakOverview: [HotStreak]?
    let sofascore: Bool?
    let cardsUsed: Int?
    let totalProjected: Double?
    let totalExpected: Double?
}

struct Fixture: Codable {
    let slug: String
    let gameWeek: Int?
    let start: String?
    let end: String?
}

struct HotStreak: Codable, Identifiable {
    var id: String { "\(rarity)-\(label)" }
    let rarity: String
    let label: String
    let inSeason: Int
    let needed: Int?
    let fieldable: Bool
}

struct Competition: Codable, Identifiable {
    var id: String { "\(rarity)-\(label)" }
    let rarity: String
    let label: String
    let format: String
    let mode: String
    let size: Int
    let cap: Int?
    let teamsCap: Int
    let inSeason: Bool?
    let prizeWeight: Double?
    let deadlineFirst: String?
    let deadlineLast: String?
    let teams: [Team]
}

struct Team: Codable, Identifiable {
    let id = UUID()
    let cards: [LineupCard]
    let complete: Bool
    let capUsed: Double?
    let overCap: Bool?
    let projectedTotal: Double
    let expectedTotal: Double?
    let avgStart: Double?
    let minStart: Double?
    let riskFloor: Double?

    private enum CodingKeys: String, CodingKey {
        case cards, complete, capUsed, overCap, projectedTotal,
             expectedTotal, avgStart, minStart, riskFloor
    }
}

struct LineupCard: Codable, Identifiable {
    var id: String { slug }
    let slug: String
    let player: String
    let playerSlug: String?
    let season: Int?
    let positions: [String]?
    let age: Int?
    let clubName: String?
    let proj: Double
    let ev: Double?
    let startProb: Double?
    let sofaStatus: String?
    let recentMins: [Double?]?
    let injured: Bool?
    let capScore: Double?
    let l5: Double?
    let appearances: Int?
    let league: String?
    let country: String?
    let home: Bool?
    let opponent: String?
    let kickoff: String?
    let isClassic: Bool?
    let slot: String?
    let captain: Bool?
    let classic: Bool?
}

// MARK: - Bundle (all three in one response)

struct Bundle: Codable {
    let club: Club
    let rewards: Rewards
    let lineups: Lineups
}
