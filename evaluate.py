#!/usr/bin/env python3
"""Treffer-Bilanz + Lernkreislauf für die Startquoten.

Joins every prediction in logs/predictions.jsonl with what really happened
(Sorare's exact per-game `gameStarted` flag, minutes, SO5 score) and reports how
each data point performs:
  - overall and per source (model, researched override, Sorare-%, API-Football,
    national-duty / national-bench / red-card heuristics): predicted vs actual
    start rate + Brier score
  - Sorare's playingStatus label: actual start rate per label
  - "out" signals (API-Football Missing Fixture, call-ups, bench, red card):
    how often the player really did not start (precision)
  - scoring projection vs actual score (games he played): MAE + bias

It then LEARNS a calibration from the evaluated games and writes
calibration.json, which lineup_suggest.py applies automatically:
  - start probability, SEPARATELY per game type (national / club): regularised
    Platt scaling per source, p_cal = sigmoid(a + b * logit(p_raw)), shrunk
    towards the type-wide fit (shrunk towards "no change"; external sources
    like Nick's Sorare-app % straight towards "no change"), optionally plus a
    logit offset per Sorare playingStatus. A game type's calibration is only
    ACTIVE if it beats the raw probabilities out of sample (leave-one-out
    Brier) -> no learning of noise;
  - projection: one global scale factor (actual/predicted), shrunk towards 1,
    plus a factor per position x game type (club / national), shrunk towards
    the global one (e.g. defenders score less in national games) -- with the
    same leave-one-out guard (only used if it lowers the out-of-sample MAE).
The raw (pre-calibration) probability is what gets learned from, so the loop
does not feed on its own corrections.

Only the LAST prediction logged before kickoff counts per player & game.

Usage:
    python3 evaluate.py                 # report + logs/evaluation.json + calibration.json
    python3 evaluate.py --no-fit        # report only, keep calibration.json as is
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import time
from collections import defaultdict

from sorare_client import graphql

LOG = os.path.join("logs", "predictions.jsonl")
EVAL_OUT = os.path.join("logs", "evaluation.json")
CALIB_OUT = "calibration.json"
BATCH = 8
PACE = 0.25
MATCH_TOL = dt.timedelta(hours=12)      # log kickoff vs Sorare game date
FINISHED_AFTER = dt.timedelta(hours=3)  # kickoff + 3 h -> game is over
NO_ENTRY_AFTER = dt.timedelta(hours=36) # no game entry by then -> not in squad
MIN_N_GLOBAL = 30                       # evaluated games before anything is learned
LAMBDA = 8.0                            # prior strength (in "games")
PROJ_MIN_N = 20
PROJ_GROUP_MIN_N = 8                    # games per position x game type group
OUT_SIGNALS = ("apif_out", "callup_out", "intl_duty_auto", "natl_bench_auto",
               "natl_bench_soft", "suspension_risk", "sofa_pred_bench",
               "sofa_pred_out", "sofa_conf_bench", "sofa_conf_out")
# Calibration is learned SEPARATELY per game type (national vs club): an
# international break must not reshape the club-game probabilities. A game type
# only gets its own start-prob calibration from TYPE_MIN_N games; before that
# its probabilities stay unchanged.
TYPE_MIN_N = 20
# External, already news-aware sources: no shrink towards OUR model's
# miscalibration (prior = "no change") and no playingStatus offset on top.
EXTERNAL_SRCS = ("sorare_app", "sorare_odds", "sofa_pred_start", "sofa_pred_bench",
                 "sofa_pred_out", "sofa_conf_start", "sofa_conf_bench", "sofa_conf_out")
NO_FIT_SRCS = ("callup_out",)

OUTCOME_QUERY = """
{ players(slugs: [%s]) {
    slug
    anyPositions
    playerGameScores(last: 8) {
      score
      anyGame { date }
      anyPlayerGameStats { ... on PlayerGameStats { gameStarted minsPlayed onGameSheet } }
    }
} }
"""


def _ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def final_predictions(path, now):
    """Last prediction before kickoff per (player, kickoff), finished games only."""
    last = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            ko, ts = _ts(r.get("kickoff")), _ts(r.get("ts"))
            if not ko or not ts or ts > ko:
                continue
            key = (r["player_slug"], r["kickoff"])
            if key not in last or _ts(last[key]["ts"]) <= ts:
                last[key] = r
    done = {k: r for k, r in last.items() if _ts(k[1]) + FINISHED_AFTER <= now}
    return done, len(last) - len(done)


POSITIONS = {}


def proj_group(r):
    pos = r.get("pos") or POSITIONS.get(r["player_slug"]) or "?"
    return f"{pos}|{'national' if r.get('opp_type') == 'NationalTeam' else 'club'}"


def _proj(r):
    """Projection before the learned scale (what the model itself said)."""
    return r.get("proj_raw") if r.get("proj_raw") is not None else r.get("proj")


def fetch_outcomes(slugs):
    out, slugs = {}, sorted(slugs)
    for i in range(0, len(slugs), BATCH):
        chunk = slugs[i:i + BATCH]
        resp = graphql(OUTCOME_QUERY % ", ".join(f'"{s}"' for s in chunk))
        for p in ((resp.get("data") or {}).get("players") or []):
            if p and p.get("slug"):
                out[p["slug"]] = p.get("playerGameScores") or []
                POSITIONS[p["slug"]] = (p.get("anyPositions") or [None])[0]
        time.sleep(PACE)
    return out


def match_outcome(games, kickoff, now):
    """(started, played, mins, score) for the game at `kickoff`, 'pending' or None."""
    ko = _ts(kickoff)
    for g in games:
        gd = _ts((g.get("anyGame") or {}).get("date"))
        if gd and abs(gd - ko) <= MATCH_TOL:
            st = g.get("anyPlayerGameStats") or {}
            mins = st.get("minsPlayed") or 0
            started = st.get("gameStarted")
            started = bool(started) if started is not None else mins >= 60
            return {"started": started, "played": mins > 0, "mins": mins,
                    "score": g.get("score"), "in_squad": st.get("onGameSheet")}
    if ko + NO_ENTRY_AFTER <= now:       # no entry at all -> wasn't involved
        return {"started": False, "played": False, "mins": 0, "score": 0.0,
                "in_squad": False}
    return "pending"


def _sig(z):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def _logit(p):
    p = min(0.99, max(0.01, p))
    return math.log(p / (1 - p))


def fit_platt(pairs, prior=(0.0, 1.0), lam=LAMBDA):
    """Regularised Platt scaling: minimise log-loss of sigmoid(a + b*logit(p))
    plus lam*((a-a0)^2 + (b-b0)^2). Newton steps on the 2 parameters."""
    a, b = prior
    xs = [(_logit(p), y) for p, y in pairs]
    for _ in range(50):
        ga = 2 * lam * (a - prior[0])
        gb = 2 * lam * (b - prior[1])
        haa = hbb = 2 * lam
        hab = 0.0
        for x, y in xs:
            s = _sig(a + b * x)
            w = s * (1 - s)
            ga += s - y
            gb += (s - y) * x
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a, b = a - da, b - db
        if abs(da) + abs(db) < 1e-7:
            break
    return round(a, 4), round(b, 4)


def fit_offset(pairs, lam=LAMBDA):
    """Regularised logit offset d: minimise log-loss of sigmoid(z + d) plus
    lam*d^2 over (z, y) pairs (z = already calibrated logit)."""
    d = 0.0
    for _ in range(50):
        g, h = 2 * lam * d, 2 * lam
        for z, y in pairs:
            s = _sig(z + d)
            g += s - y
            h += s * (1 - s)
        step = g / h
        d -= step
        if abs(step) < 1e-7:
            break
    return round(d, 4)


def _mae(pairs):
    return round(sum(abs(p - a) for p, a in pairs) / len(pairs), 3) if pairs else None


def fit_proj(played):
    """Projection scale (actual/predicted, shrunk towards 1) + one factor per
    position x game type (shrunk towards the global scale)."""
    scale = 1.0
    if played and len(played) >= PROJ_MIN_N:
        ratio = sum(r["score"] for r in played) / max(1e-6, sum(_proj(r) for r in played))
        w = len(played) / (len(played) + 30)
        scale = round(max(0.8, min(1.25, 1 + w * (ratio - 1))), 3)
    groups = defaultdict(list)
    for r in played:
        groups[proj_group(r)].append(r)
    out = {}
    for k, rs in groups.items():
        if len(rs) < PROJ_GROUP_MIN_N:
            continue
        ratio = sum(r["score"] for r in rs) / max(1e-6, sum(_proj(r) for r in rs))
        w = len(rs) / (len(rs) + 30)
        out[k] = {"value": round(max(0.7, min(1.3, scale + w * (ratio - scale))), 3),
                  "n": len(rs)}
    return scale, out


def proj_factor(scale, groups, r):
    g = groups.get(proj_group(r))
    return g["value"] if g else scale


def game_type(r):
    return "national" if r.get("opp_type") == "NationalTeam" else "club"


def fit_type(rows, y):
    """Start-prob calibration for one game type, switched on ONLY if it beats
    the raw probabilities out of sample (leave-one-out Brier). In-sample gains
    with a few dozen games are mostly overfitting (02.10.: in-sample 0.189 vs
    raw 0.1995, but leave-one-out 0.204 = worse) -> this guard keeps the loop
    from 'learning' noise. Tries with and without the playingStatus offsets
    and keeps the better variant."""
    rows = [r for r in rows if r["p_raw"] is not None
            and r.get("start_src") not in NO_FIT_SRCS]
    raw = brier([(r["p_raw"], y(r)) for r in rows])
    best, best_loo = None, None
    if len(rows) >= TYPE_MIN_N:
        for with_status in (False, True):
            loo = brier([(apply_type(_fit_type(rows[:i] + rows[i + 1:], y, with_status,
                                               force=True), r), y(r))
                         for i, r in enumerate(rows)])
            if best_loo is None or loo < best_loo:
                best, best_loo = with_status, loo
    out = _fit_type(rows, y, bool(best))
    out["loo"] = {"raw": raw, "calibrated": best_loo, "with_status": bool(best)}
    out["active"] = bool(best_loo is not None and best_loo < raw)
    return out


def _fit_type(rows, y, with_status=True, force=False):
    """Platt per source (shrunk towards the type-wide fit, external sources
    towards 'no change') plus, optionally, a logit offset per Sorare
    playingStatus (shrunk towards 0) learned from the stage-1 residuals."""
    out = {"n": len(rows), "min_n": TYPE_MIN_N, "active": force or len(rows) >= TYPE_MIN_N}
    g = fit_platt([(r["p_raw"], y(r)) for r in rows]) if rows else (0.0, 1.0)
    out["global"] = {"a": g[0], "b": g[1]}
    out["sources"] = {}
    by_src = defaultdict(list)
    for r in rows:
        by_src[r.get("start_src") or "model"].append(r)
    for src, rs in by_src.items():
        prior = (0.0, 1.0) if src in EXTERNAL_SRCS else g
        a, b = fit_platt([(r["p_raw"], y(r)) for r in rs], prior=prior)
        out["sources"][src] = {"a": a, "b": b, "n": len(rs)}
    out["status"] = {}
    if not with_status:
        return out
    by_status = defaultdict(list)
    for r in rows:
        if (r.get("start_src") or "model") in EXTERNAL_SRCS:
            continue
        by_status[r.get("playing_status") or "NONE"].append(
            (stage1_logit(out, r), y(r)))
    out["status"] = {s: {"d": fit_offset(zs), "n": len(zs)} for s, zs in by_status.items()}
    return out


def stage1_logit(t, r):
    src = r.get("start_src") or "model"
    prm = t["sources"].get(src) or ({"a": 0.0, "b": 1.0} if src in EXTERNAL_SRCS
                                    else t["global"])
    return prm["a"] + prm["b"] * _logit(r["p_raw"])


def apply_type(t, r):
    """Calibrated start prob for one logged row (mirrors lineup_suggest)."""
    if not t or not t.get("active"):
        return r["p_raw"]
    z = stage1_logit(t, r)
    if (r.get("start_src") or "model") not in EXTERNAL_SRCS:
        z += (t["status"].get(r.get("playing_status") or "NONE") or {}).get("d", 0.0)
    return _sig(z)


def brier(pairs):
    return round(sum((p - y) ** 2 for p, y in pairs) / len(pairs), 4) if pairs else None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=LOG)
    ap.add_argument("--out", default=EVAL_OUT)
    ap.add_argument("--calibration", default=CALIB_OUT)
    ap.add_argument("--no-fit", action="store_true")
    args = ap.parse_args(argv)
    now = dt.datetime.now(dt.timezone.utc)

    if not os.path.exists(args.log):
        sys.exit(f"Kein Log unter {args.log} -- erst lineup_suggest.py laufen lassen.")
    preds, upcoming = final_predictions(args.log, now)
    outcomes = fetch_outcomes({k[0] for k in preds}) if preds else {}

    rows, pending = [], 0
    for (slug, ko), r in preds.items():
        o = match_outcome(outcomes.get(slug, []), ko, now)
        if o == "pending":
            pending += 1
            continue
        raw = r.get("start_prob_raw", r.get("start_prob"))
        rows.append({**r, "p_raw": raw, "p": r.get("start_prob"), **o})

    print("================ TREFFER-BILANZ ================")
    print(f"Stand {now:%Y-%m-%d %H:%M} UTC | ausgewertete Spiele: {len(rows)} | "
          f"Ergebnis noch nicht da: {pending} | Spiele noch nicht gespielt: {upcoming}")
    if not rows:
        print("Noch keine abgeschlossenen Spiele mit Vorhersage im Log.")
        return 0

    y = lambda r: 1 if r["started"] else 0
    all_pairs = [(r["p"], y(r)) for r in rows if r["p"] is not None]
    raw_pairs = [(r["p_raw"], y(r)) for r in rows if r["p_raw"] is not None]
    base = sum(v for _, v in all_pairs) / len(all_pairs)
    print(f"\nGesamt: Brier {brier(all_pairs)} (Baseline {brier([(base, v) for _, v in all_pairs])}"
          f", nur Basisrate raten) | Startquote real {base:.0%}")

    by_src = defaultdict(list)
    for r in rows:
        by_src[r.get("start_src") or "model"].append(r)
    print(f"\n{'Quelle':<17}{'n':>4}{'Ø vorherg.':>11}{'real':>7}{'Brier':>8}")
    src_stats = {}
    for src, rs in sorted(by_src.items(), key=lambda kv: -len(kv[1])):
        pr = [(r["p"], y(r)) for r in rs]
        st = {"n": len(rs), "mean_pred": round(sum(p for p, _ in pr) / len(pr), 3),
              "actual": round(sum(v for _, v in pr) / len(pr), 3), "brier": brier(pr)}
        src_stats[src] = st
        print(f"{src:<17}{st['n']:>4}{st['mean_pred']:>11.2f}{st['actual']:>7.2f}{st['brier']:>8}")

    out_stats = {}
    outs = [r for r in rows if r.get("start_src") in OUT_SIGNALS or (r.get("apif") or "").startswith("Missing")]
    if outs:
        hit = sum(1 for r in outs if not r["started"])
        out_stats = {"n": len(outs), "correct_out": hit}
        print(f"\nAusfall-Signale: {hit}/{len(outs)} richtig (Spieler startete wirklich nicht)")

    status_stats = {}
    for r in rows:
        s = r.get("playing_status") or "NONE"
        status_stats.setdefault(s, [0, 0])
        status_stats[s][0] += 1
        status_stats[s][1] += y(r)
    print("\nSorare-Status -> reale Startquote: " + ", ".join(
        f"{s} {v[1]}/{v[0]}" for s, v in sorted(status_stats.items(), key=lambda kv: -kv[1][0])))

    odds = [(r["sorare_start"], y(r)) for r in rows if r.get("sorare_start") is not None]
    if odds:
        print(f"Sorare-% (wenn vorhanden): Brier {brier(odds)} bei n={len(odds)}")

    misses = sorted((r for r in rows if r["p"] is not None and
                     ((r["p"] >= 0.7 and not r["started"]) or (r["p"] <= 0.3 and r["started"]))),
                    key=lambda r: -abs(r["p"] - y(r)))[:8]
    if misses:
        print("\nGrößte Fehlgriffe (≥70 % und nicht gestartet / ≤30 % und gestartet):")
        for r in misses:
            print(f"  {r['player_slug']:<28} {r['kickoff'][:10]} vorhergesagt "
                  f"{r['p']:.0%} ({r.get('start_src') or 'model'}) -> "
                  f"{'Startelf' if r['started'] else ('Joker' if r['played'] else 'nicht gespielt')}")

    played = [r for r in rows if r["played"] and r.get("score") is not None and _proj(r)]
    proj_stats = None
    if played:
        err = [r["proj"] - r["score"] for r in played]
        proj_stats = {"n": len(played), "mae": round(sum(abs(e) for e in err) / len(err), 2),
                      "bias": round(sum(err) / len(err), 2)}
        print(f"\nProjektion (gespielte Spiele): n={proj_stats['n']} MAE {proj_stats['mae']} "
              f"Bias {proj_stats['bias']:+} (>0 = überschätzt)")
        by_grp = defaultdict(list)
        for r in played:
            by_grp[proj_group(r)].append(r)
        proj_stats["groups"] = {}
        for k, rs in sorted(by_grp.items(), key=lambda kv: -len(kv[1])):
            e = [_proj(r) - r["score"] for r in rs]
            proj_stats["groups"][k] = {"n": len(rs), "bias": round(sum(e) / len(e), 2),
                                       "mae": round(sum(abs(x) for x in e) / len(e), 2)}
            print(f"  {k:<24} n={len(rs):>3} Bias {sum(e) / len(e):+6.1f}  "
                  f"MAE {sum(abs(x) for x in e) / len(e):5.1f}")

    calib = None
    if not args.no_fit:
        fit_pairs = [(r["p_raw"], y(r)) for r in rows
                     if r["p_raw"] is not None and r.get("start_src") not in NO_FIT_SRCS]
        calib = {"_updated": now.isoformat(), "n": len(fit_pairs),
                 "min_n": MIN_N_GLOBAL, "active": len(fit_pairs) >= MIN_N_GLOBAL}
        g = fit_platt(fit_pairs) if fit_pairs else (0.0, 1.0)
        calib["global"] = {"a": g[0], "b": g[1]}       # report only (all types)
        calib["by_type"] = {t: fit_type([r for r in rows if game_type(r) == t], y)
                            for t in ("national", "club")}
        scale, grp = fit_proj(played)
        # same out-of-sample guard as for the start probs: the factors are only
        # used if they lower the leave-one-out MAE against the raw projection
        loo_raw = _mae([(_proj(r), r["score"]) for r in played])
        loo_cal = _mae([(_proj(r) * proj_factor(*fit_proj(played[:i] + played[i + 1:]), r),
                         r["score"]) for i, r in enumerate(played)])
        proj_on = bool(loo_raw is not None and loo_cal is not None and loo_cal < loo_raw)
        calib["proj_loo"] = {"raw": loo_raw, "calibrated": loo_cal, "active": proj_on}
        if not proj_on:
            scale, grp = 1.0, {}
        calib["proj_scale"] = {"value": scale, "n": len(played)}
        calib["proj_scale_groups"] = grp
        cal_pairs = [(apply_type(calib["by_type"][game_type(r)], r), y(r)) for r in rows
                     if r["p_raw"] is not None and r.get("start_src") not in NO_FIT_SRCS]
        calib["brier_raw"] = brier(fit_pairs)
        calib["brier_calibrated_in_sample"] = brier(cal_pairs)
        with open(args.calibration, "w", encoding="utf-8") as fh:
            json.dump(calib, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        any_on = (calib["proj_loo"]["active"]
                  or any(v["active"] for v in calib["by_type"].values()))
        state = ("noch inaktiv (ab {} Spielen)".format(MIN_N_GLOBAL) if not calib["active"]
                 else "AKTIV" if any_on else "bereit, aber nichts verbessert sich out-of-sample -> neutral")
        types = " | ".join(
            f"{t}: n={v['n']} " + (f"a={v['global']['a']} b={v['global']['b']}"
                                   + ("; Status " + ", ".join(f"{s} {o['d']:+.2f}" for s, o in
                                                             sorted(v["status"].items()))
                                      if v["status"] else "")
                                   + f" (LOO {v['loo']['raw']} -> {v['loo']['calibrated']})"
                                   if v["active"] else
                                   (f"neutral (LOO roh {v['loo']['raw']} vs kalibriert "
                                    f"{v['loo']['calibrated']} -> keine Verbesserung)"
                                    if v["loo"]["calibrated"] is not None
                                    else f"neutral (ab {TYPE_MIN_N} Spielen)"))
            for t, v in calib["by_type"].items())
        print(f"\nLernkreislauf: Kalibrierung {state} | n={calib['n']} | {types}"
              f" | Brier roh {calib['brier_raw']} -> kalibriert {calib['brier_calibrated_in_sample']}"
              f" | Projektions-Faktor {scale}"
              f" (LOO-MAE roh {calib['proj_loo']['raw']} -> {calib['proj_loo']['calibrated']}"
              f"{'' if calib['proj_loo']['active'] else ', keine Verbesserung -> aus'})"
              + (" | je Gruppe: " + ", ".join(f"{k} {v['value']}" for k, v in
                                              calib["proj_scale_groups"].items())
                 if calib["proj_scale_groups"] else ""))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"updated": now.isoformat(), "evaluated": len(rows), "pending": pending,
                   "upcoming": upcoming,
                   "brier": brier(all_pairs), "brier_raw": brier(raw_pairs),
                   "start_rate": round(base, 3), "by_source": src_stats,
                   "out_signals": out_stats,
                   "playing_status": {k: {"n": v[0], "started": v[1]} for k, v in status_stats.items()},
                   "projection": proj_stats,
                   "misses": [{"player": r["player_slug"], "kickoff": r["kickoff"],
                               "pred": r["p"], "src": r.get("start_src") or "model",
                               "started": r["started"], "played": r["played"]}
                              for r in misses]}, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"\nGeschrieben: {args.out}" + (f", {args.calibration}" if calib else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
