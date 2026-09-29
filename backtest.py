#!/usr/bin/env python3
"""Backtest / calibration loop for the lineup model.

Measures — retrospectively, from Sorare's own game history — how good the
model's two predictions actually are:

  1. START probability: for each past game of each squad player, reconstruct the
     model's P(start) using ONLY the games BEFORE it (same recency-weighted
     minutes logic as lineup_suggest), then compare to what actually happened
     (did he start? proxy: minutes >= 60). Reports a calibration table + Brier
     score (lower = better; skill = improvement over always predicting the base
     rate).
  2. SCORING projection: the model's L5-style trailing average vs the actual SO5
     score of that game (over games he played). Reports MAE and bias.
  3. Bottom line EV: P(start) x projection vs the points the card actually
     delivered (its SO5 score if he played, else 0). MAE and bias.

Public data only (no OAuth). Reuses the exact minutes->start logic from
lineup_suggest so the numbers describe the REAL model.

Honest limitations (so the numbers aren't over-read):
  - Sorare's API returns at most ~15 games per player, so each player gives a
    short window; signal comes from pooling many players.
  - Point-in-time reconstruction can't see the injuries, researched overrides,
    SofaScore XIs or matchup weighting that the live run applies -> this scores
    the CORE model (minutes + appearance + form), i.e. the floor, not the
    override-assisted live output.
  - "Started" is proxied by minutes >= 60 (a starter subbed before 60' or a
    60'+ sub-on are edge cases the minute count can't resolve).

Usage:
    python3 backtest.py nicktd7 [--rarities limited] [--min-prior 3]
        [--players "slug1,slug2"]   # backtest specific players instead of squad
        [--json backtest.json]
"""
import argparse
import json
import sys
import time

from sorare_client import graphql
from lineup_suggest import (CARDS_QUERY, RECENCY_W, _mins_to_start, fetch_cards,
                            START_RECAL_K, BASE_START_RATE)

HIST = 15          # Sorare caps playerGameScores near 15
BATCH = 6          # score + detailedScore inflates query cost -> small batches
PACE = 0.25
START_MINS = 60    # minutes at/above which we count the game as a start


HISTORY_QUERY = """
{ players(slugs: [%s]) {
    slug
    playerGameScores(last: %d) {
      score
      anyGame { date }
      detailedScore { stat statValue }
    }
} }
"""


def fetch_histories(slugs):
    """slug -> chronological (oldest-first) list of {date, score, mins}."""
    out, slugs, i, batch = {}, list(slugs), 0, BATCH
    while i < len(slugs):
        chunk = slugs[i:i + batch]
        q = HISTORY_QUERY % (", ".join(f'"{s}"' for s in chunk), HIST)
        resp = graphql(q)
        data = resp.get("data")
        if not data:
            if batch > 2:
                batch = max(2, batch // 2)
                continue
            print(f"  history fetch failed for {chunk}: {resp.get('errors')}",
                  file=sys.stderr)
            i += len(chunk)
            continue
        for p in (data.get("players") or []):
            if not p or not p.get("slug"):
                continue
            games = []
            for g in (p.get("playerGameScores") or []):
                mp = None
                for s in (g.get("detailedScore") or []):
                    if s.get("stat") == "mins_played":
                        mp = s.get("statValue")
                        break
                date = ((g.get("anyGame") or {}).get("date") or "")[:10]
                games.append({"date": date, "score": g.get("score"), "mins": mp})
            # API returns most-recent-first -> flip to chronological.
            games.reverse()
            out[p["slug"]] = games
        i += len(chunk)
        print(f"  ...history {min(i, len(slugs))}/{len(slugs)}", file=sys.stderr)
        time.sleep(PACE)
    return out


def model_start_prob(prior):
    """Reconstruct the model's P(start) from the games BEFORE the target one.

    `prior` is the chronological list of prior games; mirrors
    lineup_suggest.start_probability minus the point-in-time-unknowable injury
    factor and researched overrides."""
    recent_first = list(reversed(prior))
    num = den = 0.0
    for i, g in enumerate(recent_first[:len(RECENCY_W)]):
        si = _mins_to_start(g["mins"])
        if si is None:
            continue
        w = RECENCY_W[i]
        num += w * si
        den += w
    min_signal = (num / den) if den else None
    # appearance rate over the last <=15 prior games with any minutes played
    last15 = recent_first[:15]
    apps = sum(1 for g in last15 if (g["mins"] or 0) > 0)
    app_rate = min(1.0, apps / 15.0)
    if min_signal is None:
        base = app_rate * 0.85
    else:
        base = 0.70 * min_signal + 0.30 * app_rate
    # mirror the deployed mild recalibration toward the base rate
    base = (1 - START_RECAL_K) * base + START_RECAL_K * BASE_START_RATE
    return max(0.0, min(0.98, base))


def model_proj(prior):
    """Played-only blend, mirroring lineup_suggest.played_projection:
    0.6*mean(last5 played) + 0.4*mean(last15 played), over prior games with
    minutes > 0 (DNP/unused-sub games excluded)."""
    played = [g["score"] for g in reversed(prior)
              if (g.get("mins") or 0) > 0 and g.get("score") is not None]
    if not played:
        return None
    l5, l15 = played[:5], played[:15]
    return 0.6 * (sum(l5) / len(l5)) + 0.4 * (sum(l15) / len(l15))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--rarities", default="limited")
    ap.add_argument("--players", default="",
                    help="comma-separated player slugs to backtest instead of "
                         "the manager's whole squad")
    ap.add_argument("--min-prior", type=int, default=3,
                    help="minimum prior games required before a game is scored "
                         "(warm-up; default 3)")
    ap.add_argument("--json", default="")
    args = ap.parse_args(argv)

    if args.players.strip():
        slugs = [s.strip() for s in args.players.split(",") if s.strip()]
    else:
        rarities = [r.strip() for r in args.rarities.split(",") if r.strip()]
        cards = fetch_cards(args.slug, rarities)
        slugs = sorted({c["anyPlayer"]["slug"] for c in cards if c.get("anyPlayer")})
    print(f"Backtesting {len(slugs)} players (<= {HIST} games each)...",
          file=sys.stderr)
    hist = fetch_histories(slugs)

    start_pairs = []     # (pred_prob, actual_start 0/1)
    proj_pairs = []      # (pred_proj, actual_score)  -- only games he played
    ev_pairs = []        # (pred_ev, actual_points)   -- all evaluable games
    for slug, games in hist.items():
        for i in range(len(games)):
            if i < args.min_prior:
                continue
            g = games[i]
            if g.get("mins") is None:      # no data for this game -> skip
                continue
            prior = games[:i]
            p_start = model_start_prob(prior)
            proj = model_proj(prior)
            played = (g["mins"] or 0) > 0
            started = (g["mins"] or 0) >= START_MINS
            start_pairs.append((p_start, 1 if started else 0))
            if proj is not None:
                actual_points = g["score"] if (played and g["score"] is not None) else 0.0
                ev_pairs.append((p_start * proj, actual_points))
                if played and g["score"] is not None:
                    proj_pairs.append((proj, g["score"]))

    if not start_pairs:
        sys.exit("No evaluable games (need players with game history). "
                 "Try --min-prior 2 or a different squad.")

    # --- start calibration ---
    n = len(start_pairs)
    base_rate = sum(a for _, a in start_pairs) / n
    brier = sum((p - a) ** 2 for p, a in start_pairs) / n
    brier_base = sum((base_rate - a) ** 2 for _, a in start_pairs) / n
    skill = (brier_base - brier) / brier_base if brier_base else 0.0
    bins = []
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        hi = lo + 0.2
        sel = [(p, a) for p, a in start_pairs if (p >= lo and (p < hi or (hi >= 1.0 and p <= hi)))]
        if sel:
            bins.append({"range": f"{lo:.1f}-{hi:.1f}", "n": len(sel),
                         "mean_pred": round(sum(p for p, _ in sel) / len(sel), 3),
                         "actual_start_rate": round(sum(a for _, a in sel) / len(sel), 3)})

    # --- scoring projection error (games played) ---
    def _err(pairs):
        if not pairs:
            return None
        m = len(pairs)
        mae = sum(abs(p - a) for p, a in pairs) / m
        bias = sum(p - a for p, a in pairs) / m
        mean_a = sum(a for _, a in pairs) / m
        base_mae = sum(abs(mean_a - a) for _, a in pairs) / m
        return {"n": m, "mae": round(mae, 2), "bias": round(bias, 2),
                "baseline_mae": round(base_mae, 2)}

    proj_stats = _err(proj_pairs)
    ev_stats = _err(ev_pairs)

    print("\n================ BACKTEST / KALIBRIERUNG ================")
    print(f"Spieler: {len(hist)}  |  bewertete Spiele: {n}  "
          f"(Warm-up: erste {args.min_prior} je Spieler übersprungen)")
    print("\n--- 1) START-Wahrscheinlichkeit ---")
    print(f"Basisrate (Ist-Startquote): {base_rate:.1%}")
    print(f"Brier-Score: {brier:.4f}  (Baseline {brier_base:.4f}, "
          f"Skill {skill:+.1%}; niedriger = besser, Skill>0 = besser als raten)")
    print(f"{'Vorhersage-Bin':>16} {'n':>5} {'Ø vorherg.':>11} {'Ist-Startrate':>14}")
    for b in bins:
        flag = ""
        diff = b["actual_start_rate"] - b["mean_pred"]
        if abs(diff) >= 0.12:
            flag = "  <- überschätzt" if diff < 0 else "  <- unterschätzt"
        print(f"{b['range']:>16} {b['n']:>5} {b['mean_pred']:>11.3f} "
              f"{b['actual_start_rate']:>14.3f}{flag}")

    print("\n--- 2) SCORING-Projektion (nur gespielte Spiele) ---")
    if proj_stats:
        print(f"n={proj_stats['n']}  MAE={proj_stats['mae']}  "
              f"Bias={proj_stats['bias']:+} (Bias>0 = Modell überschätzt)  "
              f"| Baseline-MAE {proj_stats['baseline_mae']}")
    else:
        print("keine Daten")

    print("\n--- 3) EV = P(Start) x Projektion vs. tatsächlich gelieferte Punkte ---")
    if ev_stats:
        print(f"n={ev_stats['n']}  MAE={ev_stats['mae']}  "
              f"Bias={ev_stats['bias']:+}  | Baseline-MAE {ev_stats['baseline_mae']} "
              f"(schlägt das Modell die Baseline?)")
    else:
        print("keine Daten")
    print("========================================================")
    print("Hinweis: misst das KERN-Modell ohne Live-Overrides/Injuries/Matchup; "
          "'Start' = Minuten>=60 (Näherung).", file=sys.stderr)

    if args.json:
        out = {"players": len(hist), "games": n, "base_rate": round(base_rate, 4),
               "brier": round(brier, 4), "brier_baseline": round(brier_base, 4),
               "brier_skill": round(skill, 4), "calibration_bins": bins,
               "projection": proj_stats, "ev": ev_stats}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"Wrote {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
