// Shapes of the JSON the Python pipeline writes (lineup_suggest.py,
// club_overview.py, evaluate.py, lineup_review.py). Only the fields the
// dashboard reads are typed; everything else passes through untouched.

export type Fixture = {
  slug: string;
  gameWeek: number;
  start: string; // = Classic deadline of this GW (UTC)
  end: string;
};

export type LineupCard = {
  slug: string;
  player: string;
  player_slug: string;
  season: number;
  positions: string[];
  slot: string;
  club_name?: string;
  team_name?: string;
  opponent?: string;
  opp_type?: "Club" | "NationalTeam" | string;
  kickoff?: string;
  home?: boolean;
  proj: number;
  ev: number;
  start_prob: number;
  start_src?: string;
  model_prob?: number;
  playing_status?: string | null;
  captain?: boolean;
  is_classic?: boolean;
  injured?: boolean;
  suspended?: boolean;
  intl_duty?: boolean;
  status_conflict?: boolean;
  override_stale?: boolean;
  apif?: string | null;
  cap_score?: number;
  l5?: number;
  matchup?: number;
};

export type LineupTeam = {
  cards: LineupCard[];
  complete: boolean;
  cap_used?: number | null;
  over_cap?: boolean;
  projected_total: number;
  expected_total: number;
  avg_start: number;
  min_start: number;
};

export type Competition = {
  rarity: string;
  label: string;
  format?: string;
  mode?: string;
  size: number;
  cap?: number | null;
  teams_cap?: number;
  in_season?: boolean;
  teams: LineupTeam[];
};

export type LineupsData = {
  fixture: Fixture;
  generated: string;
  international_break?: boolean;
  competitions: Competition[];
  eligible?: Record<string, LineupCard[]>;
  cards_used?: number;
  total_projected: number;
  total_expected: number;
};

export type ClubRow = {
  player: string;
  rarity: string;
  season: number;
  card_slug: string;
  transfer_type?: string | null;
  purchase_eur?: number | null;
  value_eur?: number | null;
  delta_eur?: number | null;
  delta_pct?: number | null;
};

export type ClubData = { nickname: string; rows: ClubRow[] };

export type SourceStat = { n: number; mean_pred: number; actual: number; brier: number };

export type Evaluation = {
  updated: string;
  evaluated: number;
  pending: number;
  upcoming?: number;
  brier: number | null;
  brier_raw: number | null;
  start_rate: number;
  by_source: Record<string, SourceStat>;
  out_signals?: { n: number; correct_out: number };
  playing_status?: Record<string, { n: number; started: number }>;
  projection?: {
    n: number;
    mae: number;
    bias: number;
    groups?: Record<string, { n: number; bias: number; mae: number }>;
  } | null;
  misses?: { player: string; kickoff: string; pred: number; src: string; started: boolean; played: boolean }[];
};

export type Calibration = {
  _updated: string;
  n: number;
  min_n: number;
  active: boolean;
  proj_scale?: { value: number; n: number };
  proj_scale_groups?: Record<string, { value: number; n: number }>;
  brier_raw?: number;
  brier_calibrated_in_sample?: number;
};

export type ModelData = { evaluation: Evaluation | null; calibration: Calibration | null };

export type ReviewApp = {
  player: string;
  player_slug: string;
  pos: string;
  captain: boolean;
  raw: number | null;
  final: number | null;
  mins: number | null;
  started: number | null;
  kickoff: string | null;
  game_type: "club" | "national" | null;
  dnp: boolean;
  pending: boolean;
  pred_start?: number | null;
  pred_proj?: number | null;
};

export type ReviewLineup = {
  competition: string;
  rank: number | null;
  score: number;
  rewards: number;
  reward_eur: number;
  reward_cards: number;
  apps: ReviewApp[];
  captain?: string;
  best_captain?: string;
  captain_loss?: number;
};

export type ReviewGw = {
  gw: number;
  slug: string;
  state: string;
  lineups: ReviewLineup[];
  total: number;
  avg: number;
  dnp: string[];
  pending_games: number;
  captain_loss: number;
};

export type ReviewData = {
  updated: string;
  captain_multiplier: number;
  gameweeks: ReviewGw[];
};

/** Result of a data load: the payload, or why it isn't there. */
export type Loaded<T> =
  | { ok: true; data: T; source: string; ageSeconds?: number | null }
  | { ok: false; error: string; source: string };
