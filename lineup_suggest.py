#!/usr/bin/env python3
"""Suggest Sorare lineups for the upcoming gameweek from a manager's own cards.

Public data only (no OAuth). For each owned card (Limited/Rare) whose player has
a game in the upcoming gameweek, project an expected SO5 score from recent form,
appearance rate and home/away, excluding injured players. Then build, per rarity:
  - a classic formation XI (GK, DEF, MID, FWD + Extra) with a captain pick
  - a "best form" top 5 (highest projections, ignoring position rules)

Honest limits: opponent strength and non-injury news are not in the Sorare API,
so the projection uses form + availability + home/away only.

Usage:
    python3 lineup_suggest.py <manager-slug> [--json lineups.json] [--rarities limited,rare]
"""
import argparse
import datetime as dt
import json
import statistics
import sys
import time

from sorare_client import graphql

CARD_PAGE = 50
PLAYER_BATCH = 20
PACE = 0.25
POS_SLOTS = ["Goalkeeper", "Defender", "Midfielder", "Forward"]

CARDS_QUERY = """
query Cards($slug: String!, $after: String, $rarities: [Rarity!]) {
  user(slug: $slug) {
    cards(first: %d, after: $after, rarities: $rarities) {
      pageInfo { hasNextPage endCursor }
      nodes {
        slug rarityTyped seasonYear
        anyPlayer { slug displayName anyPositions }
      }
    }
  }
}
""" % CARD_PAGE


def get_upcoming_fixture():
    q = """{ so5 { so5Fixtures(first: 8) { nodes {
              slug gameWeek aasmState startDate endDate } } } }"""
    nodes = graphql(q)["data"]["so5"]["so5Fixtures"]["nodes"]
    now = dt.datetime.now(dt.timezone.utc)
    upcoming = []
    for n in nodes:
        try:
            start = dt.datetime.fromisoformat(n["startDate"].replace("Z", "+00:00"))
        except Exception:
            continue
        if start > now:
            upcoming.append((start, n))
    upcoming.sort(key=lambda x: x[0])
    if not upcoming:
        # fall back to the most recent opened fixture
        opened = [n for n in nodes if n["aasmState"] == "opened"]
        return opened[0] if opened else nodes[0]
    return upcoming[0][1]


def fetch_cards(slug, rarities):
    cards = []
    after = None
    while True:
        conn = graphql(CARDS_QUERY, {"slug": slug, "after": after, "rarities": rarities})
        conn = conn["data"]["user"]["cards"]
        cards.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
        time.sleep(PACE)
    return cards


PLAYER_FIELDS = """
  slug displayName anyPositions lastFifteenSo5Appearances
  activeClub { ... on Club { name } }
  activeInjuries { status kind expectedEndDate }
  nextGame { date statusTyped
    homeTeam { ... on Club { name } }
    awayTeam { ... on Club { name } } }
  playerGameScores(last: 5) { score anyGame { statusTyped } }
"""


def fetch_players(slugs):
    """Fetch form/injury/next-game for many players, batched with aliases."""
    out = {}
    slugs = list(slugs)
    i = 0
    batch = PLAYER_BATCH
    while i < len(slugs):
        chunk = slugs[i:i + batch]
        sel = " ".join(
            f'p{j}: players(slugs: ["{s}"]) {{{PLAYER_FIELDS}}}'
            for j, s in enumerate(chunk)
        )
        resp = graphql("{ " + sel + " }")
        data = resp.get("data")
        if not data:
            # likely query-complexity: shrink the batch and retry this chunk
            if batch > 4:
                batch = max(4, batch // 2)
                continue
            sys.exit(f"Player fetch failed: {resp.get('errors')}")
        for j, s in enumerate(chunk):
            arr = data.get(f"p{j}") or []
            if arr:
                out[s] = arr[0]
        i += len(chunk)
        print(f"  ...players {min(i, len(slugs))}/{len(slugs)}", file=sys.stderr)
        time.sleep(PACE)
    return out


def project(pdata, window_start, window_end):
    """Return (projection, meta) or (None, meta) if not eligible this GW."""
    meta = {"injured": bool(pdata.get("activeInjuries")),
            "appearances": pdata.get("lastFifteenSo5Appearances") or 0}
    scores = [g["score"] for g in (pdata.get("playerGameScores") or [])
              if g.get("score") is not None
              and (g.get("anyGame") or {}).get("statusTyped") == "played"]
    meta["last5"] = scores
    meta["avg5"] = round(statistics.mean(scores), 1) if scores else None

    ng = pdata.get("nextGame")
    if not ng or not ng.get("date"):
        meta["eligible"] = False
        return None, meta
    try:
        gd = dt.datetime.fromisoformat(ng["date"].replace("Z", "+00:00"))
    except Exception:
        meta["eligible"] = False
        return None, meta
    if not (window_start <= gd <= window_end):
        meta["eligible"] = False
        return None, meta

    club = (pdata.get("activeClub") or {}).get("name")
    home = (ng.get("homeTeam") or {}).get("name")
    away = (ng.get("awayTeam") or {}).get("name")
    is_home = (club is not None and club == home)
    opp = away if is_home else home
    meta.update({"eligible": True, "home": is_home, "opponent": opp,
                 "kickoff": ng["date"]})

    if meta["injured"] or not scores:
        return (0.0 if meta["injured"] else None), meta

    base = statistics.mean(scores)
    app_rate = min(1.0, (meta["appearances"] or 0) / 15.0)
    proj = base * (0.75 + 0.25 * app_rate) * (1.03 if is_home else 1.0)
    return round(proj, 1), meta


def primary_slot(positions):
    for slot in POS_SLOTS:
        if slot in (positions or []):
            return slot
    return (positions or ["Forward"])[0]


def build_formation(pool):
    """pool: list of card dicts with 'proj' and 'positions'. Greedy GK/DEF/MID/FWD/Extra."""
    chosen = []
    used = set()
    for slot in POS_SLOTS:
        cands = [c for c in pool if c["slug"] not in used and slot in c["positions"]]
        cands.sort(key=lambda c: c["proj"], reverse=True)
        if cands:
            pick = dict(cands[0]); pick["slot"] = slot
            chosen.append(pick); used.add(pick["slug"])
    # Extra: best remaining of any position
    rest = [c for c in pool if c["slug"] not in used]
    rest.sort(key=lambda c: c["proj"], reverse=True)
    if rest:
        pick = dict(rest[0]); pick["slot"] = "Extra"
        chosen.append(pick); used.add(pick["slug"])
    if chosen:
        cap = max(chosen, key=lambda c: c["proj"])
        cap["captain"] = True
    total = round(sum(c["proj"] for c in chosen)
                  + max((c["proj"] for c in chosen), default=0), 1)  # captain ~ double
    return {"cards": chosen, "projected_total": total}


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

    cards = fetch_cards(args.slug, rarities)
    print(f"Fetched {len(cards)} cards.", file=sys.stderr)
    slugs = {c["anyPlayer"]["slug"] for c in cards if c.get("anyPlayer")}
    print(f"Fetching form/next-game for {len(slugs)} players...", file=sys.stderr)
    players = fetch_players(slugs)

    # project each player once
    proj_cache = {}
    for s, pd in players.items():
        proj_cache[s] = project(pd, ws, we)

    result = {"fixture": {"slug": fx["slug"], "gameWeek": fx["gameWeek"],
                          "start": fx["startDate"], "end": fx["endDate"]},
              "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
              "rarities": {}}

    for rar in rarities:
        # one card per player (highest season), eligible + projectable
        best_by_player = {}
        for c in cards:
            if c["rarityTyped"] != rar or not c.get("anyPlayer"):
                continue
            ps = c["anyPlayer"]["slug"]
            proj, meta = proj_cache.get(ps, (None, {}))
            if proj is None or not meta.get("eligible") or meta.get("injured"):
                continue
            entry = {
                "slug": c["slug"], "player": c["anyPlayer"]["displayName"],
                "player_slug": ps, "season": c.get("seasonYear"),
                "positions": c["anyPlayer"].get("anyPositions") or [],
                "proj": proj, "avg5": meta.get("avg5"), "last5": meta.get("last5"),
                "appearances": meta.get("appearances"),
                "home": meta.get("home"), "opponent": meta.get("opponent"),
                "kickoff": meta.get("kickoff"),
            }
            prev = best_by_player.get(ps)
            if prev is None or (entry["season"] or 0) > (prev["season"] or 0):
                best_by_player[ps] = entry
        pool = list(best_by_player.values())
        for c in pool:
            c["slot_primary"] = primary_slot(c["positions"])
        formation = build_formation(pool)
        best_form = sorted(pool, key=lambda c: c["proj"], reverse=True)[:5]
        result["rarities"][rar] = {
            "eligible_count": len(pool),
            "formation": formation,
            "best_form": best_form,
        }
        print(f"  {rar}: {len(pool)} eligible players", file=sys.stderr)

    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {args.json}", file=sys.stderr)
    for rar in rarities:
        f = result["rarities"][rar]["formation"]
        print(f"\n=== {rar.upper()} — Formation (proj total ~{f['projected_total']}) ===")
        for c in f["cards"]:
            cap = " (C)" if c.get("captain") else ""
            ha = "H" if c.get("home") else "A"
            print(f"  {c['slot']:11} {c['player'][:22]:22} proj {c['proj']:5}  "
                  f"avg5 {c['avg5']}  vs {c.get('opponent','?')} ({ha}){cap}")


if __name__ == "__main__":
    main(sys.argv[1:])
