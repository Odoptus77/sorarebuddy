#!/usr/bin/env python3
"""Attribute Sorare lineup rewards to the players that earned them.

For every SO5 lineup a manager fielded, take the lineup's monetary reward,
split it evenly across the players in that lineup (the manager's "divide by 5"
idea -- we divide by the actual player count, which is 5 for the classic
Limited competitions), and sum per player.

Public data only (no OAuth). Note: Sorare only exposes a EUR value for a small
share of rewards (cash-prize competitions). Card rewards carry no monetary
value in the API and are skipped here (those cards already sit in the gallery
and count toward the club value).

Usage:
    python3 rewards_by_player.py <manager-slug> [--out rewards.csv] [--json rewards.json] [--max-fixtures N]
"""
import argparse
import csv
import json
import sys
import time
from collections import defaultdict

from sorare_client import graphql

PAGE = 20          # fixtures per request
LINEUPS = 50       # lineups per fixture (max a manager fields per gameweek)
PACE = 0.25

QUERY = """
query Fixtures($after: String, $slug: String!) {
  so5 {
    so5Fixtures(first: %d, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes {
        slug
        so5LineupsPaginated(first: %d, userSlug: $slug) {
          nodes {
            so5Leaderboard { displayName }
            so5Rankings { ranking so5Rewards { amount { eurCents } coinAmount } }
            so5Appearances { player { slug displayName } }
          }
        }
      }
    }
  }
}
""" % (PAGE, LINEUPS)


def fetch(slug, max_fixtures):
    after = None
    fixtures = 0
    lineups = 0
    lineups_with_players = 0
    reward_lineups = []          # (fixture, leaderboard, eur, players[])
    total_coins = 0
    while True:
        resp = graphql(QUERY, {"after": after, "slug": slug})
        conn = resp["data"]["so5"]["so5Fixtures"]
        for fx in conn["nodes"]:
            fixtures += 1
            for lu in fx["so5LineupsPaginated"]["nodes"]:
                lineups += 1
                players = [ap["player"] for ap in lu["so5Appearances"] if ap.get("player")]
                if players:
                    lineups_with_players += 1
                eur = 0
                for rk in lu["so5Rankings"]:
                    for rw in rk["so5Rewards"]:
                        amt = rw.get("amount")
                        if amt and amt.get("eurCents"):
                            eur += amt["eurCents"]
                        if rw.get("coinAmount"):
                            total_coins += rw["coinAmount"]
                if eur > 0 and players:
                    reward_lineups.append({
                        "fixture": fx["slug"],
                        "leaderboard": (lu.get("so5Leaderboard") or {}).get("displayName", "?"),
                        "eur": eur / 100,
                        "players": players,
                    })
        print(f"  ...{fixtures} fixtures, {lineups} lineups, "
              f"{len(reward_lineups)} with € reward", file=sys.stderr)
        if not conn["pageInfo"]["hasNextPage"] or (max_fixtures and fixtures >= max_fixtures):
            break
        after = conn["pageInfo"]["endCursor"]
        time.sleep(PACE)
    return {
        "fixtures": fixtures, "lineups": lineups,
        "lineups_with_players": lineups_with_players,
        "reward_lineups": reward_lineups, "total_coins": total_coins,
    }


def attribute(reward_lineups):
    """Split each lineup's reward evenly across its players; sum per player."""
    per_player = defaultdict(lambda: {"name": "", "reward_eur": 0.0, "lineups": 0})
    for lu in reward_lineups:
        n = len(lu["players"])
        share = lu["eur"] / n
        for p in lu["players"]:
            rec = per_player[p["slug"]]
            rec["name"] = p["displayName"]
            rec["reward_eur"] += share
            rec["lineups"] += 1
    rows = [{"player": v["name"], "slug": k,
             "reward_eur": round(v["reward_eur"], 2),
             "reward_lineups": v["lineups"]}
            for k, v in per_player.items()]
    rows.sort(key=lambda r: -r["reward_eur"])
    return rows


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--out", default="rewards.csv")
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--max-fixtures", type=int, default=0)
    args = ap.parse_args(argv)

    print(f"Scanning lineups for '{args.slug}'...", file=sys.stderr)
    data = fetch(args.slug, args.max_fixtures)
    rows = attribute(data["reward_lineups"])
    total = round(sum(r["reward_eur"] for r in rows), 2)

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["player", "reward_eur", "reward_lineups", "slug"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"slug": args.slug, "totals": {
                "fixtures": data["fixtures"], "lineups": data["lineups"],
                "reward_lineups": len(data["reward_lineups"]),
                "total_reward_eur": total},
                "players": rows,
                "reward_lineups": data["reward_lineups"]}, fh, ensure_ascii=False, indent=2)

    print(f"\n=== REWARDS BY PLAYER ({args.slug}) ===")
    print(f"Fixtures scanned:        {data['fixtures']}")
    print(f"Lineups fielded:         {data['lineups']}")
    print(f"Lineups with € reward:   {len(data['reward_lineups'])}")
    print(f"Total monetary reward:   EUR {total:,.2f}")
    print(f"Players credited:        {len(rows)}")
    print("\nTop 15 players by reward earned:")
    for r in rows[:15]:
        print(f"  {r['player'][:26]:26} €{r['reward_eur']:6.2f}  ({r['reward_lineups']} lineups)")


if __name__ == "__main__":
    main(sys.argv[1:])
