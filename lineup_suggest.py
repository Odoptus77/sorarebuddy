#!/usr/bin/env python3
"""Suggest the best Sorare setup for the upcoming gameweek, per competition.

Public data only (no OAuth). Reads the gameweek's competition structure and
builds the best lineup(s) for each general competition, respecting:
  - format: Classic = SO7 (7 cards), Arena = SO5 (5 cards)
  - the SO5/SO7 formation (GK, DEF, MID, FWD, + Extra(s))
  - the cap (Arena only): sum of the cards' L15 average score <= cap
  - teamsCap: up to N teams per competition, each using DISTINCT cards
maximising projected score (recent form x appearance rate x home edge),
excluding injured players and players without a game in the gameweek.

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
import os
import re
import sys
import time

from sorare_client import graphql

CARD_PAGE = 50
PLAYER_BATCH = 10   # detailedScore (minutes) per game inflates query complexity
GAMES_BACK = 5      # recent games used for the Startelf (start-probability) score
PACE = 0.25
POS_SLOTS = ["Goalkeeper", "Defender", "Midfielder", "Forward"]
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
      nodes { slug rarityTyped seasonYear
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
  playerGameScores(last: %d) { anyGame { date } detailedScore { stat statValue } }
  l5: averageScore(type: LAST_FIVE_SO5_AVERAGE_SCORE)
  l15: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
""" % GAMES_BACK


def rarity_of(t):
    for rar, tok in RARITY_TOKENS:
        if tok in t:
            return rar
    return None


def get_upcoming_fixture():
    q = "{ so5 { so5Fixtures(first: 8) { nodes { slug gameWeek aasmState startDate endDate } } } }"
    nodes = graphql(q)["data"]["so5"]["so5Fixtures"]["nodes"]
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
    return cards


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
    # Sorare returns oldest->newest for last:N; flip to most-recent first.
    out.reverse()
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
    return max(0.0, min(0.98, round(prob, 3))), mins


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


def eligible_entry(card, pd, ws, we):
    ng = pd.get("nextGame")
    if not ng or not ng.get("date"):
        return None
    try:
        gd = dt.datetime.fromisoformat(ng["date"].replace("Z", "+00:00"))
    except Exception:
        return None
    if not (ws <= gd <= we):
        return None
    l5, l15 = pd.get("l5"), pd.get("l15")
    if not l5:
        return None
    start_prob, recent_mins = start_probability(pd, we)
    if start_prob < 0.08:
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
        is_home, opp_team = True, away_t
    elif _is_mine(away_t):
        is_home, opp_team = False, home_t
    else:
        is_home, opp_team = False, home_t   # unknown side -> assume away
    opponent = opp_team.get("name")
    opp_type = opp_team.get("__typename")   # "Club" or "NationalTeam"
    proj = round(l5 * (0.75 + 0.25 * min(1.0, app / 15.0)) * (1.03 if is_home else 1.0), 1)
    ev = round(proj * start_prob, 1)   # expected value = projection x P(start)
    club = pd.get("activeClub") or {}
    league = (club.get("domesticLeague") or {}).get("slug")
    country = (club.get("country") or {}).get("code")
    return {"slug": card["slug"], "player": card["anyPlayer"]["displayName"],
            "player_slug": card["anyPlayer"]["slug"], "season": card.get("seasonYear"),
            "positions": card["anyPlayer"].get("anyPositions") or [],
            "age": pd.get("age"), "club_name": club.get("name"),
            "proj": proj, "ev": ev, "start_prob": start_prob, "sofa_status": None,
            "recent_mins": [mp for _, mp in recent_mins],
            "injured": bool(pd.get("activeInjuries")),
            "cap_score": round(l15 if l15 else l5, 1),
            "l5": round(l5, 1), "appearances": app, "league": league, "country": country,
            "home": is_home, "opponent": opponent,
            "opp_type": opp_type, "matchup": 1.0,
            "kickoff": ng["date"]}


def cands(pool, slot, blocked, min_start=0.0):
    if slot == "EXTRA":
        cs = [c for c in pool if c["slug"] not in blocked
              and any(p in POS_SLOTS[1:] for p in c["positions"])]  # non-GK
    else:
        cs = [c for c in pool if c["slug"] not in blocked and slot in c["positions"]]
    # Prefer players at/above the start-probability floor (safe starters),
    # then by expected value. Below-floor players stay as a fallback so a slot
    # is never left empty (an empty slot scores 0 — worse than a risky start).
    return sorted(cs, key=lambda c: (c.get("start_prob", 0) >= min_start,
                                     c.get("ev", c["proj"])), reverse=True)


def build_team(pool, used, size, cap, max_classic=None, min_start=0.0):
    def _ev(c):
        return c.get("ev", c["proj"])
    slot_list = list(POS_SLOTS) + ["EXTRA"] * (size - 4)
    chosen = {}          # slot index -> card
    blocked = set(used)
    for idx, slot in enumerate(slot_list):
        cs = cands(pool, slot, blocked, min_start)
        if cs:
            chosen[idx] = cs[0]
            blocked.add(cs[0]["slug"])
    if max_classic is not None:
        # Hot Streak: keep at most `max_classic` classic (non-in-season) cards.
        guard = 0
        while sum(1 for c in chosen.values() if c.get("is_classic")) > max_classic and guard < 400:
            guard += 1
            best = None  # replace a classic card with the least-loss in-season alt
            for idx, cur in chosen.items():
                if not cur.get("is_classic"):
                    continue
                others = blocked - {cur["slug"]}
                for alt in cands(pool, slot_list[idx], others, min_start):
                    if alt.get("is_classic"):
                        continue
                    loss = _ev(cur) - _ev(alt)
                    if best is None or loss < best[0]:
                        best = (loss, idx, alt)
            if not best:
                break
            _, idx, alt = best
            blocked.discard(chosen[idx]["slug"])
            chosen[idx] = alt
            blocked.add(alt["slug"])
    if cap is not None:
        guard = 0
        while sum(c["cap_score"] for c in chosen.values()) > cap and guard < 400:
            guard += 1
            best = None
            for idx, cur in chosen.items():
                slot = slot_list[idx]
                others = blocked - {cur["slug"]}
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
            blocked.discard(chosen[idx]["slug"])
            chosen[idx] = alt
            blocked.add(alt["slug"])
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

    fx = get_upcoming_fixture()
    ws = dt.datetime.fromisoformat(fx["startDate"].replace("Z", "+00:00"))
    we = dt.datetime.fromisoformat(fx["endDate"].replace("Z", "+00:00"))
    print(f"Upcoming GW {fx['gameWeek']} ({fx['slug']}) {ws.date()}–{we.date()}", file=sys.stderr)

    comps = fetch_competitions(fx["slug"], rarities)
    print(f"{len(comps)} competitions to build.", file=sys.stderr)

    cards = fetch_cards(args.slug, rarities)
    print(f"Fetched {len(cards)} cards.", file=sys.stderr)
    current_season = max((c.get("seasonYear") or 0 for c in cards), default=0)
    print(f"Current season = {current_season}", file=sys.stderr)
    slugs = {c["anyPlayer"]["slug"] for c in cards if c.get("anyPlayer")}
    print(f"Fetching form/cap/next-game for {len(slugs)} players...", file=sys.stderr)
    players = fetch_players(slugs)

    # eligible pool per rarity (one best-season card per player)
    pools = {}
    dropped = set()
    matched_keys = set()
    for rar in rarities:
        best = {}
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
            e = eligible_entry(c, pd, ws, we)
            if not e:
                continue
            prev = best.get(e["player_slug"])
            if prev is None or (e["season"] or 0) > (prev["season"] or 0):
                best[e["player_slug"]] = e
        for e in best.values():
            e["is_classic"] = (e.get("season") or 0) < current_season
            apply_matchup(e)
        pools[rar] = list(best.values())
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
           "eligible": {r: len(pools.get(r, [])) for r in rarities},
           "competitions": []}

    def comp_pool(comp, available):
        # league filter only; the in-season/classic rule is enforced per format
        # (Hot Streak allows at most 1 classic; Arena allows all seasons).
        pool = [e for e in available if e["rarity_"] == comp["rarity"]]
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
        used_local = set(used_global)
        for ti in range(comp["teams_cap"]):
            floor = START_FLOORS[min(ti, len(START_FLOORS) - 1)]
            avail = [e for e in pools[comp["rarity"]] if e["slug"] not in used_local]
            pool = build_pool(comp, avail)
            t = build_team(pool, set(), comp["size"], comp["cap"],
                           comp.get("max_classic"), min_start=floor)
            t["risk_floor"] = floor
            if not t["cards"]:
                break
            if not t["complete"] and teams:
                break  # only keep a partial team as the first entry
            teams.append(t)
            used_local |= t["used"]
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
        used_global = used_local
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


if __name__ == "__main__":
    main(sys.argv[1:])
