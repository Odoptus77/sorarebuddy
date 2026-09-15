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
  activeClub { ... on Club { name domesticLeague { slug } } }
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
            token = body  # e.g. SCOTLAND, ENGLAND_SECOND, CONTENDERS
            if token not in LEAGUE_MAP:
                continue  # skip Contenders / Rest of the World / unmapped
            key = (rar, "SO7", None, token, True)
            g = groups.setdefault(key, {"teams_cap": 1})
            g["teams_cap"] = max(g["teams_cap"], tcap)
        # else: U21 / league arena / special -> skipped

    comps = []
    for (rar, fmt, cap, token, in_season), g in groups.items():
        league_prefix = None
        if token:
            league_prefix, name = LEAGUE_MAP[token]
            label = f"Liga · {name} (In-Season)"
        elif fmt == "SO7":
            label = f"Classic · {' / '.join(sorted(g['families']))}"
        elif cap:
            label = f"Arena · Cap {cap}"
        else:
            label = "Arena · Uncapped"
        comps.append({
            "rarity": rar, "label": label, "format": fmt,
            "size": 5 if fmt == "SO5" else 7, "cap": cap,
            "teams_cap": g["teams_cap"], "league_prefix": league_prefix,
            "in_season": in_season,
        })

    def rank(c):
        fam = 0 if c["league_prefix"] else (1 if c["format"] == "SO7" else 2)
        return (c["rarity"], fam, c["label"], -(c["cap"] or 99999))
    comps.sort(key=rank)
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
    league = ((pd.get("activeClub") or {}).get("domesticLeague") or {}).get("slug")
    return {"slug": card["slug"], "player": card["anyPlayer"]["displayName"],
            "player_slug": card["anyPlayer"]["slug"], "season": card.get("seasonYear"),
            "positions": card["anyPlayer"].get("anyPositions") or [],
            "proj": proj, "cap_score": round(l15 if l15 else l5, 1),
            "l5": round(l5, 1), "appearances": app, "league": league,
            "home": is_home, "opponent": away if is_home else home}


def cands(pool, slot, blocked):
    if slot == "EXTRA":
        cs = [c for c in pool if c["slug"] not in blocked
              and any(p in POS_SLOTS[1:] for p in c["positions"])]  # non-GK
    else:
        cs = [c for c in pool if c["slug"] not in blocked and slot in c["positions"]]
    return sorted(cs, key=lambda c: -c["proj"])


def build_team(pool, used, size, cap):
    slot_list = list(POS_SLOTS) + ["EXTRA"] * (size - 4)
    chosen = {}          # slot index -> card
    blocked = set(used)
    for idx, slot in enumerate(slot_list):
        cs = cands(pool, slot, blocked)
        if cs:
            chosen[idx] = cs[0]
            blocked.add(cs[0]["slug"])
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
    complete = len(cards) == size
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
        pools[rar] = list(best.values())
        print(f"  {rar}: {len(pools[rar])} eligible players", file=sys.stderr)

    out = {"fixture": {"slug": fx["slug"], "gameWeek": fx["gameWeek"],
                       "start": fx["startDate"], "end": fx["endDate"]},
           "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
           "eligible": {r: len(pools.get(r, [])) for r in rarities},
           "competitions": []}

    current_season = max((c.get("seasonYear") or 0 for c in cards), default=0)
    print(f"Current season = {current_season}", file=sys.stderr)

    for comp in comps:
        pool = pools.get(comp["rarity"], [])
        if comp.get("league_prefix"):
            pref = comp["league_prefix"]
            pool = [e for e in pool if (e.get("league") or "").startswith(pref)]
        if comp.get("in_season"):
            pool = [e for e in pool if (e.get("season") or 0) >= current_season]
        teams = []
        used = set()
        for _ in range(comp["teams_cap"]):
            t = build_team(pool, used, comp["size"], comp["cap"])
            if not t["cards"] or not t["complete"]:
                if not teams and t["cards"]:
                    teams.append(t)  # keep a partial first team to show what's missing
                break
            teams.append(t)
            used |= t["used"]
        for t in teams:
            t.pop("used", None)
        # league competitions only shown if a full team is fieldable (reduce noise)
        if comp.get("league_prefix") and not any(t.get("complete") for t in teams):
            continue
        out["competitions"].append({**{k: comp[k] for k in
                                    ("rarity", "label", "format", "size", "cap", "teams_cap")},
                                    "in_season": comp.get("in_season", False),
                                    "eligible_count": len(pool), "teams": teams})
        tt = ", ".join(f"Σ{t['projected_total']}" for t in teams) or "—"
        print(f"  {comp['rarity']} · {comp['label']} [{comp['format']}] "
              f"teams={len(teams)}/{comp['teams_cap']}: {tt}", file=sys.stderr)

    # Hot Streak proxy: Sorare's Hot Streak rules aren't in the API, so we show
    # a transparent "best form" top-5 pick per rarity (no formation / no cap).
    for rar in rarities:
        pool = sorted(pools.get(rar, []), key=lambda e: -e["proj"])[:5]
        if not pool:
            continue
        cards = []
        for e in pool:
            c = dict(e)
            c["slot"] = next((s for s in POS_SLOTS if s in c["positions"]),
                             (c["positions"] or ["Forward"])[0])
            cards.append(c)
        cap_c = max(cards, key=lambda c: c["proj"]); cap_c["captain"] = True
        team = {"cards": cards, "complete": len(cards) == 5,
                "cap_used": round(sum(c["cap_score"] for c in cards), 1),
                "over_cap": False,
                "projected_total": round(sum(c["proj"] for c in cards) + cap_c["proj"], 1)}
        out["competitions"].append({
            "rarity": rar, "label": "Hot Streak (Näherung · beste Form)",
            "format": "Best-5", "size": 5, "cap": None,
            "teams_cap": 1, "countries": None, "in_season": False,
            "eligible_count": len(pools.get(rar, [])), "teams": [team],
            "proxy": True})

    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
