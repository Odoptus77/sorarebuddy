#!/usr/bin/env python3
"""Scout replacement / target players and rank them by value.

Given a benchmark player (--like, e.g. the one you want to replace) and a list
of candidate player slugs (--candidates), fetch each one's hard Sorare data --
recent form (L15/L5 average score), appearance rate, next game, injuries -- plus
a market-price estimate for their card (median of recent Limited sales), then
rank the candidates by form, reliability and price/performance and print a clear
Kaufen / Watchlist / Skip call with a target price.

Public data only (uses the API key like the other scripts). Candidate sourcing
is deliberately left to the human/assistant (pick names from form tables, news,
Nick's leagues); this tool turns those names into a data-backed shortlist.

Usage:
    python3 scout.py --like rasmus-nissen-kristensen \
        --candidates "denzel-dumfries,jeremie-frimpong,..." [--rarity limited]
        [--season 2026] [--budget 40] [--position Defender] [--json scout.json]

Slugs are Sorare player slugs (firstname-lastname, e.g. "joshua-kimmich").
"""
import argparse
import json
import statistics
import sys

from sorare_client import graphql

PLAYER_QUERY = """
query Scout($slugs: [String!]) {
  players(slugs: $slugs) {
    slug displayName anyPositions age
    activeClub { ... on Club { name domesticLeague { slug } country { code } } }
    lastFifteenSo5Appearances
    activeInjuries { kind expectedEndDate active }
    l5: averageScore(type: LAST_FIVE_SO5_AVERAGE_SCORE)
    l15: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
    nextGame { date }
  }
}
"""


def fetch_players(slugs):
    out = {}
    for i in range(0, len(slugs), 10):
        chunk = slugs[i:i + 10]
        resp = graphql(PLAYER_QUERY, {"slugs": chunk})
        for p in (resp.get("data", {}).get("players") or []):
            if p and p.get("slug"):
                out[p["slug"]] = p
    return out


def _price_batch(chunk, rarity, season):
    """One aliased tokenPrices request; returns {slug: eur or None} or None on error.

    Without a season filter tokenPrices returns many sales per player, so a big
    batch can blow the GraphQL complexity limit -- the caller then splits it.
    """
    season_arg = f", season: {season}" if season else ""
    sels = [f'a{j}: tokenPrices(playerSlug: "{s}", rarity: {rarity}{season_arg}) '
            f'{{ amounts {{ eurCents }} }}' for j, s in enumerate(chunk)]
    resp = graphql("{ tokens { " + " ".join(sels) + " } }")
    if resp.get("errors") or not resp.get("data"):
        return None
    data = (resp["data"] or {}).get("tokens") or {}
    out = {}
    for j, s in enumerate(chunk):
        sales = data.get(f"a{j}") or []
        cents = [x["amounts"]["eurCents"] for x in sales
                 if x.get("amounts") and x["amounts"].get("eurCents") is not None]
        out[s] = (statistics.median(cents) / 100.0) if cents else None
    return out


def fetch_prices(slugs, rarity, season, batch=5):
    """Median of recent public sales (EUR) per player, with complexity-safe splitting."""
    prices = {}
    for i in range(0, len(slugs), batch):
        chunk = slugs[i:i + batch]
        res = _price_batch(chunk, rarity, season)
        if res is None and len(chunk) > 1:            # too complex -> split
            for s in chunk:
                one = _price_batch([s], rarity, season)
                prices[s] = (one or {}).get(s)
        else:
            prices.update(res or {s: None for s in chunk})
    return prices


def profile(p, price):
    l15 = p.get("l15") or 0.0
    l5 = p.get("l5") or 0.0
    app = p.get("lastFifteenSo5Appearances") or 0
    injured = any(a.get("active") for a in (p.get("activeInjuries") or []))
    club = p.get("activeClub") or {}
    # value = form points per EUR. Guard tiny prices (a <0.5€ floor makes the
    # ratio explode and isn't a meaningful comparison) -> treat as "very cheap".
    value = (l15 / price) if (price and price >= 0.5 and l15) else None
    return {
        "slug": p["slug"], "name": p.get("displayName", p["slug"]),
        "pos": ",".join(p.get("anyPositions") or []), "age": p.get("age"),
        "club": club.get("name", ""), "league": (club.get("domesticLeague") or {}).get("slug"),
        "l15": round(l15, 1), "l5": round(l5, 1), "app": app,
        "injured": injured, "price": price, "value": round(value, 3) if value else None,
        "has_game": bool(p.get("nextGame")),
    }


def recommend(c, bench, budget):
    """Kaufen / Watchlist / Skip with a one-line reason."""
    if c["injured"]:
        return "Skip", "verletzt"
    if c["l15"] < 1:
        return "Skip", "keine/kaum Form-Daten"
    over_budget = budget is not None and c["price"] is not None and c["price"] > budget
    form_ok = bench is None or c["l15"] >= 0.9 * bench["l15"]
    reliable = c["app"] >= 10
    cheaper = bench is None or (c["price"] is not None and bench["price"] is not None
                               and c["price"] <= bench["price"])
    if over_budget:
        return "Watchlist", f"über Budget ({c['price']:.2f}€)"
    if form_ok and reliable and cheaper:
        return "Kaufen", "Form >= Benchmark, verlässlich, nicht teurer"
    if form_ok and reliable:
        return "Watchlist", "stark, aber teurer als Benchmark"
    if not reliable:
        return "Watchlist", f"Einsatzrate niedrig ({c['app']}/15)"
    return "Watchlist", "Form unter Benchmark"


def target_price(c):
    return round(c["price"] * 0.9, 2) if c["price"] else None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--like", help="benchmark player slug (the one to replace)")
    ap.add_argument("--candidates", default="", help="comma-separated candidate slugs")
    ap.add_argument("--rarity", default="limited")
    ap.add_argument("--season", type=int, default=None, help="restrict price to this season year")
    ap.add_argument("--budget", type=float, default=None, help="max price in EUR")
    ap.add_argument("--position", default=None, help="only keep candidates with this position")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args(argv)

    cand_slugs = [s.strip() for s in args.candidates.split(",") if s.strip()]
    all_slugs = ([args.like] if args.like else []) + cand_slugs
    if not all_slugs:
        ap.error("need --candidates (and optionally --like)")

    players = fetch_players(all_slugs)
    prices = fetch_prices(all_slugs, args.rarity, args.season)
    missing = [s for s in all_slugs if s not in players]
    if missing:
        print(f"WARNING: not found (check slug): {', '.join(missing)}", file=sys.stderr)

    bench = None
    if args.like and args.like in players:
        bench = profile(players[args.like], prices.get(args.like))
        print("=== BENCHMARK ===")
        pr = f"{bench['price']:.0f}€" if bench["price"] else "?"
        print(f"{bench['name']} ({bench['pos']}, {bench['club']}) — L15 {bench['l15']}, "
              f"Einsätze {bench['app']}/15, Preis {pr}\n")

    rows = []
    for s in cand_slugs:
        if s not in players:
            continue
        c = profile(players[s], prices.get(s))
        if args.position and args.position not in (c["pos"] or ""):
            continue
        rec, why = recommend(c, bench, args.budget)
        c["rec"], c["why"], c["target"] = rec, why, target_price(c)
        rows.append(c)

    # rank: Kaufen first, then by value (form/€), then by form
    order = {"Kaufen": 0, "Watchlist": 1, "Skip": 2}
    rows.sort(key=lambda r: (order.get(r["rec"], 3), -(r["value"] or 0), -r["l15"]))

    print("=== KANDIDATEN (rangiert) ===")
    hdr = f"{'Spieler':22s} {'Pos':10s} {'Club':20s} {'L15':>5s} {'Eins':>5s} {'Preis':>7s} {'P/L':>5s}  Empf."
    print(hdr)
    for r in rows:
        pr = f"{r['price']:.2f}€" if r["price"] is not None else "   -"
        val = f"{r['value']:.1f}" if r["value"] else ("günstig" if r["price"] is not None and r["price"] < 0.5 else "  -")
        tgt = f" (Ziel {r['target']:.2f}€)" if r["target"] else ""
        print(f"{r['name'][:22]:22s} {r['pos'][:10]:10s} {r['club'][:20]:20s} "
              f"{r['l15']:5.1f} {r['app']:3d}/15 {pr:>8s} {val:>7s}  {r['rec']}{tgt} — {r['why']}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"benchmark": bench, "candidates": rows}, fh, ensure_ascii=False, indent=2)
        print(f"\nWrote {args.json_out}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
