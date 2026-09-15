#!/usr/bin/env python3
"""Build a club overview for a Sorare manager: purchase price vs. current value.

Public data only -- no OAuth. Uses the API key (or proxy-injected key) to read
a manager's public gallery, the acquisition price of each tradeable card, and a
current-value estimate from recent market sales of the same player + rarity.

Usage:
    python3 club_overview.py <manager-slug> [--out club.csv] [--rarities limited,rare,super_rare,unique]

Notes:
- "Purchase price" is what the current owner paid, from public transfer data.
  Cards received via trade / reward / shards have no monetary price (shown blank).
- "Current value" is the median of recent public sales for that player + rarity.
  It is an estimate and does not distinguish card season.
"""
import argparse
import json
import statistics
import sys
import time

from sorare_client import graphql, load_env

DEFAULT_RARITIES = ["limited", "rare", "super_rare", "unique"]
PAGE_SIZE = 50
PRICE_BATCH = 15          # tokenPrices aliases per request
PACE_SECONDS = 0.3        # small delay between requests to be gentle on the API

CARDS_QUERY = """
query Club($slug: String!, $after: String, $rarities: [Rarity!]) {
  user(slug: $slug) {
    nickname
    cards(first: %d, after: $after, rarities: $rarities) {
      pageInfo { hasNextPage endCursor }
      nodes {
        slug
        rarityTyped
        seasonYear
        anyPlayer { slug displayName }
        tokenOwner { transferType amounts { eurCents } }
      }
    }
  }
}
""" % PAGE_SIZE


def fetch_all_cards(slug, rarities):
    """Page through the manager's tradeable cards."""
    cards = []
    after = None
    page = 0
    while True:
        resp = graphql(CARDS_QUERY, {"slug": slug, "after": after, "rarities": rarities})
        if "errors" in resp:
            sys.exit("GraphQL error while fetching cards:\n" + json.dumps(resp["errors"], indent=2))
        user = resp["data"]["user"]
        if user is None:
            sys.exit(f"Manager '{slug}' not found.")
        conn = user["cards"]
        cards.extend(conn["nodes"])
        page += 1
        print(f"  ...page {page}: {len(cards)} cards so far", file=sys.stderr)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
        time.sleep(PACE_SECONDS)
    return user["nickname"], cards


def fetch_price_medians(keys):
    """For each (player_slug, rarity, season) return the median recent sale price.

    Season matters a lot: an in-season limited card is worth far more than an
    old classic one, so we query tokenPrices per season to avoid mixing them.
    Batches many lookups into one request using GraphQL aliases.
    """
    medians = {}
    keys = list(keys)
    for start in range(0, len(keys), PRICE_BATCH):
        batch = keys[start:start + PRICE_BATCH]
        selections = []
        for i, (pslug, rarity, season) in enumerate(batch):
            # pslug is a slug (safe chars); embed directly with quotes.
            season_arg = f", season: {season}" if season else ""
            selections.append(
                f'a{i}: tokenPrices(playerSlug: "{pslug}", rarity: {rarity}{season_arg}) '
                f'{{ amounts {{ eurCents }} }}'
            )
        query = "{ tokens { " + " ".join(selections) + " } }"
        resp = graphql(query)
        data = (resp.get("data") or {}).get("tokens") or {}
        for i, key in enumerate(batch):
            sales = data.get(f"a{i}") or []
            cents = [s["amounts"]["eurCents"] for s in sales
                     if s.get("amounts") and s["amounts"].get("eurCents") is not None]
            medians[key] = statistics.median(cents) if cents else None
        print(f"  ...prices {min(start + PRICE_BATCH, len(keys))}/{len(keys)}", file=sys.stderr)
        time.sleep(PACE_SECONDS)
    return medians


def build_rows(cards, medians):
    rows = []
    for c in cards:
        player = c.get("anyPlayer") or {}
        pslug = player.get("slug")
        rarity = c["rarityTyped"]
        season = c.get("seasonYear")
        owner = c.get("tokenOwner") or {}
        amounts = owner.get("amounts") or {}
        purchase = amounts.get("eurCents")
        value = medians.get((pslug, rarity, season))
        delta = (value - purchase) if (value is not None and purchase is not None) else None
        delta_pct = (delta / purchase * 100) if (delta is not None and purchase) else None
        rows.append({
            "player": player.get("displayName", ""),
            "rarity": rarity,
            "season": c.get("seasonYear"),
            "card_slug": c["slug"],
            "transfer_type": owner.get("transferType", ""),
            "purchase_eur": round(purchase / 100, 2) if purchase is not None else None,
            "value_eur": round(value / 100, 2) if value is not None else None,
            "delta_eur": round(delta / 100, 2) if delta is not None else None,
            "delta_pct": round(delta_pct, 1) if delta_pct is not None else None,
        })
    return rows


def write_csv(rows, path):
    import csv
    fields = ["player", "rarity", "season", "purchase_eur", "value_eur",
              "delta_eur", "delta_pct", "transfer_type", "card_slug"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def summarize(rows):
    priced = [r for r in rows if r["purchase_eur"] is not None]
    valued = [r for r in rows if r["value_eur"] is not None]
    both = [r for r in rows if r["delta_eur"] is not None]
    total_purchase = sum(r["purchase_eur"] for r in priced)
    total_value_all = sum(r["value_eur"] for r in valued)
    total_value_both = sum(r["value_eur"] for r in both)
    total_purchase_both = sum(r["purchase_eur"] for r in both)
    delta = total_value_both - total_purchase_both
    print("\n=== CLUB SUMMARY ===")
    print(f"Cards total:                 {len(rows)}")
    print(f"  with known purchase price: {len(priced)}")
    print(f"  with value estimate:       {len(valued)}")
    print(f"  with both (comparable):    {len(both)}")
    print(f"Total spent (bought cards):  EUR {total_purchase:,.2f}")
    print(f"Est. value (all valued):     EUR {total_value_all:,.2f}")
    print(f"On comparable cards -> spent EUR {total_purchase_both:,.2f} | "
          f"value EUR {total_value_both:,.2f} | delta EUR {delta:,.2f}")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="manager slug, e.g. nicktd7")
    ap.add_argument("--out", default="club.csv")
    ap.add_argument("--rarities", default=",".join(DEFAULT_RARITIES))
    ap.add_argument("--json", dest="json_out", default=None,
                    help="also write the rows as JSON to this path")
    args = ap.parse_args(argv)
    load_env()
    rarities = [r.strip() for r in args.rarities.split(",") if r.strip()]

    print(f"Fetching cards for '{args.slug}' ({', '.join(rarities)})...", file=sys.stderr)
    nickname, cards = fetch_all_cards(args.slug, rarities)
    print(f"Fetched {len(cards)} cards for {nickname}.", file=sys.stderr)

    keys = {(c["anyPlayer"]["slug"], c["rarityTyped"], c.get("seasonYear"))
            for c in cards if c.get("anyPlayer")}
    print(f"Fetching value estimates for {len(keys)} player+rarity+season combos...", file=sys.stderr)
    medians = fetch_price_medians(keys)

    rows = build_rows(cards, medians)
    rows.sort(key=lambda r: (r["delta_eur"] is None, -(r["delta_eur"] or 0)))
    write_csv(rows, args.out)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"nickname": nickname, "rows": rows}, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {len(rows)} rows to {args.out}", file=sys.stderr)
    summarize(rows)


if __name__ == "__main__":
    main(sys.argv[1:])
