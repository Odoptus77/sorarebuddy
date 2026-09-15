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
competitions are skipped. Opponent strength and non-injury news aren't in the
API. A card may be reused across DIFFERENT competitions (Sorare allows this);
within one competition's multiple teams the cards are distinct.

Usage:
    python3 lineup_suggest.py <manager-slug> [--json lineups.json] [--rarities limited,rare]
"""
import argparse
import datetime as dt
import json
import re
import sys
import time

from sorare_client import graphql

CARD_PAGE = 50
PLAYER_BATCH = 20
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
    "GERMANY": ("bundesliga", "Bundesliga"),
    "FRANCE": ("ligue-1", "Ligue 1"),
    "ITALY": ("serie-a", "Serie A"),
    "NETHERLANDS": ("eredivisie", "Eredivisie"),
    "SCOTLAND": ("premiership", "SPFL"),
    "JUPILER": ("jupiler", "Jupiler Pro League"),
    "PORTUGAL": ("liga-portugal", "Liga Portugal"),
    "USA": ("major-league-soccer", "MLS"),
    "MLS": ("major-league-soccer", "MLS"),
}
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


def prize_weight(comp):
    rw = RARITY_WEIGHT.get(comp["rarity"], 1.0)
    mw = MODE_WEIGHT.get(comp["mode"], 1.0)
    pref = comp.get("league_prefix")
    if pref:
        fam = FAMILY_TOP_LEAGUE if pref.startswith(TOP_LEAGUE_PREFIXES) else FAMILY_OTHER_LEAGUE
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
  slug displayName anyPositions lastFifteenSo5Appearances
  activeClub { ... on Club { name country { code } domesticLeague { slug } } }
  activeInjuries { status kind }
  nextGame { date statusTyped homeTeam { ... on Club { name } } awayTeam { ... on Club { name } } }
  l5: averageScore(type: LAST_FIVE_SO5_AVERAGE_SCORE)
  l15: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
"""


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

        if "ALL_STAR" in t or "CHAMPIONS" in t:
            fam = "Champion" if "CHAMPIONS" in t else "All Star"
            key = (rar, "SO5" if is_arena else "SO7", cap, None, False)
            g = groups.setdefault(key, {"families": set(), "teams_cap": 1})
            g["families"].add(fam)
            g["teams_cap"] = max(g["teams_cap"], tcap)
        elif t.startswith("IN_SEASON_") and not is_arena:
            # league-specific classic competition (SO7, in-season, league filter)
            body = t[len("IN_SEASON_"):]
            for tok in RARITY_TOKENS:
                body = body.replace("_" + tok[1], "")
            token = body  # e.g. SCOTLAND, ENGLAND_SECOND, JAPAN, CONTENDERS
            if resolve_league(token) is None:
                continue  # Contender / Rest of the World / unmapped
            key = (rar, "HS", None, token, True)   # HS = Hot Streak (5 cards)
            g = groups.setdefault(key, {"teams_cap": 1})
            g["teams_cap"] = max(g["teams_cap"], tcap)
        elif is_arena:
            # league arena (SO5, cap, league filter, all seasons)
            m2 = re.match(r"ALL_SEASONS_(.+?)_ARENA", t)
            token = m2.group(1) if m2 else None
            if not token or resolve_league(token) is None:
                continue  # U21 arena / unmapped
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
        if token:
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
            "in_season": in_season,
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


def eligible_entry(card, pd, ws, we):
    if pd.get("activeInjuries"):
        return None
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
    app = pd.get("lastFifteenSo5Appearances") or 0
    club = (pd.get("activeClub") or {}).get("name")
    home = (ng.get("homeTeam") or {}).get("name")
    away = (ng.get("awayTeam") or {}).get("name")
    is_home = club is not None and club == home
    proj = round(l5 * (0.75 + 0.25 * min(1.0, app / 15.0)) * (1.03 if is_home else 1.0), 1)
    club = pd.get("activeClub") or {}
    league = (club.get("domesticLeague") or {}).get("slug")
    country = (club.get("country") or {}).get("code")
    return {"slug": card["slug"], "player": card["anyPlayer"]["displayName"],
            "player_slug": card["anyPlayer"]["slug"], "season": card.get("seasonYear"),
            "positions": card["anyPlayer"].get("anyPositions") or [],
            "proj": proj, "cap_score": round(l15 if l15 else l5, 1),
            "l5": round(l5, 1), "appearances": app, "league": league, "country": country,
            "home": is_home, "opponent": away if is_home else home,
            "kickoff": ng["date"]}


def cands(pool, slot, blocked):
    if slot == "EXTRA":
        cs = [c for c in pool if c["slug"] not in blocked
              and any(p in POS_SLOTS[1:] for p in c["positions"])]  # non-GK
    else:
        cs = [c for c in pool if c["slug"] not in blocked and slot in c["positions"]]
    return sorted(cs, key=lambda c: -c["proj"])


def build_team(pool, used, size, cap, max_classic=None):
    slot_list = list(POS_SLOTS) + ["EXTRA"] * (size - 4)
    chosen = {}          # slot index -> card
    blocked = set(used)
    for idx, slot in enumerate(slot_list):
        cs = cands(pool, slot, blocked)
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
                for alt in cands(pool, slot_list[idx], others):
                    if alt.get("is_classic"):
                        continue
                    loss = cur["proj"] - alt["proj"]
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
                for alt in cands(pool, slot, others):
                    saved = cur["cap_score"] - alt["cap_score"]
                    if saved <= 0:
                        continue
                    ratio = (cur["proj"] - alt["proj"]) / saved
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
        cap_card = max(cards, key=lambda c: c["proj"]); cap_card["captain"] = True
        proj_total = round(sum(c["proj"] for c in cards) + cap_card["proj"], 1)
    else:
        proj_total = 0
    return {"cards": cards, "complete": complete, "cap_used": cap_used,
            "over_cap": cap is not None and cap_used > cap,
            "projected_total": proj_total,
            "used": {c["slug"] for c in cards}}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--json", default="lineups.json")
    ap.add_argument("--rarities", default="limited,rare")
    args = ap.parse_args(argv)
    rarities = [r.strip() for r in args.rarities.split(",") if r.strip()]

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
    for rar in rarities:
        best = {}
        for c in cards:
            if c["rarityTyped"] != rar or not c.get("anyPlayer"):
                continue
            pd = players.get(c["anyPlayer"]["slug"])
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
        pools[rar] = list(best.values())
        print(f"  {rar}: {len(pools[rar])} eligible players", file=sys.stderr)

    out = {"fixture": {"slug": fx["slug"], "gameWeek": fx["gameWeek"],
                       "start": fx["startDate"], "end": fx["endDate"]},
           "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
           "eligible": {r: len(pools.get(r, [])) for r in rarities},
           "competitions": []}

    def comp_pool(comp, available):
        # league filter only; the in-season/classic rule is enforced per format
        # (Hot Streak allows at most 1 classic; Arena allows all seasons).
        pool = [e for e in available if e["rarity_"] == comp["rarity"]]
        if comp.get("league_prefix"):
            pref = comp["league_prefix"]
            pool = [e for e in pool if (e.get("league") or "").startswith(pref)]
        elif comp.get("country_code"):
            cc = comp["country_code"]
            pool = [e for e in pool if e.get("country") == cc]
        return pool

    # tag rarity on entries so a single global "used" set works across rarities
    for rar in rarities:
        for e in pools.get(rar, []):
            e["rarity_"] = rar

    def window(teams):
        ko = [c["kickoff"] for t in teams for c in t["cards"] if c.get("kickoff")]
        return (min(ko), max(ko)) if ko else (None, None)

    all_entries = sum(pools.values(), [])

    def enough_pool(comp):
        pool = comp_pool(comp, all_entries)
        if comp.get("hotstreak"):
            # need >=2 in-season league cards for a hot streak (+ classic slot)
            return sum(1 for e in pool if not e.get("is_classic")) >= 2
        if comp.get("league_prefix") or comp.get("country_code"):
            return len(pool) >= 4
        return True

    # ---- max-profit priority: each card used only once (global) ----
    # Pass A: standalone strength of each competition's best single team.
    for comp in comps:
        base = build_team(comp_pool(comp, all_entries), set(),
                          comp["size"], comp["cap"], comp.get("max_classic"))
        comp["prize_weight"] = prize_weight(comp)
        # expected reward proxy = lineup strength x prize-pool weight
        comp["_priority"] = base["projected_total"] * comp["prize_weight"]
    for comp in comps:
        if comp.get("hotstreak"):
            n_ins = sum(1 for e in comp_pool(comp, all_entries) if not e.get("is_classic"))
            print(f"  [hotstreak pool] {comp['rarity']} {comp['label']}: "
                  f"{n_ins} in-season", file=sys.stderr)
    comps = [c for c in comps if enough_pool(c)]
    # Always fill In-Season Hot Streaks first (best cards), then the rest by
    # projected strength. Within each tier, strongest lineup first.
    comps.sort(key=lambda c: (0 if c.get("hotstreak") else 1, -c["_priority"]))

    # Pass B: fill in priority order from the shrinking global pool.
    used_global = set()
    for comp in comps:
        teams = []
        used_local = set(used_global)
        for _ in range(comp["teams_cap"]):
            avail = [e for e in pools[comp["rarity"]] if e["slug"] not in used_local]
            pool = comp_pool(comp, avail)
            t = build_team(pool, set(), comp["size"], comp["cap"], comp.get("max_classic"))
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
        tt = ", ".join(f"Σ{t['projected_total']}" for t in teams) or "—"
        print(f"  {comp['rarity']} · {comp['label']} [{comp['mode']}] "
              f"teams={len(teams)}/{comp['teams_cap']}: {tt}", file=sys.stderr)

    out["cards_used"] = len(used_global)
    out["total_projected"] = round(
        sum(t["projected_total"] for c in out["competitions"] for t in c["teams"]), 1)
    print(f"Total projected {out['total_projected']} across {out['cards_used']} cards",
          file=sys.stderr)

    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
