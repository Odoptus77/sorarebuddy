#!/usr/bin/env python3
"""Suggest the best Sorare setup for the upcoming gameweek, per competition.

Public data only (no OAuth). Reads the gameweek's competition structure and
builds the best lineup(s) for each general competition, respecting:
  - format: Classic = SO7 (7 cards), Arena = SO5 (5 cards)
  - the formation: SO5 = GK, DEF, MID, FWD, Extra; SO7 = GK, 2x DEF, 2x MID,
    FWD, Extra (Extra = any outfield position)
  - the cap (Arena only): sum of the cards' L15 average score <= cap
  - teamsCap: up to N teams per competition, each using DISTINCT cards
  - no defence-vs-attack clash: within one team we avoid pairing our GK/DEF
    with an opposing FWD from the SAME match (their points partly cancel)
maximising projected score (recent form x appearance rate x home edge x
opponent matchup), excluding injured players and players without a game.

Only the general All Star / Champion competitions are built (no per-player
league or age filter needed). League-specific (SPFL, LALIGA, ...) and Under-21
competitions are skipped. Opponent strength is not in the Sorare API but can be
supplied via --strength (a JSON of 0..1 ratings per club/nation); the projection
is then scaled by the matchup (weak opponent -> up, strong -> down). Non-injury
news still isn't in the API -- cross-check it per CLAUDE.md before the deadline.
A card may be reused across DIFFERENT competitions (Sorare allows this);
within one competition's multiple teams the cards are distinct.

Usage:
    python3 lineup_suggest.py <manager-slug> [--json lineups.json] [--rarities limited,rare]
        [--exclude "player-slug-or-name,..."]   # drop injured/suspended players
        [--strength team_strength.json] [--matchup-weight 0.20]  # weight by opponent
"""
import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time

from sorare_client import graphql

CARD_PAGE = 50
PLAYER_BATCH = 10   # detailedScore (minutes) per game inflates query complexity
GAMES_BACK = 5      # recent games used for the Startelf (start-probability) score
PROJ_GAMES = 15     # games fetched for the played-only scoring projection
PACE = 0.25
# During an international break, a player called up to his country will NOT play
# a club game that happens to fall in the same window (Sorare shows ~0%), yet
# the club-minutes model still rates him a starter. When his nation plays in the
# window and this is a CLUB game, downweight his start prob by this factor and
# flag it for a Sorare-% check (soft, not a hard drop -> a researched override
# or a confirmed club start can still restore him).
INTL_DUTY_FACTOR = 0.12
# Softer downweight for a player whose nation ALREADY played this break and
# who logged 0 minutes in it (unused squad member). Was x0.12; the Treffer-Bilanz
# of 02.10.2026 showed national coaches rotate a lot between the two matchdays
# (2 of 6 flagged players started, e.g. Krejci 90', Baribo 69'; the club model
# alone had them at ~39% vs 33% real) -> x0.6 (source "natl_bench_soft").
# Bilanz 03.10.: 5 more flagged at x0.6, none started (2 of 11 overall) ->
# Brier over all 11 is flat between x0.3 and x0.5 (best x0.4: 0.150 vs 0.156) -> x0.4.
NATIONAL_BENCH_FACTOR = 0.4
NATIONAL_BENCH_DAYS = 16   # how far back to look for the nation's break games (12 missed
#   the first game of a long window: Laporte 90' on 26.09. was ignored for GW719, 02.10.2026)
# A red card (straight or 2nd yellow) in the player's most recent game almost
# always bans him from the next game of the SAME competition stream (club vs
# national). Soft downweight + flag (not a hard drop: reds get rescinded, and
# the ban is competition-specific) so it surfaces for a check.
SUSPENSION_FACTOR = 0.10
# API-Football fixture injury/suspension report (injuries_feed.py): "Missing
# Fixture" = listed out for this game, "Questionable" = doubtful. Soft factors +
# flag, like the other automatic signals, so a researched override still wins.
APIF_MISSING_FACTOR = 0.10
APIF_DOUBT_FACTOR = 0.60
# Mild recalibration of the model start probability toward the observed base
# rate: p' = (1-k)*p + k*base. Backtest-tuned (k=0.10 minimised Brier); a small,
# monotonic nudge that mainly de-biases the extremes and barely moves rankings.
START_RECAL_K = 0.10
BASE_START_RATE = 0.48     # squad-wide observed start rate (backtest, n~5k)
POS_SLOTS = ["Goalkeeper", "Defender", "Midfielder", "Forward"]

# Exact slot make-up per lineup size (EXTRA = any outfield position).
#   SO5 (Arena):     GK, DEF, MID, FWD, Extra
#   SO7 (Pro/Classic): GK, 2x DEF, 2x MID, FWD, Extra
FORMATIONS = {
    5: ["Goalkeeper", "Defender", "Midfielder", "Forward", "EXTRA"],
    7: ["Goalkeeper", "Defender", "Defender", "Midfielder", "Midfielder",
        "Forward", "EXTRA"],
}


def formation_for(size):
    """Slot list for a lineup of `size` cards (falls back to 1-per-line+extras)."""
    return FORMATIONS.get(size, list(POS_SLOTS) + ["EXTRA"] * (size - 4))


# UEFA member nations (normalized: lowercase, no accents), for a "European
# Nations" national-team competition filter. Includes common name variants.
UEFA_NATIONS = {
    "albania", "andorra", "armenia", "austria", "azerbaijan", "belarus",
    "belgium", "bosnia and herzegovina", "bulgaria", "croatia", "cyprus",
    "czechia", "czech republic", "denmark", "england", "estonia",
    "faroe islands", "finland", "france", "georgia", "germany", "gibraltar",
    "greece", "hungary", "iceland", "israel", "italy", "kazakhstan", "kosovo",
    "latvia", "liechtenstein", "lithuania", "luxembourg", "malta", "moldova",
    "montenegro", "netherlands", "north macedonia", "northern ireland",
    "norway", "poland", "portugal", "republic of ireland", "ireland",
    "romania", "russia", "san marino", "scotland", "serbia", "slovakia",
    "slovenia", "spain", "sweden", "switzerland", "turkiye", "turkey",
    "ukraine", "wales",
}
RARITY_TOKENS = [("super_rare", "SUPER_RARE"), ("limited", "LIMITED"),
                 ("rare", "RARE"), ("unique", "UNIQUE")]
# IN_SEASON_<TOKEN> competition -> (domesticLeague slug prefix, readable name).
# Matched with str.startswith so e.g. "bundesliga" excludes "2-bundesliga".
LEAGUE_MAP = {
    "ENGLAND": ("premier-league", "Premier League"),
    "ENGLAND_SECOND": ("championship", "Championship"),
    "SPAIN": ("laliga", "LALIGA"),
    "GERMANY": ("bundesliga-de", "Bundesliga"),
    "FRANCE": ("ligue-1", "Ligue 1"),
    "ITALY": ("serie-a", "Serie A"),
    "NETHERLANDS": ("eredivisie", "Eredivisie"),
    "SCOTLAND": ("premiership-gb-sct", "SPFL"),
    "JUPILER": ("jupiler", "Jupiler Pro League"),
    "PORTUGAL": ("primeira-liga", "Liga Portugal"),
    "US": ("mlspa", "MLS"),      # Sorare's MLS token is IN_SEASON_US_*
    "USA": ("mlspa", "MLS"),
    "MLS": ("mlspa", "MLS"),
}
# Contender groups these leagues (Sorare 27); classic slot allows ANY league.
CONTENDER_LEAGUES = ("austrian-bundesliga", "2-bundesliga", "ligue-2",
                     "hnl", "prva-hnl", "1-hnl", "supersport-hnl")
# Fallback: IN_SEASON_<COUNTRY> token -> club country code, for leagues without a
# precise slug in LEAGUE_MAP (one top-flight per country is filtered by country).
COUNTRY_ISO = {
    "SCOTLAND": "gb-sct", "SPAIN": "es", "GERMANY": "de", "FRANCE": "fr",
    "ITALY": "it", "NETHERLANDS": "nl", "PORTUGAL": "pt", "BELGIUM": "be",
    "JUPILER": "be", "JAPAN": "jp", "KOREA": "kr", "USA": "us", "MLS": "us",
    "BRAZIL": "br", "TURKEY": "tr", "DENMARK": "dk", "AUSTRIA": "at",
    "CROATIA": "hr", "ARGENTINA": "ar", "MEXICO": "mx", "COLOMBIA": "co",
    "PERU": "pe", "RUSSIA": "ru", "SWITZERLAND": "ch", "POLAND": "pl",
    "NORWAY": "no", "SWEDEN": "se", "GREECE": "gr",
}


def resolve_league(token):
    """Map an IN_SEASON_<token> to a card filter. Prefer a precise league slug;
    otherwise fall back to the club country code. Returns (kind, value, name)."""
    if token in LEAGUE_MAP:
        slug, name = LEAGUE_MAP[token]
        return ("league", slug, name)
    if token in COUNTRY_ISO:
        return ("country", COUNTRY_ISO[token], token.replace("_", " ").title())
    return None


# --- Prize-pool weighting (editable) --------------------------------------
# Relative prize weight per competition, used to turn "best lineup" into
# "best expected reward". Derived from the Sorare 27 blog figures (Rare ~2x
# Limited: e.g. $6k vs $12k Pro, $5k vs $10k Arena; Pro slightly above Arena;
# Champion/All-Star and the big leagues carry the largest pools). Not exact
# payouts — adjust these numbers to match the official prize-pool tables.
RARITY_WEIGHT = {"limited": 1.0, "rare": 2.0, "super_rare": 5.0, "unique": 8.0}
MODE_WEIGHT = {"Pro": 1.25, "Arena": 1.0}
TOP_LEAGUE_PREFIXES = ("premier-league", "bundesliga", "laliga", "ligue-1")
FAMILY_TOP_LEAGUE = 1.3      # biggest league pools
FAMILY_OTHER_LEAGUE = 1.0
FAMILY_FLAGSHIP = 1.5        # Champion / All Star (Pro)
FAMILY_ALLSTAR_ARENA = 1.2   # All-Star arena
FAMILY_U23_PRO = 1.1         # Under 23 (Pro) — dedicated pool, below flagship
FAMILY_U23_ARENA = 0.95      # Under 23 (Arena)


def prize_weight(comp):
    rw = RARITY_WEIGHT.get(comp["rarity"], 1.0)
    mw = MODE_WEIGHT.get(comp["mode"], 1.0)
    pref = comp.get("league_prefix")
    if comp.get("max_age"):
        fam = FAMILY_U23_PRO if comp["mode"] == "Pro" else FAMILY_U23_ARENA
    elif comp.get("contender"):
        fam = 0.9                       # grouped competition, smaller pools
    elif pref or comp.get("country_code"):
        fam = FAMILY_TOP_LEAGUE if (pref and pref.startswith(TOP_LEAGUE_PREFIXES)) else FAMILY_OTHER_LEAGUE
    elif comp["mode"] == "Pro":
        fam = FAMILY_FLAGSHIP
    else:
        fam = FAMILY_ALLSTAR_ARENA
    return round(rw * mw * fam, 2)

CARDS_QUERY = """
query Cards($slug: String!, $after: String, $rarities: [Rarity!]) {
  user(slug: $slug) {
    cards(first: %d, after: $after, rarities: $rarities) {
      pageInfo { hasNextPage endCursor }
      nodes { slug rarityTyped seasonYear anyPositions sealed
        anyPlayer { slug displayName anyPositions } }
    }
  }
}
""" % CARD_PAGE

PLAYER_FIELDS = """
  slug displayName anyPositions age lastFifteenSo5Appearances
  country { code }
  activeClub { ... on Club { name country { code } domesticLeague { slug } } }
  activeInjuries { kind expectedEndDate active }
  nextGame { date statusTyped
    homeTeam { __typename name ... on NationalTeam { country { code } } }
    awayTeam { __typename name ... on NationalTeam { country { code } } } }
  playerGameScores(last: %d) { score
    anyGame { date homeTeam { __typename } awayTeam { __typename } }
    detailedScore { stat statValue } }
  l5: averageScore(type: LAST_FIVE_SO5_AVERAGE_SCORE)
  l15: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
  ... on Player {
    playingStatus
    nextClassicFixturePlayingStatusOdds {
      starterOddsBasisPoints substituteOddsBasisPoints reliability } }
""" % PROJ_GAMES


def rarity_of(t):
    for rar, tok in RARITY_TOKENS:
        if tok in t:
            return rar
    return None


def get_upcoming_fixture(slug=None):
    q = "{ so5 { so5Fixtures(first: 8) { nodes { slug gameWeek aasmState startDate endDate } } } }"
    nodes = graphql(q)["data"]["so5"]["so5Fixtures"]["nodes"]
    if slug:                                   # explicit fixture (e.g. next GW)
        for n in nodes:
            if n["slug"] == slug or str(n["gameWeek"]) == str(slug):
                return n
        sys.exit(f"Fixture '{slug}' not found. Available: "
                 + ", ".join(n["slug"] for n in nodes))
    now = dt.datetime.now(dt.timezone.utc)
    up = []
    for n in nodes:
        try:
            start = dt.datetime.fromisoformat(n["startDate"].replace("Z", "+00:00"))
        except Exception:
            continue
        if start > now:
            up.append((start, n))
    up.sort(key=lambda x: x[0])
    return up[0][1] if up else nodes[0]


def fetch_fixture_games(fx_slug):
    """Index of this fixture's games by club name and by nation code:
    {"club": {name: [game, ...]}, "nation": {code: [game, ...]}}, each list
    sorted by date. Used when a player's `nextGame` still lies in the
    CURRENT (locked) GW: his first game inside the planned window is looked up
    here, so a draft for the next GW isn't missing everyone who plays in both
    (e.g. national MD 01.10. and again 04.10.)."""
    q = ('{ so5 { so5Fixture(slug: "%s") { anyGames { date statusTyped '
         'homeTeam { __typename name ... on NationalTeam { country { code } } } '
         'awayTeam { __typename name ... on NationalTeam { country { code } } } } } } }'
         % fx_slug)
    idx = {"club": {}, "nation": {}}
    try:
        data = (graphql(q) or {}).get("data") or {}
    except Exception as exc:
        print(f"WARNING: could not read fixture games: {exc}", file=sys.stderr)
        return idx
    games = (((data.get("so5") or {}).get("so5Fixture")) or {}).get("anyGames") or []
    for g in sorted((g for g in games if g.get("date")), key=lambda g: g["date"]):
        for side in ("homeTeam", "awayTeam"):
            t = g.get(side) or {}
            if t.get("__typename") == "NationalTeam":
                c = (t.get("country") or {}).get("code")
                if c:
                    idx["nation"].setdefault(c, []).append(g)
            elif t.get("name"):
                idx["club"].setdefault(t["name"], []).append(g)
    return idx


def _game_in_window(pd, ng, ws, we, fx_games):
    """Replacement for a nextGame that lies BEFORE the window: the player's
    first game inside [ws, we] -- national if his pending game is a national
    one (he is with his nation), else his club's."""
    if not fx_games:
        return None
    def _in(games):
        for g in games or []:
            try:
                gd = dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
            except Exception:
                continue
            if ws <= gd <= we:
                return g
        return None
    nat = (pd.get("country") or {}).get("code")
    club = (pd.get("activeClub") or {}).get("name")
    with_nation = any((ng.get(s) or {}).get("__typename") == "NationalTeam"
                      for s in ("homeTeam", "awayTeam"))
    nat_g = _in(fx_games["nation"].get(nat)) if nat else None
    club_g = _in(fx_games["club"].get(club)) if club else None
    # Not with his nation -> only his club game counts. Falling back to the
    # nation's game here put club-only players (Ortuno, Albacete; not in the
    # Spain squad) into Spain's national game (bug found 03.10.2026).
    return (nat_g or club_g) if with_nation else club_g


def fetch_nation_last_games(fx_slug):
    """Map country code -> datetime of that nation's LAST national-team game in
    this fixture window. One query over the fixture's games; empty for a pure
    club GW (self-gating: no national games -> no call-up logic).

    The last-game datetime (not just "plays at all") is what tells a club game
    apart: a player is with his nation only while it is still playing, so a club
    game clearly AFTER his nation's last window game means he is back and plays.

    NOTE: Sorare's fixture only carries the national games it actually runs (in
    practice UEFA nations). Call-ups to nations Sorare doesn't carry (much of
    CAF/AFC/CONCACAF/CONMEBOL — e.g. a Gabon/Korea/Jamaica international playing
    in MLS or the K-League through the break) stay INVISIBLE to the API and must
    be declared in international_callups.json instead."""
    q = ('{ so5 { so5Fixture(slug: "%s") { anyGames { date '
         'homeTeam { __typename ... on NationalTeam { country { code } } } '
         'awayTeam { __typename ... on NationalTeam { country { code } } } } } } }'
         % fx_slug)
    try:
        data = (graphql(q) or {}).get("data") or {}
    except Exception as exc:
        print(f"WARNING: could not read fixture games for int'l-break "
              f"detection: {exc}", file=sys.stderr)
        return {}
    fix = ((data.get("so5") or {}).get("so5Fixture")) or {}
    last = {}
    for g in (fix.get("anyGames") or []):
        gd = g.get("date")
        if not gd:
            continue
        try:
            gdt = dt.datetime.fromisoformat(gd.replace("Z", "+00:00"))
        except Exception:
            continue
        for side in ("homeTeam", "awayTeam"):
            t = g.get(side) or {}
            if t.get("__typename") == "NationalTeam":
                c = (t.get("country") or {}).get("code")
                if c and (c not in last or gdt > last[c]):
                    last[c] = gdt
    return last


# A club game is treated as missed to national duty only if it kicks off no
# later than this long after the nation's LAST game in the window (else the
# player is back from the national team and plays his club game).
DUTY_RETURN_BUFFER = dt.timedelta(hours=24)


def _on_national_duty(entry, nation_last_game):
    """True if the player's nation is still on duty when his CLUB game kicks off
    -> he is with his country and will miss the club game. Compares his club
    kickoff against his nation's LAST game in the window (+ a return buffer)."""
    last = nation_last_game.get(entry.get("nat_code"))
    if last is None:
        return False                     # nation not playing this window
    ko = entry.get("kickoff")
    if not ko:
        return True                      # unknown kickoff -> be safe, flag it
    try:
        kdt = dt.datetime.fromisoformat(ko.replace("Z", "+00:00"))
    except Exception:
        return True
    return kdt <= last + DUTY_RETURN_BUFFER


def fetch_competitions(fx_slug, rarities):
    """Return the general (All Star / Champion) competitions to build, per rarity."""
    q = ('{ so5 { so5Fixture(slug: "%s") { so5Leaderboards { displayName so5LeaderboardType teamsCap } } } }'
         % fx_slug)
    lbs = graphql(q)["data"]["so5"]["so5Fixture"]["so5Leaderboards"]
    # collapse to distinct (rarity, format, cap) — that triple determines the
    # optimal lineup; several named competitions share it.
    groups = {}
    for lb in lbs:
        t = lb["so5LeaderboardType"]
        rar = rarity_of(t)
        if rar not in rarities:
            continue
        is_arena = "ARENA" in t
        m = re.search(r"Cap (\d+)", lb["displayName"])
        cap = int(m.group(1)) if m else None
        tcap = min(4, lb.get("teamsCap") or 1)

        if "UNDER_TWENTY_ONE" in t or "UNDER_TWENTY_THREE" in t:
            # U23 competition (typed UNDER_TWENTY_ONE, displayed "Under 23"):
            # Pro = SO7, Arena = SO5 with cap; age-limited, all seasons, no league.
            key = (rar, "SO5" if is_arena else "SO7", cap, "U23", False)
            g = groups.setdefault(key, {"teams_cap": 1})
            g["teams_cap"] = max(g["teams_cap"], tcap)
        elif "ALL_STAR" in t or "CHAMPIONS" in t:
            fam = "Champion" if "CHAMPIONS" in t else "All Star"
            key = (rar, "SO5" if is_arena else "SO7", cap, None, False)
            g = groups.setdefault(key, {"families": set(), "teams_cap": 1})
            g["families"].add(fam)
            g["teams_cap"] = max(g["teams_cap"], tcap)
        elif t.startswith("IN_SEASON_") and not is_arena:
            # league Hot Streak (5 cards, in-season, league filter)
            body = t[len("IN_SEASON_"):]
            for tok in RARITY_TOKENS:
                body = body.replace("_" + tok[1], "")
            for suf in ("_PVP", "_PVE", "_PVH"):
                body = body.replace(suf, "")
            token = body.strip("_")           # SCOTLAND, JAPAN, CONTENDERS, ...
            if token not in ("CONTENDERS",) and resolve_league(token) is None:
                continue
            key = (rar, "HS", None, token, True)
            g = groups.setdefault(key, {"teams_cap": 1})
            g["teams_cap"] = max(g["teams_cap"], tcap)
        elif is_arena:
            # league arena (SO5, cap, league filter, all seasons)
            m2 = re.match(r"ALL_SEASONS_(.+?)_ARENA", t)
            token = (m2.group(1) if m2 else "").strip("_")
            if token not in ("CONTENDER", "CONTENDERS") and resolve_league(token) is None:
                continue  # U21 arena / unmapped
            if token == "CONTENDER":
                token = "CONTENDERS"
            key = (rar, "SO5", cap, token, False)
            g = groups.setdefault(key, {"teams_cap": 1})
            g["teams_cap"] = max(g["teams_cap"], tcap)
        # else: U21 classic / special -> skipped

    comps = []
    for (rar, fmt, cap, token, in_season), g in groups.items():
        hotstreak = (fmt == "HS")
        mode = "Arena" if fmt == "SO5" else "Pro"   # Sorare 27: Pro (SO7/Hot Streak), Arena (SO5)
        size = 7 if fmt == "SO7" else 5             # Hot Streak & Arena = 5, Classic Pro = 7
        fmt_label = {"HS": "Hot Streak", "SO7": "SO7", "SO5": "SO5"}[fmt]
        league_prefix = None
        country_code = None
        league_prefixes = None
        contender = False
        max_age = None
        if token == "U23":
            max_age = 23
            name = "Under 23"
            if fmt == "SO7":
                label = "Pro · Under 23"
            elif cap:
                label = f"Arena · Under 23 · Cap {cap}"
            else:
                label = "Arena · Under 23 · Uncapped"
        elif token == "CONTENDERS":
            contender = True
            league_prefixes = list(CONTENDER_LEAGUES)
            name = "Contender"
            if hotstreak:
                label = "Pro · Contender (Hot Streak)"
            elif cap:
                label = f"Arena · Contender · Cap {cap}"
            else:
                label = "Arena · Contender · Uncapped"
        elif token:
            kind, value, name = resolve_league(token)
            if kind == "league":
                league_prefix = value
            else:
                country_code = value
            if hotstreak:
                label = f"Pro · {name} (Hot Streak)"
            elif cap:
                label = f"Arena · {name} · Cap {cap}"
            else:
                label = f"Arena · {name} · Uncapped"
        elif fmt == "SO7":
            label = f"Pro · {' / '.join(sorted(g['families']))}"
        elif cap:
            label = f"Arena · Cap {cap}"
        else:
            label = "Arena · Uncapped"
        comps.append({
            "rarity": rar, "label": label, "format": fmt_label, "mode": mode,
            "size": size, "cap": cap, "teams_cap": g["teams_cap"],
            "league_prefix": league_prefix, "country_code": country_code,
            "league_prefixes": league_prefixes, "contender": contender,
            "max_age": max_age, "in_season": in_season,
            "hotstreak": hotstreak, "max_classic": 1 if hotstreak else None,
        })
    return comps


def fetch_cards(slug, rarities):
    cards, after = [], None
    while True:
        conn = graphql(CARDS_QUERY, {"slug": slug, "after": after, "rarities": rarities})
        conn = conn["data"]["user"]["cards"]
        cards.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
        time.sleep(PACE)
    # Sealed cards (in the vault/tresor) can't be fielded -> drop them here.
    sealed = [c for c in cards if c.get("sealed")]
    if sealed:
        print(f"Skipping {len(sealed)} sealed (vault) card(s): "
              + ", ".join(sorted({(c.get('anyPlayer') or {}).get('displayName', c['slug']) for c in sealed})),
              file=sys.stderr)
    return [c for c in cards if not c.get("sealed")]


def fetch_players(slugs):
    out, slugs, i, batch = {}, list(slugs), 0, PLAYER_BATCH
    while i < len(slugs):
        chunk = slugs[i:i + batch]
        slug_list = ", ".join(f'"{s}"' for s in chunk)
        resp = graphql("{ players(slugs: [" + slug_list + "]) {" + PLAYER_FIELDS + "} }")
        data = resp.get("data")
        if not data:
            if batch > 4:
                batch = max(4, batch // 2)
                continue
            sys.exit(f"Player fetch failed: {resp.get('errors')}")
        for p in (data.get("players") or []):
            if p and p.get("slug"):
                out[p["slug"]] = p
        i += len(chunk)
        print(f"  ...players {min(i, len(slugs))}/{len(slugs)}", file=sys.stderr)
        time.sleep(PACE)
    return out


# --- Startelf prediction (start-probability) score ------------------------
# Blends Sorare's own signals into P(player starts the upcoming game):
#   1. recent minutes per game (the strongest signal: did they actually start
#      and stay on?), recency-weighted over the last GAMES_BACK games
#   2. season availability (last-15 SO5 appearance rate)
#   3. injury feed with expected return date, cross-checked against (1) so a
#      stale injury record on a player who just played 90' doesn't over-punish
# External predicted-lineup/news sources are network-blocked (only
# api.sorare.com is reachable), so this is derived purely from Sorare data.
RECENCY_W = [1.0, 0.82, 0.66, 0.52, 0.4, 0.3]   # most-recent game first


def _recent_minutes(pd):
    """List of minutes played in the last games, most recent first."""
    out = []
    for g in (pd.get("playerGameScores") or []):
        mp = None
        for s in (g.get("detailedScore") or []):
            if s.get("stat") == "mins_played":
                mp = s.get("statValue")
                break
        dte = ((g.get("anyGame") or {}).get("date") or "")[:10]
        out.append((dte, mp))
    # Sorare returns playerGameScores MOST-RECENT-FIRST (verified: index 0 is the
    # newest game) -> the list is already in the order RECENCY_W expects.
    return out


def _mins_to_start(mp):
    """Per-game start indicator from minutes played."""
    if mp is None:
        return None
    if mp >= 60:
        return 1.0      # started and stayed on
    if mp >= 30:
        return 0.55     # rotation / early sub or sub-on with real minutes
    if mp > 0:
        return 0.2      # cameo off the bench
    return 0.0          # unused / not in squad


def start_probability(pd, we):
    """Return (prob in [0,1], recent_minutes list). we = gameweek end datetime."""
    mins = _recent_minutes(pd)
    # 1) recency-weighted minutes signal
    num = den = 0.0
    for i, (_, mp) in enumerate(mins[:len(RECENCY_W)]):
        si = _mins_to_start(mp)
        if si is None:
            continue
        w = RECENCY_W[i]
        num += w * si
        den += w
    min_signal = (num / den) if den else None
    # 2) season availability
    app = pd.get("lastFifteenSo5Appearances") or 0
    app_rate = min(1.0, app / 15.0)
    # blend (fall back to availability when no recent games are on record)
    if min_signal is None:
        base = app_rate * 0.85
    else:
        base = 0.70 * min_signal + 0.30 * app_rate
    # 3) injury adjustment, validated against recent minutes
    factor = 1.0
    for inj in (pd.get("activeInjuries") or []):
        if inj.get("active") is False:
            continue
        end = inj.get("expectedEndDate")
        out_through_gw = True
        if end:
            try:
                ed = dt.datetime.fromisoformat(end.replace("Z", "+00:00"))
                out_through_gw = ed >= we
            except Exception:
                out_through_gw = True
        # if they logged real minutes in the most recent game, the record is
        # likely stale/minor -> soft penalty; otherwise treat as (near-)out.
        just_played = bool(mins) and (mins[0][1] or 0) >= 60
        if out_through_gw and not just_played:
            factor = min(factor, 0.05)
        else:
            factor = min(factor, 0.5)
    prob = base * factor
    # mild recalibration toward the base rate (backtest-tuned, de-biases extremes)
    prob = (1 - START_RECAL_K) * prob + START_RECAL_K * BASE_START_RATE
    return max(0.0, min(0.98, round(prob, 3))), mins


def played_projection(pd):
    """Expected SO5 score GIVEN the player plays: a blend of his last-5 and
    last-15 scores over games he ACTUALLY PLAYED (minutes > 0).

    Rationale (validated by backtest.py on 1k+ games): the raw L5 average mixes
    in DNP / unused-sub games (score ~0), which dragged the projection ~10 pts
    below the true score-when-playing level (MAE 19 -> 14, bias -11 -> ~0). The
    start probability already accounts for availability, so the projection must
    be the clean 'if he plays' score, not a play-rate-discounted one."""
    played = []
    for g in (pd.get("playerGameScores") or []):   # API order = most-recent-first
        mp = None
        for s in (g.get("detailedScore") or []):
            if s.get("stat") == "mins_played":
                mp = s.get("statValue")
                break
        if (mp or 0) > 0 and g.get("score") is not None:
            played.append(g["score"])
    if not played:
        return None
    l5 = played[:5]
    l15 = played[:15]
    m5 = sum(l5) / len(l5)
    m15 = sum(l15) / len(l15)
    return 0.6 * m5 + 0.4 * m15


def national_bench_signal(pd, we):
    """True if the player's nation ALREADY played national-team game(s) in this
    international break (within NATIONAL_BENCH_DAYS before the GW end) and he
    logged 0 minutes in ALL of them -> an unused squad member, so his club-based
    start prob for the UPCOMING national game is meaningless (he most likely
    sits again). Automates the manual 'benched for his country' catch.

    Only fires for players whose nation has already featured this break; the
    first national game of a window gives no such signal (nothing to read yet).
    A researched start_override still wins (Nick may know he starts next)."""
    cutoff = we - dt.timedelta(days=NATIONAL_BENCH_DAYS)
    mins_seen = []
    for g in (pd.get("playerGameScores") or []):
        ag = g.get("anyGame") or {}
        d = ag.get("date")
        if not d:
            continue
        try:
            gd = dt.datetime.fromisoformat(d.replace("Z", "+00:00"))
        except Exception:
            continue
        if not (cutoff <= gd <= we):
            continue
        is_natl = ((ag.get("homeTeam") or {}).get("__typename") == "NationalTeam"
                   or (ag.get("awayTeam") or {}).get("__typename") == "NationalTeam")
        if not is_natl:
            continue
        mp = None
        for s in (g.get("detailedScore") or []):
            if s.get("stat") == "mins_played":
                mp = s.get("statValue")
                break
        mins_seen.append(mp or 0)
    return bool(mins_seen) and max(mins_seen) == 0


def suspension_signal(pd, opp_type):
    """True if the player's MOST RECENT game had a red card AND that game is the
    same competition stream (club vs national) as his upcoming game -> almost
    certainly banned for the next game of that stream. Uses the dated game log
    (red_card stat covers straight reds and second yellows). A researched
    override still wins (e.g. a rescinded red)."""
    games = pd.get("playerGameScores") or []
    if not games:
        return False
    last = games[0]                     # most-recent-first -> index 0 is newest
    red = 0
    for s in (last.get("detailedScore") or []):
        if s.get("stat") == "red_card":
            red = s.get("statValue") or 0
            break
    if red < 1:
        return False
    ag = last.get("anyGame") or {}
    last_type = "NationalTeam" if (
        (ag.get("homeTeam") or {}).get("__typename") == "NationalTeam"
        or (ag.get("awayTeam") or {}).get("__typename") == "NationalTeam") else "Club"
    # ban applies to the same stream; unknown upcoming type -> flag to be safe
    return opp_type is None or last_type == opp_type


# Sorare role labels (Player.playingStatus). Backtest-free sanity check on the
# squad (2026-09-29): the label agrees with the model almost everywhere (STARTER
# avg 0.83, NOT_PLAYING 0.13, SUBSTITUTE 0.31), so it is NOT used to move the
# probability -- only to flag the rare strong contradictions for a manual check.
_BENCH_STATUSES = ("NOT_PLAYING", "SUBSTITUTE", "RETIRED")
_AUTO_SRCS = ("callup_out", "intl_duty_auto", "natl_bench_auto", "natl_bench_soft",
              "suspension_risk")


def _status_conflict(e):
    """True if Sorare's role label strongly contradicts our final start prob."""
    ps, p = e.get("playing_status"), e.get("start_prob") or 0.0
    if ps in _BENCH_STATUSES and p >= 0.55:
        return True
    # a club STARTER we rate low for a known automatic reason is expected; and
    # the label describes his CLUB role, so it says nothing about a national XI
    if (ps == "STARTER" and p <= 0.35 and e.get("opp_type") != "NationalTeam"
            and e.get("start_src") not in _AUTO_SRCS):
        return True
    return False


def sorare_start_odds(pd):
    """Sorare's own starter/sub odds for the next Classic fixture (the "Sorare-%"
    shown in the app), as (p_start, p_sub, reliability) with probabilities in
    0..1 — or (None, None, None) when unavailable. NOTE: the public API returns
    null for these since 2026-09-14 (sorare/api issue #693); this hook switches
    on automatically as soon as Sorare fixes it."""
    o = pd.get("nextClassicFixturePlayingStatusOdds") or {}
    bp = o.get("starterOddsBasisPoints")
    if bp is None:
        return None, None, None
    sub = o.get("substituteOddsBasisPoints")
    return (max(0.0, min(1.0, bp / 10000.0)),
            None if sub is None else max(0.0, min(1.0, sub / 10000.0)),
            o.get("reliability"))


def apply_sofascore(entries, index):
    """Fuse SofaScore predicted/confirmed XIs into each entry's start_prob.
    Confirmed lineups override the model; predicted lineups blend with it.
    Returns (n_confirmed, n_predicted) for logging."""
    from sofascore_lineups import _norm
    n_conf = n_pred = 0
    for e in entries:
        info = index.get(e.get("club_name"))
        if not info or not info.get("players"):
            continue
        xi = info["players"]
        pn = _norm(e["player"])
        started = xi.get(pn)
        if started is None and e.get("player"):
            # last-name fallback, only if it maps to exactly one XI player
            ln = _norm(e["player"].split()[-1])
            if len(ln) >= 4:
                hits = [(nm, st) for nm, st in xi.items() if nm.endswith(ln) or ln in nm]
                if len(hits) == 1:
                    started = hits[0][1]
        conf = info.get("confirmed")
        if started is None:
            if conf:                      # teamsheet out and player not on it
                e["start_prob"] = min(e["start_prob"], 0.10)
                e["sofa_status"] = "confirmed_out"
                e["ev"] = round(e["proj"] * e["start_prob"], 1)
                n_conf += 1
            continue
        if conf:
            e["start_prob"] = 0.95 if started else 0.08
            e["sofa_status"] = "confirmed_start" if started else "confirmed_bench"
            n_conf += 1
        else:
            target = 0.85 if started else 0.18
            e["start_prob"] = round(0.35 * e["start_prob"] + 0.65 * target, 3)
            e["sofa_status"] = "pred_start" if started else "pred_bench"
            n_pred += 1
        e["ev"] = round(e["proj"] * e["start_prob"], 1)
    return n_conf, n_pred


def eligible_entry(card, pd, ws, we, fx_games=None):
    ng = pd.get("nextGame")
    if not ng or not ng.get("date"):
        return None
    try:
        gd = dt.datetime.fromisoformat(ng["date"].replace("Z", "+00:00"))
    except Exception:
        return None
    if gd < ws:            # next game still in the current GW -> look further
        ng = _game_in_window(pd, ng, ws, we, fx_games)
        if not ng:
            return None
        gd = dt.datetime.fromisoformat(ng["date"].replace("Z", "+00:00"))
    if not (ws <= gd <= we):
        return None
    l5, l15 = pd.get("l5"), pd.get("l15")
    if not l5:
        return None
    start_prob, recent_mins = start_probability(pd, we)
    s_start, s_sub, s_rel = sorare_start_odds(pd)
    if max(start_prob, s_start or 0.0) < 0.08:
        return None          # (near-)certain absentee: drop entirely
    app = pd.get("lastFifteenSo5Appearances") or 0
    club = (pd.get("activeClub") or {}).get("name")
    home_t = ng.get("homeTeam") or {}
    away_t = ng.get("awayTeam") or {}
    nat = (pd.get("country") or {}).get("code")

    def _is_mine(team):
        # Club game: match on club name. National game: match the player's
        # nationality code against the national team's country code (the club
        # name never matches a national team, which mis-assigned the opponent).
        if team.get("__typename") == "NationalTeam":
            return nat is not None and (team.get("country") or {}).get("code") == nat
        return club is not None and team.get("name") == club

    if _is_mine(home_t):
        is_home, opp_team, my_team = True, away_t, home_t
    elif _is_mine(away_t):
        is_home, opp_team, my_team = False, home_t, away_t
    else:
        is_home, opp_team, my_team = False, home_t, away_t  # unknown side -> assume away
    opponent = opp_team.get("name")
    opp_type = opp_team.get("__typename")   # "Club" or "NationalTeam"
    team_name = my_team.get("name")
    # Stable id for the fixture, side-independent: the two team names + kickoff.
    fixture = "|".join(sorted(x for x in (team_name, opponent) if x)) + "@" + ng["date"]
    # Expected score IF he plays: played-only blend (see played_projection);
    # fall back to the API L5 average when no per-game scores are on record.
    # No play-rate discount here — start_prob already carries availability.
    base_proj = played_projection(pd)
    if base_proj is None:
        base_proj = l5
    proj = round(base_proj * (1.03 if is_home else 1.0), 1)
    ev = round(proj * start_prob, 1)   # expected value = projection x P(start)
    club = pd.get("activeClub") or {}
    league = (club.get("domesticLeague") or {}).get("slug")
    country = (club.get("country") or {}).get("code")
    return {"slug": card["slug"], "player": card["anyPlayer"]["displayName"],
            "player_slug": card["anyPlayer"]["slug"], "season": card.get("seasonYear"),
            # Slot by the CARD's position (what Sorare enforces), not the
            # player's real-life position -- they can differ (e.g. a midfielder
            # on a Forward card). Fall back to the player position if absent.
            "positions": card.get("anyPositions") or card["anyPlayer"].get("anyPositions") or [],
            "age": pd.get("age"), "club_name": club.get("name"),
            "proj": proj, "ev": ev, "start_prob": start_prob, "sofa_status": None,
            "recent_mins": [mp for _, mp in recent_mins],
            "injured": bool(pd.get("activeInjuries")),
            "cap_score": round(l15 if l15 else l5, 1),
            "l5": round(l5, 1), "appearances": app, "league": league, "country": country,
            "home": is_home, "opponent": opponent,
            "opp_type": opp_type, "matchup": 1.0,
            "team_name": team_name, "fixture": fixture,
            "kickoff": ng["date"],
            # player's nationality code, for international call-up detection
            "nat_code": nat, "intl_duty": False, "suspended": False,
            # Sorare's own signals: coarse role label + app starter odds (null
            # in the API since 2026-09-14) -> used/checked in main()
            "model_prob": start_prob, "playing_status": pd.get("playingStatus"),
            "sorare_start": s_start, "sorare_sub": s_sub, "sorare_rel": s_rel}


def cands(pool, slot, blocked, min_start=0.0):
    # `blocked` holds BOTH card slugs and player slugs (distinct namespaces): a
    # card is skipped if its own slug is used OR another card of the same player
    # is already in this lineup -> never the same player twice in one team.
    if slot == "EXTRA":
        cs = [c for c in pool if c["slug"] not in blocked and c["player_slug"] not in blocked
              and any(p in POS_SLOTS[1:] for p in c["positions"])]  # non-GK
    else:
        cs = [c for c in pool if c["slug"] not in blocked and c["player_slug"] not in blocked
              and slot in c["positions"]]
    # Prefer players at/above the start-probability floor (safe starters),
    # then by expected value. Below-floor players stay as a fallback so a slot
    # is never left empty (an empty slot scores 0 — worse than a risky start).
    return sorted(cs, key=lambda c: (c.get("start_prob", 0) >= min_start,
                                     c.get("ev", c["proj"])), reverse=True)


def _role(slot, entry):
    """Coarse role for the same-fixture conflict rule."""
    if slot in ("Goalkeeper", "Defender"):
        return "def"
    if slot == "Forward":
        return "att"
    if slot == "Midfielder":
        return "mid"
    pos = entry.get("positions") or []          # EXTRA: infer from the player
    if "Forward" in pos:
        return "att"
    if "Defender" in pos or "Goalkeeper" in pos:
        return "def"
    return "mid"


def _fixture_conflict(slot, cand, chosen, slot_list):
    """True if `cand` would face an already-picked team-mate-of-the-lineup from
    the opposite side of the SAME match in a defence-vs-attack pairing (e.g. our
    keeper/defender vs the opponent's forward). Those points partly cancel, so
    we avoid stacking both sides of one game as GK/DEF against FWD."""
    r = _role(slot, cand)
    if r == "mid":
        return False
    for cidx, other in chosen.items():
        if (other.get("fixture") == cand.get("fixture")
                and other.get("team_name") != cand.get("team_name")
                and {r, _role(slot_list[cidx], other)} == {"def", "att"}):
            return True
    return False


def build_team(pool, used, size, cap, max_classic=None, min_start=0.0):
    def _ev(c):
        return c.get("ev", c["proj"])
    slot_list = formation_for(size)
    chosen = {}          # slot index -> card
    blocked = set(used)
    classic_used = 0
    for idx, slot in enumerate(slot_list):
        cs = cands(pool, slot, blocked, min_start)
        if not cs:
            continue

        def _ok(c):
            # Avoid a same-fixture defence-vs-attack clash, and respect the Hot
            # Streak classic cap already during the greedy fill so in-season
            # players get placed in the slots only they can fill (a scarce
            # in-season pool otherwise loses a slot to a classic).
            if _fixture_conflict(slot, c, chosen, slot_list):
                return False
            if (max_classic is not None and c.get("is_classic")
                    and classic_used >= max_classic):
                return False
            return True

        pick = next((c for c in cs if _ok(c)), cs[0])
        chosen[idx] = pick
        blocked.add(pick["slug"]); blocked.add(pick["player_slug"])
        if pick.get("is_classic"):
            classic_used += 1
    if max_classic is not None:
        # Hot Streak: keep at most `max_classic` classic (non-in-season) cards.
        guard = 0
        while sum(1 for c in chosen.values() if c.get("is_classic")) > max_classic and guard < 400:
            guard += 1
            best = None  # replace a classic card with the least-loss in-season alt
            for idx, cur in chosen.items():
                if not cur.get("is_classic"):
                    continue
                others = blocked - {cur["slug"], cur["player_slug"]}
                for alt in cands(pool, slot_list[idx], others, min_start):
                    if alt.get("is_classic"):
                        continue
                    loss = _ev(cur) - _ev(alt)
                    if best is None or loss < best[0]:
                        best = (loss, idx, alt)
            if not best:
                break
            _, idx, alt = best
            blocked.discard(chosen[idx]["slug"]); blocked.discard(chosen[idx]["player_slug"])
            chosen[idx] = alt
            blocked.add(alt["slug"]); blocked.add(alt["player_slug"])
    if cap is not None:
        guard = 0
        while sum(c["cap_score"] for c in chosen.values()) > cap and guard < 400:
            guard += 1
            best = None
            for idx, cur in chosen.items():
                slot = slot_list[idx]
                others = blocked - {cur["slug"], cur["player_slug"]}
                for alt in cands(pool, slot, others, min_start):
                    saved = cur["cap_score"] - alt["cap_score"]
                    if saved <= 0:
                        continue
                    ratio = (_ev(cur) - _ev(alt)) / saved
                    if best is None or ratio < best[0]:
                        best = (ratio, idx, alt)
            if not best:
                break
            _, idx, alt = best
            blocked.discard(chosen[idx]["slug"]); blocked.discard(chosen[idx]["player_slug"])
            chosen[idx] = alt
            blocked.add(alt["slug"]); blocked.add(alt["player_slug"])
    cards = []
    for idx, slot in enumerate(slot_list):
        if idx in chosen:
            c = dict(chosen[idx]); c["slot"] = slot
            cards.append(c)
    classic_n = sum(1 for c in cards if c.get("is_classic"))
    over_classic = max_classic is not None and classic_n > max_classic
    complete = len(cards) == size and not over_classic
    cap_used = round(sum(c["cap_score"] for c in cards), 1)
    if cards:
        cap_card = max(cards, key=_ev); cap_card["captain"] = True
        proj_total = round(sum(c["proj"] for c in cards) + cap_card["proj"], 1)
        exp_total = round(sum(_ev(c) for c in cards) + _ev(cap_card), 1)
        avg_start = round(sum(c.get("start_prob", 0) for c in cards) / len(cards), 3)
        min_start_seen = round(min(c.get("start_prob", 0) for c in cards), 3)
    else:
        proj_total = exp_total = avg_start = min_start_seen = 0
    return {"cards": cards, "complete": complete, "cap_used": cap_used,
            "over_cap": cap is not None and cap_used > cap,
            "projected_total": proj_total, "expected_total": exp_total,
            "avg_start": avg_start, "min_start": min_start_seen,
            "used": {c["slug"] for c in cards}}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--json", default="lineups.json")
    ap.add_argument("--rarities", default="limited,rare")
    ap.add_argument("--exclude", default="",
                    help="comma-separated player slugs or display names to drop "
                         "from the pool (injured/suspended players that Sorare's "
                         "own injury feed does not yet flag). Matched case- and "
                         "accent-insensitively against slug and display name.")
    ap.add_argument("--unavailable", default="unavailable.json",
                    help="JSON list of player_slugs whose CARD can't be fielded "
                         "right now (in the vault/tresor, listed for sale, etc.) "
                         "-- separate from injuries. Format: "
                         '{"slugs": ["xaver-schlager", ...]} or a plain [ ... ]. '
                         "These are dropped from the pool like --exclude.")
    ap.add_argument("--start-override", default="start_overrides.json",
                    help="JSON {player_slug: probability 0..1} to REPLACE the "
                         "model's club-based start probability. Use it for "
                         "national-team games, where club minutes don't predict "
                         "selection -- research the probable XI and set your own "
                         "number here. Missing file/slug -> keep the model value.")
    ap.add_argument("--strength", default="team_strength.json",
                    help="JSON with opponent strength ratings (0..1, higher = "
                         "stronger) to weight the projection by matchup. Format: "
                         '{"clubs": {"FC Porto": 0.9, ...}, '
                         '"nations": {"Germany": 0.95, ...}}. Missing file or '
                         "unknown opponent -> neutral (no matchup effect).")
    ap.add_argument("--matchup-weight", type=float, default=0.20,
                    help="how strongly the opponent's strength swings the "
                         "projection. factor = 1 + w*(0.5 - opp_strength); "
                         "0.20 => +/-10%% at the extremes. 0 disables it.")
    ap.add_argument("--manual-competitions", default="manual_competitions.json",
                    help="JSON of competitions the API doesn't expose, keyed by "
                         "fixture slug (apply only to that GW). See the file.")
    ap.add_argument("--international-callups", default="international_callups.json",
                    help="JSON of player_slugs on national duty, keyed by fixture "
                         "slug (apply only to that GW, auto-expire after). Listed "
                         "players are treated as ABSENT from any club game this GW "
                         "(start_prob 0 -> dropped). Use it for call-ups Sorare's "
                         "fixture doesn't carry (non-UEFA nations, whose national "
                         "games the API can't see); UEFA call-ups are detected "
                         "automatically from the fixture. A researched "
                         "start-override still wins over automatic detection.")
    ap.add_argument("--fixture", default=None,
                    help="build for a specific fixture slug or gameweek number "
                         "instead of the next one (e.g. football-25-29-sep-2026 "
                         "for the MLS Hot Streak round during an int'l break)")
    ap.add_argument("--calibration", default="calibration.json",
                    help="learned calibration from evaluate.py (Treffer-Bilanz): "
                         "per-source correction of the start probability + a "
                         "projection scale. Applied only once enough games were "
                         "evaluated ('active'). '' disables.")
    ap.add_argument("--no-injuries-feed", action="store_true",
                    help="skip the API-Football injury/suspension feed "
                         "(injuries_feed.py); it is used automatically when "
                         "v3.football.api-sports.io is reachable")
    ap.add_argument("--no-sorare-odds", action="store_true",
                    help="ignore Sorare's own starter odds even when the API "
                         "returns them (null since 2026-09-14, sorare/api #693)")
    ap.add_argument("--log", default="logs/predictions.jsonl",
                    help="append one JSON line per eligible player (model prob, "
                         "Sorare status/odds, final prob + source) for later "
                         "calibration against the real outcomes. COMMITTED on "
                         "purpose (Nick, 2026-09-29). '' disables -- use that "
                         "for tests/experiments so they don't pollute the log.")
    ap.add_argument("--sofascore", action="store_true",
                    help="opt in to SofaScore predicted-lineup enrichment "
                         "(needs api.sofascore.com allowed; SofaScore IP-blocks "
                         "datacenter egress, so this usually falls back)")
    args = ap.parse_args(argv)
    rarities = [r.strip() for r in args.rarities.split(",") if r.strip()]

    def _norm(s):
        # Case/accent-insensitive key so "Nico Schlotterbeck", "schlotterbeck"
        # and the slug all match the same excluded player.
        import unicodedata
        s = unicodedata.normalize("NFKD", (s or "").strip().lower())
        return "".join(ch for ch in s if not unicodedata.combining(ch))

    excluded = {_norm(x) for x in args.exclude.split(",") if x.strip()}

    # Cards not currently fieldable (vault/tresor, on sale, ...) -> drop them
    # from the pool exactly like --exclude. Read by default so the routines
    # respect it automatically.
    if os.path.exists(args.unavailable):
        try:
            with open(args.unavailable, encoding="utf-8") as fh:
                raw = json.load(fh)
            slugs = raw.get("slugs", []) if isinstance(raw, dict) else raw
            unavail = {_norm(s) for s in slugs if isinstance(s, str) and not s.startswith("_")}
            if unavail:
                excluded |= unavail
                print(f"Unavailable (not fieldable) from {args.unavailable}: "
                      f"{len(unavail)} cards.", file=sys.stderr)
        except (ValueError, OSError) as exc:
            print(f"WARNING: could not read --unavailable {args.unavailable}: {exc}",
                  file=sys.stderr)

    # Researched start-probability overrides (mainly national-team games).
    # Each override is BOUND to one gameweek (fixture slug) and carries the
    # date it was researched, so it expires with its GW instead of silently
    # leaking into the next one (the Froholdt case). File format:
    #   "_fixture": "<fixture-slug>"      default binding for plain numbers
    #   "_researched": "YYYY-MM-DD"       default research date
    #   "<player-slug>": 0.85             -> bound to _fixture/_researched
    #   "<player-slug>": {"p": 0.5, "fixture": "...", "researched": "...",
    #                     "src": "sorare_app"}
    # "src" names where the number comes from: "researched" (default, my own
    # research) or "sorare_app" (the Sorare-% Nick reads in the app -- at the
    # GW717 deadline it beat my research 4/4, so it gets its own source in the
    # log and the Treffer-Bilanz can measure it separately).
    # Overrides without any binding are ignored (with a warning).
    override_raw = {}
    if os.path.exists(args.start_override):
        try:
            with open(args.start_override, encoding="utf-8") as fh:
                raw = json.load(fh)
            d_fx = raw.get("_fixture")
            d_date = raw.get("_researched") or raw.get("_updated")
            for k, v in raw.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, dict):
                    override_raw[k] = {"p": float(v["p"]),
                                       "fixture": v.get("fixture", d_fx),
                                       "researched": v.get("researched", d_date),
                                       "src": v.get("src") or "researched"}
                else:
                    override_raw[k] = {"p": float(v), "fixture": d_fx,
                                       "researched": d_date, "src": "researched"}
        except (ValueError, OSError, KeyError, TypeError) as exc:
            print(f"WARNING: could not read --start-override "
                  f"{args.start_override}: {exc}", file=sys.stderr)

    # Opponent strength (0..1, higher = stronger) for matchup weighting.
    strength = {"clubs": {}, "nations": {}}
    if args.matchup_weight and os.path.exists(args.strength):
        try:
            with open(args.strength, encoding="utf-8") as fh:
                raw = json.load(fh)
            for bucket in ("clubs", "nations"):
                strength[bucket] = {_norm(k): float(v)
                                    for k, v in (raw.get(bucket) or {}).items()}
            print(f"Matchup weighting on (w={args.matchup_weight}) from "
                  f"{args.strength}: {len(strength['clubs'])} clubs, "
                  f"{len(strength['nations'])} nations.", file=sys.stderr)
        except (ValueError, OSError) as exc:
            print(f"WARNING: could not read --strength {args.strength}: {exc} "
                  "-> matchup weighting off.", file=sys.stderr)

    def apply_matchup(e):
        """Scale proj/ev by the opponent's strength. Neutral if unknown."""
        if not args.matchup_weight or not e.get("opponent"):
            return
        table = strength["nations"] if e.get("opp_type") == "NationalTeam" else strength["clubs"]
        s = table.get(_norm(e["opponent"]))
        if s is None:
            return                       # unknown opponent -> no change
        factor = 1.0 + args.matchup_weight * (0.5 - s)
        e["matchup"] = round(factor, 3)
        e["proj"] = round(e["proj"] * factor, 1)
        e["ev"] = round(e["proj"] * e["start_prob"], 1)

    fx = get_upcoming_fixture(args.fixture)
    # Sorare's odds describe the NEXT Classic fixture only -> ignore them when
    # building for an explicitly chosen (possibly later) fixture.
    use_sorare_odds = not args.no_sorare_odds and args.fixture is None

    # Learned calibration (evaluate.py): only used once it is 'active'.
    calib = None
    if args.calibration and os.path.exists(args.calibration):
        try:
            with open(args.calibration, encoding="utf-8") as fh:
                c = json.load(fh)
            if c.get("active"):
                calib = c
                bt = c.get("by_type") or {}
                on = [t for t, v in bt.items() if v.get("active")] if bt else ["alle"]
                print(f"Kalibrierung (aus {c.get('n')} ausgewerteten Spielen, Stand "
                      f"{str(c.get('_updated'))[:10]}): Startquoten "
                      f"{'korrigiert für ' + '/'.join(on) if on else 'unverändert (kein Out-of-sample-Gewinn)'}"
                      f"; Projektions-Faktor {(c.get('proj_scale') or {}).get('value', 1.0)}.",
                      file=sys.stderr)
            else:
                print(f"Kalibrierung noch inaktiv ({c.get('n')}/{c.get('min_n')} "
                      f"Spiele ausgewertet).", file=sys.stderr)
        except (ValueError, OSError) as exc:
            print(f"WARNING: could not read --calibration {args.calibration}: {exc}",
                  file=sys.stderr)

    def proj_group(e):
        pos = (e.get("positions") or ["?"])[0]
        return f"{pos}|{'national' if e.get('opp_type') == 'NationalTeam' else 'club'}"

    _EXTERNAL_SRCS = ("sorare_app", "sorare_odds")

    def _calibrate(e):
        """Apply the learned correction (evaluate.py) to the final start prob and
        the projection; keep the raw values for logging/learning. Calibration
        is per game type (national / club) and only where evaluate.py found it
        to help out of sample ('active')."""
        e["start_prob_raw"] = e["start_prob"]
        e["proj_raw"] = e["proj"]
        if not calib:
            return
        src = e.get("start_src") or "model"
        gtype = "national" if e.get("opp_type") == "NationalTeam" else "club"
        if src != "callup_out" and e["start_prob"] > 0:
            p = min(0.99, max(0.01, e["start_prob"]))
            x = math.log(p / (1 - p))
            z = None
            if "by_type" in calib:
                t = calib["by_type"].get(gtype) or {}
                if t.get("active"):
                    prm = (t.get("sources") or {}).get(src) or (
                        {"a": 0.0, "b": 1.0} if src in _EXTERNAL_SRCS else t.get("global") or {})
                    z = prm.get("a", 0.0) + prm.get("b", 1.0) * x
                    if src not in _EXTERNAL_SRCS:
                        z += ((t.get("status") or {}).get(e.get("playing_status") or "NONE")
                              or {}).get("d", 0.0)
            else:                       # legacy calibration.json (one fit for all)
                prm = (calib.get("sources") or {}).get(src) or calib.get("global") or {}
                z = prm.get("a", 0.0) + prm.get("b", 1.0) * x
            if z is not None:
                e["start_prob"] = round(1 / (1 + math.exp(-max(-30, min(30, z)))), 3)
        scale = (calib.get("proj_scale") or {}).get("value", 1.0)
        # finer factor per position x game type (e.g. defenders in national
        # games score less than their club form suggests), learned by evaluate.py
        grp = (calib.get("proj_scale_groups") or {}).get(proj_group(e))
        if grp:
            scale = grp.get("value", scale)
        e["proj"] = round(e["proj"] * scale, 1)

    # Keep only the overrides bound to THIS gameweek; the rest have expired.
    start_overrides = {k: o["p"] for k, o in override_raw.items()
                       if o["fixture"] == fx["slug"]}
    override_date = {k: override_raw[k]["researched"] for k in start_overrides}
    expired = sorted(k for k, o in override_raw.items()
                     if o["fixture"] and o["fixture"] != fx["slug"])
    unbound = sorted(k for k, o in override_raw.items() if not o["fixture"])
    if override_raw:
        print(f"Start-prob overrides from {args.start_override}: "
              f"{len(start_overrides)} aktiv für {fx['slug']}"
              + (f", {len(expired)} verfallen (andere GW)" if expired else "")
              + (f", {len(unbound)} ohne GW-Bindung ignoriert: {', '.join(unbound)}"
                 if unbound else ""), file=sys.stderr)

    ws = dt.datetime.fromisoformat(fx["startDate"].replace("Z", "+00:00"))
    we = dt.datetime.fromisoformat(fx["endDate"].replace("Z", "+00:00"))
    print(f"Upcoming GW {fx['gameWeek']} ({fx['slug']}) {ws.date()}–{we.date()}", file=sys.stderr)

    # API-Football injuries + suspensions (incl. yellow-card bans) for every day
    # of the window. Unreachable/unconfigured -> silently fall back.
    apif_rows = []
    if not args.no_injuries_feed:
        import injuries_feed
        try:
            apif_rows, apif_skipped = injuries_feed.fetch_window(ws, we)
            print(f"API-Football: {len(apif_rows)} Verletzungs-/Sperr-Meldungen "
                  f"im Fenster geladen.", file=sys.stderr)
            if apif_skipped:
                print(f"API-Football: Tage außerhalb des Plans übersprungen "
                      f"(Free-Plan = gestern bis morgen): {', '.join(apif_skipped)} "
                      f"-> diese Spiele ohne Feed, manuell prüfen.", file=sys.stderr)
        except injuries_feed.FeedUnavailable as exc:
            print(f"API-Football-Feed übersprungen ({exc}).", file=sys.stderr)

    # International-break awareness: for each nation, the datetime of its last
    # national-team game in this window. A player whose nation is still playing
    # when his CLUB game kicks off is on national duty and will miss it (Sorare
    # ~0%), while the club-minutes model would rate him a starter.
    nation_last_game = fetch_nation_last_games(fx["slug"])
    fx_games = fetch_fixture_games(fx["slug"])
    intl_break = bool(nation_last_game)
    if intl_break:
        print(f"Länderspiel-Fenster erkannt: {len(nation_last_game)} Nationen "
              f"mit Spiel im Fenster.", file=sys.stderr)

    # Manually declared international call-ups (player_slugs on national duty),
    # keyed by fixture slug so they auto-expire after the GW. For call-ups the
    # Sorare fixture doesn't carry (non-UEFA nations). Listed players are treated
    # as ABSENT from any club game this GW (start_prob 0 -> dropped).
    manual_callups = set()
    if os.path.exists(args.international_callups):
        try:
            with open(args.international_callups, encoding="utf-8") as fh:
                raw = json.load(fh)
            for s in (raw.get(fx["slug"]) or []):
                if isinstance(s, str) and not s.startswith("_"):
                    manual_callups.add(_norm(s))
            if manual_callups:
                print(f"Manuelle Nominierungen (national) für {fx['slug']}: "
                      f"{len(manual_callups)} Spieler.", file=sys.stderr)
        except (ValueError, OSError) as exc:
            print(f"WARNING: could not read --international-callups "
                  f"{args.international_callups}: {exc}", file=sys.stderr)

    comps = fetch_competitions(fx["slug"], rarities)
    # Manually declared competitions the API doesn't expose (e.g. an int'l-break
    # "European Nations" Hot Streak). Keyed by fixture slug, so they apply ONLY
    # to that gameweek and go stale automatically afterwards.
    if os.path.exists(args.manual_competitions):
        try:
            with open(args.manual_competitions, encoding="utf-8") as fh:
                mc = json.load(fh)
            for m in (mc.get(fx["slug"]) or []):
                if m.get("rarity") not in rarities:
                    continue
                comps.append({
                    "rarity": m["rarity"], "label": m.get("label", "Manual"),
                    "format": m.get("format", "Hot Streak"),
                    "mode": m.get("mode", "Pro"), "size": m.get("size", 5),
                    "cap": m.get("cap"), "teams_cap": m.get("teams_cap", 1),
                    "league_prefix": None, "country_code": None,
                    "league_prefixes": None, "contender": False, "max_age": None,
                    "in_season": True, "hotstreak": m.get("hotstreak", True),
                    "max_classic": m.get("max_classic", 1),
                    "national_confederation": m.get("national_confederation"),
                    "manual": True,
                })
                print(f"  + manueller Wettbewerb: {m.get('label')}", file=sys.stderr)
        except (ValueError, OSError) as exc:
            print(f"WARNING: manual_competitions.json: {exc}", file=sys.stderr)
    print(f"{len(comps)} competitions to build.", file=sys.stderr)

    cards = fetch_cards(args.slug, rarities)
    print(f"Fetched {len(cards)} cards.", file=sys.stderr)
    current_season = max((c.get("seasonYear") or 0 for c in cards), default=0)
    print(f"Current season = {current_season}", file=sys.stderr)
    slugs = {c["anyPlayer"]["slug"] for c in cards if c.get("anyPlayer")}
    print(f"Fetching form/cap/next-game for {len(slugs)} players...", file=sys.stderr)
    players = fetch_players(slugs)

    # eligible pool per rarity: keep EVERY eligible card. A player may own
    # several cards (e.g. classic + in-season) and each is separately fieldable
    # in a DIFFERENT competition. "No card twice" (global) and "no player twice
    # in one lineup/competition" are enforced later in build_team / the comp loop.
    pools = {}
    scored = []           # every rated entry incl. ones dropped below -> for the log
    dropped = set()
    matched_keys = set()
    for rar in rarities:
        entries = []
        for c in cards:
            if c["rarityTyped"] != rar or not c.get("anyPlayer"):
                continue
            ap_ = c["anyPlayer"]
            if excluded:
                keys = {_norm(ap_.get("slug")), _norm(ap_.get("displayName"))} & excluded
                if keys:
                    dropped.add(ap_.get("displayName") or ap_.get("slug"))
                    matched_keys.update(keys)
                    continue
            pd = players.get(ap_["slug"])
            if not pd:
                continue
            e = eligible_entry(c, pd, ws, we, fx_games)
            if not e:
                continue
            entries.append(e)
        for e in entries:
            e["is_classic"] = (e.get("season") or 0) < current_season
            ov = start_overrides.get(e["player_slug"])
            on_club = (e.get("opp_type") == "Club")
            inj = (injuries_feed.lookup(apif_rows, e["player"], e.get("team_name"),
                                        e.get("kickoff")) if apif_rows else None)
            if inj:
                e["apif"] = f"{inj['type']}: {inj['reason']}"
            # Precedence: (1) a declared call-up is an authoritative absence from
            # the club game; (2) a researched override wins over everything else
            # (Nick may have CONFIRMED the player does start his club game); (3)
            # otherwise auto-detect national duty (nation plays this window AND
            # this is a club game) and downweight + flag for a Sorare-% check.
            if on_club and _norm(e["player_slug"]) in manual_callups:
                e["start_prob"] = 0.0
                e["start_src"] = "callup_out"
                e["intl_duty"] = True
            elif ov is not None:
                e["start_prob"] = round(max(0.0, min(1.0, ov)), 3)
                e["start_src"] = override_raw[e["player_slug"]]["src"]
                # stale if he has played again SINCE the override was researched
                last = ((((players.get(e["player_slug"]) or {}).get("playerGameScores")
                          or [{}])[0].get("anyGame") or {}).get("date") or "")[:10]
                e["override_stale"] = bool(last and override_date.get(e["player_slug"])
                                           and last > override_date[e["player_slug"]])
            elif use_sorare_odds and e.get("sorare_start") is not None:
                # Sorare's own starter odds (the app's %): news-aggregated and
                # fresher than any of our automatic signals -> they win over
                # them, but not over a researched override (Nick's verified call)
                e["start_prob"] = round(e["sorare_start"], 3)
                e["start_src"] = "sorare_odds"
            elif inj and inj["type"] == "Missing Fixture":
                # listed OUT for this very game (injury or suspension incl.
                # yellow-card bans, which our own red-card check can't see)
                e["start_prob"] = round(e["start_prob"] * APIF_MISSING_FACTOR, 3)
                e["start_src"] = "apif_out"
                e["suspended"] = injuries_feed.is_suspension(inj)
                e["intl_duty"] = injuries_feed.is_intl_duty(inj)
            elif inj and inj["type"] == "Questionable":
                e["start_prob"] = round(e["start_prob"] * APIF_DOUBT_FACTOR, 3)
                e["start_src"] = "apif_doubtful"
            elif suspension_signal(players.get(e["player_slug"]) or {}, e.get("opp_type")):
                # red card in his last game of this stream -> banned next game
                e["start_prob"] = round(e["start_prob"] * SUSPENSION_FACTOR, 3)
                e["start_src"] = "suspension_risk"
                e["suspended"] = True
            elif on_club and _on_national_duty(e, nation_last_game):
                e["start_prob"] = round(e["start_prob"] * INTL_DUTY_FACTOR, 3)
                e["start_src"] = "intl_duty_auto"
                e["intl_duty"] = True
            elif (e.get("opp_type") == "NationalTeam"
                  and national_bench_signal(players.get(e["player_slug"]) or {}, we)):
                # unused in his nation's already-played break game(s) -> most
                # likely sits again; club-minutes prob is meaningless here.
                e["start_prob"] = round(e["start_prob"] * NATIONAL_BENCH_FACTOR, 3)
                e["start_src"] = "natl_bench_soft"
                e["intl_duty"] = True
            _calibrate(e)
            e["ev"] = round(e["proj"] * e["start_prob"], 1)
            apply_matchup(e)
            e["status_conflict"] = _status_conflict(e)
            # A club's no. 1 is often only the backup for his country: in
            # national games the club model put keepers at 76% vs 25% real
            # (Bilanz 04.10.2026: Simon, Kovar ...) -> flag for a check.
            e["gk_check"] = (e.get("opp_type") == "NationalTeam"
                             and (e.get("positions") or [None])[0] == "Goalkeeper"
                             and (e.get("start_src") or "model") == "model")
        # Drop (near-)certain non-starters AFTER overrides too: a researched
        # 0% (e.g. suspended) player or a declared call-up must never be
        # fielded, even as a fallback.
        pools[rar] = [e for e in entries if e["start_prob"] >= 0.10]
        scored.extend(entries)
        flagged = sorted({e["player"] for e in entries if e.get("intl_duty")
                          and e["start_prob"] >= 0.10})
        if flagged:
            print(f"  {rar}: Länderspiel-Verdacht (Klubspiel im Fenster, "
                  f"Sorare-% prüfen): {', '.join(flagged)}", file=sys.stderr)
        apif = sorted({f"{e['player']} ({e['apif']})" for e in entries if e.get("apif")})
        if apif:
            print(f"  {rar}: API-Football meldet (prüfen): {', '.join(apif)}",
                  file=sys.stderr)
        susp = sorted({e["player"] for e in entries if e.get("suspended")})
        if susp:
            print(f"  {rar}: Sperren-Verdacht (Rot im letzten Spiel, prüfen): "
                  f"{', '.join(susp)}", file=sys.stderr)
        stale = sorted({f"{e['player']} (recherchiert "
                        f"{override_date.get(e['player_slug'])})"
                        for e in entries if e.get("override_stale")})
        if stale:
            print(f"  {rar}: Override älter als letztes Spiel (neu prüfen): "
                  f"{', '.join(stale)}", file=sys.stderr)
        conf = sorted({f"{e['player']} ({e['playing_status']}, "
                       f"{int(round(e['start_prob'] * 100))}% {e.get('start_src') or 'model'})"
                       for e in pools[rar] if e.get("status_conflict")})
        if conf:
            print(f"  {rar}: Sorare-Status widerspricht Startquote (prüfen): "
                  f"{', '.join(conf)}", file=sys.stderr)
        gks = sorted({f"{e['player']} ({int(round(e['start_prob'] * 100))}%)"
                      for e in pools[rar] if e.get("gk_check")})
        if gks:
            print(f"  {rar}: Torwart im Länderspiel nur mit Modell-Quote "
                  f"(Nummer 1 prüfen / App-%): {', '.join(gks)}", file=sys.stderr)
        print(f"  {rar}: {len(pools[rar])} eligible players", file=sys.stderr)
    if excluded:
        if dropped:
            print(f"Excluded from pool: {', '.join(sorted(dropped))}", file=sys.stderr)
        unmatched = excluded - matched_keys
        if unmatched:
            print(f"WARNING: --exclude values matched no eligible card: "
                  f"{', '.join(sorted(unmatched))} (typo? or player has no game "
                  f"this GW anyway)", file=sys.stderr)

    # --- SofaScore predicted/confirmed XI enrichment (optional) ------------
    sofa_used = False
    all_pool_entries = [e for rar in rarities for e in pools.get(rar, [])]
    if args.sofascore and all_pool_entries:
        try:
            import sofascore_lineups as sofa
            if sofa.ping():
                clubs = {e.get("club_name") for e in all_pool_entries if e.get("club_name")}
                print(f"SofaScore: resolving XIs for {len(clubs)} clubs...", file=sys.stderr)
                index = sofa.build_club_index(clubs)
                nc, npd = apply_sofascore(all_pool_entries, index)
                sofa_used = True
                print(f"SofaScore applied: {nc} confirmed, {npd} predicted signals",
                      file=sys.stderr)
            else:
                print("SofaScore not reachable — falling back to Sorare-only model "
                      "(allow api.sofascore.com in the network policy).", file=sys.stderr)
        except Exception as e:
            print(f"SofaScore enrichment skipped: {type(e).__name__}: {str(e)[:160]}",
                  file=sys.stderr)

    out = {"fixture": {"slug": fx["slug"], "gameWeek": fx["gameWeek"],
                       "start": fx["startDate"], "end": fx["endDate"]},
           "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
           "international_break": intl_break,
           "eligible": {r: len(pools.get(r, [])) for r in rarities},
           "competitions": []}

    def comp_pool(comp, available):
        # league filter only; the in-season/classic rule is enforced per format
        # (Hot Streak allows at most 1 classic; Arena allows all seasons).
        pool = [e for e in available if e["rarity_"] == comp["rarity"]]
        conf = comp.get("national_confederation")
        if conf:                                   # national-team competition
            pool = [e for e in pool if e.get("opp_type") == "NationalTeam"
                    and (conf != "europe" or _norm(e.get("team_name")) in UEFA_NATIONS)]
        lps = comp.get("league_prefixes")
        if lps:
            pool = [e for e in pool
                    if any((e.get("league") or "").startswith(p) for p in lps)]
        elif comp.get("league_prefix"):
            pref = comp["league_prefix"]
            pool = [e for e in pool if (e.get("league") or "").startswith(pref)]
        elif comp.get("country_code"):
            cc = comp["country_code"]
            pool = [e for e in pool if e.get("country") == cc]
        if comp.get("max_age"):
            ma = comp["max_age"]
            pool = [e for e in pool if e.get("age") is not None and e["age"] <= ma]
        return pool

    # tag rarity on entries so a single global "used" set works across rarities
    for rar in rarities:
        for e in pools.get(rar, []):
            e["rarity_"] = rar

    def window(teams):
        ko = [c["kickoff"] for t in teams for c in t["cards"] if c.get("kickoff")]
        return (min(ko), max(ko)) if ko else (None, None)

    all_entries = sum(pools.values(), [])

    def build_pool(comp, avail):
        # Contender Hot Streak: 4 in-season Contender-league cards + 1 classic
        # from ANY league (blog rule), so widen the pool with all classics.
        if comp.get("contender") and comp.get("hotstreak"):
            ins = [e for e in comp_pool(comp, avail) if not e.get("is_classic")]
            classics = [e for e in avail if e.get("is_classic")
                        and e["rarity_"] == comp["rarity"]]
            return ins + classics
        return comp_pool(comp, avail)

    def enough_pool(comp):
        pool = comp_pool(comp, all_entries)
        if comp.get("hotstreak"):
            # a legal 5-card hot streak needs >=4 in-season (+ up to 1 classic)
            return sum(1 for e in pool if not e.get("is_classic")) >= 4
        if comp.get("max_age"):
            return len(pool) >= comp["size"]
        if comp.get("league_prefix") or comp.get("country_code") or comp.get("league_prefixes"):
            return len(pool) >= 4
        return True

    # ---- max-profit priority: each card used only once (global) ----
    # Pass A: standalone strength of each competition's best single team.
    for comp in comps:
        base = build_team(build_pool(comp, all_entries), set(),
                          comp["size"], comp["cap"], comp.get("max_classic"))
        comp["prize_weight"] = prize_weight(comp)
        # expected reward proxy = expected lineup value (form x P(start)) x pool
        comp["_priority"] = base["expected_total"] * comp["prize_weight"]
    hs_overview = []
    for comp in comps:
        if comp.get("hotstreak"):
            n_ins = sum(1 for e in comp_pool(comp, all_entries) if not e.get("is_classic"))
            if n_ins >= 1:
                hs_overview.append({"rarity": comp["rarity"], "label": comp["label"],
                                    "in_season": n_ins, "needed": 4,
                                    "fieldable": n_ins >= 4})
    out["hotstreak_overview"] = sorted(hs_overview, key=lambda x: -x["in_season"])
    comps = [c for c in comps if enough_pool(c)]
    # Always fill In-Season Hot Streaks first (best cards), then the rest by
    # projected strength. Within each tier, strongest lineup first.
    comps.sort(key=lambda c: (0 if c.get("hotstreak") else 1, -c["_priority"]))

    # Pass B: fill in priority order from the shrinking global pool.
    # Balanced risk policy: the first (best) team of each competition may only
    # field near-certain starters; each further team relaxes the floor so the
    # weaker teams can take upside punts.
    START_FLOORS = [0.75, 0.55, 0.40, 0.25]
    used_global = set()
    for comp in comps:
        teams = []
        # Single-use pool across ALL competitions (incl. manual/API-invisible
        # ones): on this account each CARD may be fielded only ONCE per gameweek,
        # so every comp draws from and consumes the shrinking global card pool.
        # A PLAYER may still appear via a DIFFERENT card in another competition,
        # but never twice inside one competition (comp_players guards that).
        used_local = set(used_global)     # card slugs used across all comps
        comp_players = set()              # player slugs used within THIS comp
        for ti in range(comp["teams_cap"]):
            floor = START_FLOORS[min(ti, len(START_FLOORS) - 1)]
            avail = [e for e in pools[comp["rarity"]] if e["slug"] not in used_local]
            pool = build_pool(comp, avail)
            t = build_team(pool, set(comp_players), comp["size"], comp["cap"],
                           comp.get("max_classic"), min_start=floor)
            t["risk_floor"] = floor
            if not t["cards"]:
                break
            if not t["complete"] and teams:
                break  # only keep a partial team as the first entry
            teams.append(t)
            used_local |= t["used"]
            comp_players |= {c["player_slug"] for c in t["cards"]}
            if not t["complete"]:
                break
        for t in teams:
            t.pop("used", None)
            if comp.get("hotstreak"):
                for c in t["cards"]:
                    if c.get("is_classic"):
                        c["classic"] = True
        if not teams:
            continue
        used_global = used_local         # every comp consumes the single-use pool
        w0, w1 = window(teams)
        out["competitions"].append({**{k: comp[k] for k in
                                    ("rarity", "label", "format", "mode", "size", "cap", "teams_cap")},
                                    "in_season": comp.get("in_season", False),
                                    "prize_weight": comp.get("prize_weight"),
                                    "deadline_first": w0, "deadline_last": w1,
                                    "teams": teams})
        tt = ", ".join(f"Σ{t['projected_total']}(EV{t['expected_total']}/{int(t['avg_start']*100)}%)"
                       for t in teams) or "—"
        print(f"  {comp['rarity']} · {comp['label']} [{comp['mode']}] "
              f"teams={len(teams)}/{comp['teams_cap']}: {tt}", file=sys.stderr)

    out["sofascore"] = sofa_used
    out["cards_used"] = len(used_global)
    out["total_projected"] = round(
        sum(t["projected_total"] for c in out["competitions"] for t in c["teams"]), 1)
    out["total_expected"] = round(
        sum(t["expected_total"] for c in out["competitions"] for t in c["teams"]), 1)
    print(f"Total projected {out['total_projected']} (EV {out['total_expected']}) "
          f"across {out['cards_used']} cards", file=sys.stderr)

    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {args.json}", file=sys.stderr)

    # Prediction log for later calibration (one line per player & upcoming game):
    # what the model said, what Sorare said, what we finally used and why.
    if args.log:
        n_odds = 0
        seen = set()
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
        with open(args.log, "a", encoding="utf-8") as fh:
            for e in scored:
                key = (e["player_slug"], e.get("kickoff"))
                if key in seen:
                    continue
                seen.add(key)
                n_odds += e.get("sorare_start") is not None
                fh.write(json.dumps({
                    "ts": ts, "fixture": fx["slug"], "player_slug": e["player_slug"],
                    "kickoff": e.get("kickoff"), "opp_type": e.get("opp_type"),
                    "opponent": e.get("opponent"), "model_prob": e.get("model_prob"),
                    "playing_status": e.get("playing_status"),
                    "sorare_start": e.get("sorare_start"), "sorare_sub": e.get("sorare_sub"),
                    "sorare_rel": e.get("sorare_rel"), "start_prob": e.get("start_prob"),
                    "start_prob_raw": e.get("start_prob_raw"),
                    "start_src": e.get("start_src") or "model", "proj": e.get("proj"),
                    "proj_raw": e.get("proj_raw"),
                    "pos": (e.get("positions") or [None])[0],
                    "apif": e.get("apif"),
                }, ensure_ascii=False) + "\n")
        print(f"Logged {len(seen)} predictions to {args.log} "
              f"(Sorare-Startquoten verfügbar: {n_odds})", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
