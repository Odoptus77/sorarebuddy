#!/usr/bin/env python3
"""Suggest Sorare lineups per competition (cap tier) for the upcoming gameweek.

Public data only (no OAuth). Reads the upcoming gameweek's competition structure
(leaderboards), then for each rarity the manager owns builds a lineup for each
cap tier present (Uncapped, Cap 260, Cap 220, ...), respecting:
  - rarity
  - the SO5 formation (GK, DEF, MID, FWD + Extra)
  - the cap: sum of the five cards' L15 average score must stay <= cap
maximising the projected score (recent form x appearance rate x home edge),
excluding injured players and players without a game in the gameweek.

Honest limits: league-specific (e.g. SPFL, LALIGA) and Under-21 competitions are
NOT built here, because they need per-player league/age data not fetched. Opponent
strength and non-injury news are not in the Sorare API.

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
  activeClub { ... on Club { name } }
  activeInjuries { status kind }
  nextGame { date statusTyped homeTeam { ... on Club { name } } awayTeam { ... on Club { name } } }
  l5: averageScore(type: LAST_FIVE_SO5_AVERAGE_SCORE)
  l15: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
"""


def get_upcoming_fixture():
    q = """{ so5 { so5Fixtures(first: 8) { nodes {
              slug gameWeek aasmState startDate endDate } } } }"""
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


def rarity_of(lb_type):
    for rar, tok in RARITY_TOKENS:
        if tok in lb_type:
            return rar
    return None


def fetch_competitions(fx_slug, rarities):
    """Return, per rarity, the set of cap tiers present (None = uncapped)."""
    q = ('{ so5 { so5Fixture(slug: "%s") { so5Leaderboards { displayName so5LeaderboardType } } } }'
         % fx_slug)
    lbs = graphql(q)["data"]["so5"]["so5Fixture"]["so5Leaderboards"]
    caps = {r: set() for r in rarities}
    for lb in lbs:
        rar = rarity_of(lb["so5LeaderboardType"])
        if rar not in caps:
            continue
        m = re.search(r"Cap (\d+)", lb["displayName"])
        if m:
            caps[rar].add(int(m.group(1)))
    return caps


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
    """Return a lineup entry dict if the card's player is eligible, else None."""
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
    l5 = pd.get("l5")
    l15 = pd.get("l15")
    if not l5:
        return None
    app = pd.get("lastFifteenSo5Appearances") or 0
    club = (pd.get("activeClub") or {}).get("name")
    home = (ng.get("homeTeam") or {}).get("name")
    away = (ng.get("awayTeam") or {}).get("name")
    is_home = club is not None and club == home
    proj = round(l5 * (0.75 + 0.25 * min(1.0, app / 15.0)) * (1.03 if is_home else 1.0), 1)
    return {
        "slug": card["slug"], "player": card["anyPlayer"]["displayName"],
        "player_slug": card["anyPlayer"]["slug"], "season": card.get("seasonYear"),
        "positions": card["anyPlayer"].get("anyPositions") or [],
        "proj": proj, "cap_score": round(l15 if l15 else l5, 1),
        "l5": round(l5, 1), "appearances": app,
        "home": is_home, "opponent": away if is_home else home,
    }


def cands_for(pool, slot, used):
    if slot == "EXTRA":
        cs = [c for c in pool if c["slug"] not in used]
    else:
        cs = [c for c in pool if c["slug"] not in used and slot in c["positions"]]
    return sorted(cs, key=lambda c: -c["proj"])


def build_lineup(pool, cap):
    """Greedy best formation, then repair down to the cap by cheapest-loss swaps."""
    slots = POS_SLOTS + ["EXTRA"]
    chosen = {}
    used = set()
    for slot in slots:
        cs = cands_for(pool, slot, used)
        if cs:
            chosen[slot] = cs[0]
            used.add(cs[0]["slug"])
    if not chosen:
        return None
    if cap is not None:
        guard = 0
        while sum(c["cap_score"] for c in chosen.values()) > cap and guard < 300:
            guard += 1
            best = None  # (ratio, slot, alt)
            for slot, cur in chosen.items():
                others = used - {cur["slug"]}
                for alt in cands_for(pool, slot, others):
                    saved = cur["cap_score"] - alt["cap_score"]
                    if saved <= 0:
                        continue
                    loss = cur["proj"] - alt["proj"]        # may be negative (win)
                    ratio = loss / saved
                    if best is None or ratio < best[0]:
                        best = (ratio, slot, alt)
            if not best:
                break
            _, slot, alt = best
            used.discard(chosen[slot]["slug"])
            chosen[slot] = alt
            used.add(alt["slug"])
    cards = []
    for slot in slots:
        if slot in chosen:
            c = dict(chosen[slot]); c["slot"] = slot
            cards.append(c)
    if cards:
        cap_used = round(sum(c["cap_score"] for c in cards), 1)
        captain = max(cards, key=lambda c: c["proj"])
        captain["captain"] = True
        proj_total = round(sum(c["proj"] for c in cards) + captain["proj"], 1)
    else:
        cap_used, proj_total = 0, 0
    return {"cards": cards, "cap": cap, "cap_used": cap_used,
            "projected_total": proj_total,
            "complete": len(cards) == 5,
            "over_cap": cap is not None and cap_used > cap}


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

    caps_by_rarity = fetch_competitions(fx["slug"], rarities)
    print(f"Caps present: {caps_by_rarity}", file=sys.stderr)

    cards = fetch_cards(args.slug, rarities)
    print(f"Fetched {len(cards)} cards.", file=sys.stderr)
    slugs = {c["anyPlayer"]["slug"] for c in cards if c.get("anyPlayer")}
    print(f"Fetching form/cap/next-game for {len(slugs)} players...", file=sys.stderr)
    players = fetch_players(slugs)

    result = {"fixture": {"slug": fx["slug"], "gameWeek": fx["gameWeek"],
                          "start": fx["startDate"], "end": fx["endDate"]},
              "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
              "competitions": []}

    for rar in rarities:
        # one eligible card per player (best season)
        best_by_player = {}
        for c in cards:
            if c["rarityTyped"] != rar or not c.get("anyPlayer"):
                continue
            pd = players.get(c["anyPlayer"]["slug"])
            if not pd:
                continue
            e = eligible_entry(c, pd, ws, we)
            if not e:
                continue
            prev = best_by_player.get(e["player_slug"])
            if prev is None or (e["season"] or 0) > (prev["season"] or 0):
                best_by_player[e["player_slug"]] = e
        pool = list(best_by_player.values())
        if not pool:
            continue
        # tiers: uncapped + each cap present, high->low
        tiers = [(None, "All Star / Champion (uncapped)")]
        for cap in sorted(caps_by_rarity.get(rar, set()), reverse=True):
            tiers.append((cap, f"Cap {cap}"))
        for cap, label in tiers:
            lu = build_lineup(pool, cap)
            if not lu:
                continue
            result["competitions"].append({
                "rarity": rar, "label": label, "cap": cap,
                "eligible_count": len(pool), **lu})
            print(f"  {rar} · {label}: Σ{lu['projected_total']} "
                  f"cap {lu['cap_used']}/{cap if cap else '∞'} "
                  f"{'OK' if lu['complete'] and not lu['over_cap'] else 'partial/over'}",
                  file=sys.stderr)

    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {args.json} ({len(result['competitions'])} competitions)", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
