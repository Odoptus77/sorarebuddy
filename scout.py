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
import os
import statistics
import sys
import unicodedata

from sorare_client import graphql

PLAYER_QUERY = """
query Scout($slugs: [String!]) {
  players(slugs: $slugs) {
    slug displayName anyPositions age
    country { code }
    activeClub { ... on Club { name domesticLeague { slug } country { code } } }
    lastFifteenSo5Appearances
    activeInjuries { kind expectedEndDate active }
    l5: averageScore(type: LAST_FIVE_SO5_AVERAGE_SCORE)
    l15: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
    nextGame { date
      homeTeam { __typename name ... on NationalTeam { country { code } } }
      awayTeam { __typename name ... on NationalTeam { country { code } } } }
  }
}
"""


def _norm(s):
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def load_strength(path):
    """{'clubs': {...}, 'nations': {...}} of 0..1 strengths, normalized keys."""
    strength = {"clubs": {}, "nations": {}}
    if not os.path.exists(path):
        return strength
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        for bucket in ("clubs", "nations"):
            strength[bucket] = {_norm(k): float(v)
                                for k, v in (raw.get(bucket) or {}).items()}
    except (ValueError, OSError) as exc:
        print(f"WARNING: could not read strength {path}: {exc}", file=sys.stderr)
    return strength


def next_opponent(p):
    """(opponent_name, 'Club'|'NationalTeam') for the player's next game, or (None, None).

    Club game: the side whose name isn't the player's club. National game: the
    side whose country code isn't the player's nationality."""
    ng = p.get("nextGame") or {}
    home, away = ng.get("homeTeam") or {}, ng.get("awayTeam") or {}
    if not home and not away:
        return None, None
    club = (p.get("activeClub") or {}).get("name")
    nat = (p.get("country") or {}).get("code")

    def mine(team):
        if team.get("__typename") == "NationalTeam":
            return nat is not None and (team.get("country") or {}).get("code") == nat
        return club is not None and team.get("name") == club

    opp = away if mine(home) else home
    return opp.get("name"), opp.get("__typename")


def matchup_factor(opponent, opp_type, strength, weight):
    if not weight or not opponent:
        return 1.0
    table = strength["nations"] if opp_type == "NationalTeam" else strength["clubs"]
    s = table.get(_norm(opponent))
    if s is None:
        return 1.0
    return round(1.0 + weight * (0.5 - s), 3)


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


def profile(p, price, strength=None, weight=0.0):
    l15 = p.get("l15") or 0.0
    l5 = p.get("l5") or 0.0
    app = p.get("lastFifteenSo5Appearances") or 0
    injured = any(a.get("active") for a in (p.get("activeInjuries") or []))
    club = p.get("activeClub") or {}
    opp, opp_type = next_opponent(p)
    mu = matchup_factor(opp, opp_type, strength or {"clubs": {}, "nations": {}}, weight)
    # Matchup-adjusted form is the projection we rank on: weak next opponent
    # bumps it up, strong one down (same formula as lineup_suggest).
    adj = round(l15 * mu, 1)
    # value = matchup-adjusted form per EUR. Guard tiny (<0.5€) floor prices.
    value = (adj / price) if (price and price >= 0.5 and adj) else None
    return {
        "slug": p["slug"], "name": p.get("displayName", p["slug"]),
        "pos": ",".join(p.get("anyPositions") or []), "age": p.get("age"),
        "club": club.get("name", ""), "league": (club.get("domesticLeague") or {}).get("slug"),
        "l15": round(l15, 1), "l5": round(l5, 1), "app": app,
        "opponent": opp, "opp_type": opp_type, "matchup": mu, "adj": adj,
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
    # Compare on matchup-adjusted form (adj), consistent with lineup_suggest.
    form_ok = bench is None or c["adj"] >= 0.9 * bench["adj"]
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
    ap.add_argument("--strength", default="team_strength.json",
                    help="opponent-strength file for matchup weighting (as in lineup_suggest)")
    ap.add_argument("--matchup-weight", type=float, default=0.20,
                    help="how strongly the next opponent adjusts form (0 = off)")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args(argv)
    strength = load_strength(args.strength) if args.matchup_weight else {"clubs": {}, "nations": {}}

    cand_slugs = [s.strip() for s in args.candidates.split(",") if s.strip()]
    all_slugs = ([args.like] if args.like else []) + cand_slugs
    if not all_slugs:
        ap.error("need --candidates (and optionally --like)")

    players = fetch_players(all_slugs)
    prices = fetch_prices(all_slugs, args.rarity, args.season)
    missing = [s for s in all_slugs if s not in players]
    if missing:
        print(f"WARNING: not found (check slug): {', '.join(missing)}", file=sys.stderr)

    w = args.matchup_weight
    bench = None
    if args.like and args.like in players:
        bench = profile(players[args.like], prices.get(args.like), strength, w)
        print("=== BENCHMARK ===")
        pr = f"{bench['price']:.2f}€" if bench["price"] else "?"
        mu = f" ×{bench['matchup']:.2f} vs {bench['opponent']}" if bench.get("opponent") else ""
        print(f"{bench['name']} ({bench['pos']}, {bench['club']}) — L15 {bench['l15']}, "
              f"adj {bench['adj']}{mu}, Einsätze {bench['app']}/15, Preis {pr}\n")

    rows = []
    for s in cand_slugs:
        if s not in players:
            continue
        c = profile(players[s], prices.get(s), strength, w)
        if args.position and args.position not in (c["pos"] or ""):
            continue
        rec, why = recommend(c, bench, args.budget)
        c["rec"], c["why"], c["target"] = rec, why, target_price(c)
        rows.append(c)

    # rank: Kaufen first, then by value (adj-form/€), then by adjusted form
    order = {"Kaufen": 0, "Watchlist": 1, "Skip": 2}
    rows.sort(key=lambda r: (order.get(r["rec"], 3), -(r["value"] or 0), -r["adj"]))

    print("=== KANDIDATEN (rangiert; adj = Form × Matchup) ===")
    hdr = (f"{'Spieler':22s} {'Pos':9s} {'Club':18s} {'L15':>5s} {'Mtch':>5s} {'adj':>5s} "
           f"{'Eins':>5s} {'Preis':>8s} {'P/L':>6s}  Empf.")
    print(hdr)
    for r in rows:
        pr = f"{r['price']:.2f}€" if r["price"] is not None else "   -"
        val = f"{r['value']:.1f}" if r["value"] else ("günstig" if r["price"] is not None and r["price"] < 0.5 else "  -")
        mu = f"×{r['matchup']:.2f}" if r.get("opponent") else "  -"
        tgt = f" (Ziel {r['target']:.2f}€)" if r["target"] else ""
        opp = f" [{r['opponent']}]" if r.get("opponent") else ""
        print(f"{r['name'][:22]:22s} {r['pos'][:9]:9s} {r['club'][:18]:18s} "
              f"{r['l15']:5.1f} {mu:>5s} {r['adj']:5.1f} {r['app']:3d}/15 {pr:>8s} {val:>6s}  "
              f"{r['rec']}{tgt}{opp} — {r['why']}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"benchmark": bench, "candidates": rows}, fh, ensure_ascii=False, indent=2)
        print(f"\nWrote {args.json_out}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
