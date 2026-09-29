#!/usr/bin/env python3
"""GW-Bilanz: Nicks ECHTE Aufstellungen und Ergebnisse je Gameweek (OAuth).

Liest über den eingeloggten Nutzer (SORARE_ACCESS_TOKEN, s. docs/oauth-setup.md)
je Gameweek die tatsächlich gesetzten Aufstellungen (so5Fixture.mySo5Lineups)
samt Platz, Score und Rewards und bewertet sie:
  - Punkte / Plätze / Rewards je Team und GW
  - Ausfälle: aufgestellte Spieler ohne Einsatz (0 Minuten)
  - Kapitäns-Bilanz: Punkte, die der rückblickend beste Kapitän mehr gebracht
    hätte (Kapitänsbonus wird aus den Daten geschätzt)
  - Prognose vs. Ergebnis für die aufgestellten Spieler (aus
    logs/predictions.jsonl): Startquote und Projektion, getrennt nach
    Position × Spieltyp (Klub / Länderspiel)

Die Ausgabe (Default logs/lineup_review.json) enthält Account-Daten und ist
gitignored — sie lässt sich jederzeit neu aus der API erzeugen.

Usage:
    python3 lineup_review.py                 # letzte 4 GWs nach Deadline
    python3 lineup_review.py --last 8
    python3 lineup_review.py --gw 716        # nur eine GW
    python3 lineup_review.py --json ''       # ohne JSON-Datei
"""
import argparse
import datetime as dt
import json
import os
import statistics
import sys
from collections import defaultdict

from sorare_client import ensure_user_token, graphql

LOG = os.path.join("logs", "predictions.jsonl")
OUT = os.path.join("logs", "lineup_review.json")

FIXTURES_QUERY = """
query($n: Int!) { so5 { so5Fixtures(first: $n) {
  nodes { slug gameWeek aasmState startDate endDate } } } }
"""

LINEUPS_QUERY = """
query($s: String!) { so5 { so5Fixture(slug: $s) {
  slug gameWeek aasmState endDate
  mySo5Lineups {
    id name
    so5Leaderboard { slug displayName }
    so5Rankings { ranking score so5Rewards { aasmState coinAmount amount { eurCents } rewardCards { id } } }
    so5Appearances {
      captain score position
      playerGameScore {
        score
        anyGame { date homeTeam { __typename } }
        anyPlayerGameStats { ... on PlayerGameStats { minsPlayed gameStarted } }
      }
      anyCard { slug anyPlayer { slug displayName } }
    }
  } } } }
"""


def _dt(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def load_predictions(path):
    """{(player_slug, fixture): [log rows]} from the prediction log."""
    out = defaultdict(list)
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            out[(r.get("player_slug"), r.get("fixture"))].append(r)
    return out


def last_before(rows, kickoff):
    """The last prediction logged before kickoff (what we actually believed)."""
    ko = _dt(kickoff)
    rows = [r for r in rows if ko is None or _dt(r["ts"]) <= ko]
    return max(rows, key=lambda r: r["ts"]) if rows else None


def appearance_row(a, now):
    pgs = a.get("playerGameScore") or {}
    game = pgs.get("anyGame") or {}
    stats = pgs.get("anyPlayerGameStats") or {}
    when = _dt(game.get("date"))
    mins = stats.get("minsPlayed")
    finished = bool(when and when + dt.timedelta(hours=3) <= now)
    player = (a.get("anyCard") or {}).get("anyPlayer") or {}
    return {
        "player": player.get("displayName") or "?",
        "player_slug": player.get("slug"),
        "card": (a.get("anyCard") or {}).get("slug"),
        "pos": a.get("position"),
        "captain": bool(a.get("captain")),
        "raw": pgs.get("score"),
        "final": a.get("score"),
        "mins": mins,
        "started": stats.get("gameStarted"),
        "kickoff": game.get("date"),
        "game_type": "national" if (game.get("homeTeam") or {}).get("__typename") == "NationalTeam"
                     else ("club" if game else None),
        # no game in the window at all, or 0 minutes after the game is over
        "dnp": (not game and a.get("score") in (0, None)) or (finished and not mins),
        "pending": bool(when and not finished),
    }


def captain_multiplier(lineups):
    """Estimate the captain bonus from the data: (final/raw of captains) /
    (final/raw of the others) -- card bonuses cancel out. Fallback 1.5."""
    cap, other = [], []
    for l in lineups:
        for a in l["apps"]:
            if a["raw"] and a["final"]:
                (cap if a["captain"] else other).append(a["final"] / a["raw"])
    if len(cap) >= 3 and len(other) >= 10:
        return round(statistics.median(cap) / statistics.median(other), 2)
    return 1.5


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=4, help="Anzahl GWs (nach Deadline)")
    ap.add_argument("--gw", type=int, help="nur diese Gameweek")
    ap.add_argument("--log", default=LOG)
    ap.add_argument("--json", default=OUT, help="'' = keine Datei")
    args = ap.parse_args(argv)
    now = dt.datetime.now(dt.timezone.utc)

    if not ensure_user_token():
        sys.exit("Kein gültiger Sorare-Login (SORARE_ACCESS_TOKEN). Neu einloggen: "
                 "python3 sorare_client.py authurl -> Code -> "
                 "python3 sorare_client.py token <code>  (docs/oauth-setup.md)")

    nodes = graphql(FIXTURES_QUERY, {"n": max(args.last, 1) + 6})["data"]["so5"]["so5Fixtures"]["nodes"]
    locked = [n for n in nodes if _dt(n["endDate"]) and _dt(n["startDate"]) <= now]
    # startDate = deadline of that GW; locked GWs only (their lineups are final)
    if args.gw:
        locked = [n for n in locked if n["gameWeek"] == args.gw]
    else:
        locked = sorted(locked, key=lambda n: -n["gameWeek"])[:args.last]
    if not locked:
        sys.exit("Keine passende (gelockte) Gameweek gefunden.")

    preds = load_predictions(args.log)
    gws, all_lineups = [], []
    for n in sorted(locked, key=lambda n: n["gameWeek"]):
        fx = graphql(LINEUPS_QUERY, {"s": n["slug"]})["data"]["so5"]["so5Fixture"]
        lineups = []
        for l in fx["mySo5Lineups"] or []:
            rk = (l.get("so5Rankings") or [{}])[0]
            rewards = rk.get("so5Rewards") or []
            lineups.append({
                "competition": (l.get("so5Leaderboard") or {}).get("displayName") or l.get("name"),
                "rank": rk.get("ranking"), "score": rk.get("score") or 0.0,
                "rewards": len(rewards),
                "reward_eur": sum(((r.get("amount") or {}).get("eurCents") or 0) for r in rewards) / 100,
                "reward_cards": sum(len(r.get("rewardCards") or []) for r in rewards),
                "apps": [appearance_row(a, now) for a in l.get("so5Appearances") or []],
            })
        gws.append({"gw": fx["gameWeek"], "slug": fx["slug"], "state": fx["aasmState"],
                    "lineups": lineups})
        all_lineups += lineups

    cap_mult = captain_multiplier(all_lineups)
    print("================ GW-BILANZ (echte Aufstellungen) ================")
    print(f"Stand {now:%Y-%m-%d %H:%M} UTC | Kapitänsbonus geschätzt ×{cap_mult}")

    groups = defaultdict(lambda: {"n": 0, "err": [], "start": []})
    for g in gws:
        ls = g["lineups"]
        running = g["state"] != "closed"
        tot = sum(l["score"] for l in ls)
        dnps, pend, cap_loss = [], 0, 0.0
        for l in ls:
            for a in l["apps"]:
                pend += a["pending"]
                if a["dnp"]:
                    dnps.append(a["player"] + (" (C)" if a["captain"] else ""))
                # prediction vs outcome
                p = last_before(preds.get((a["player_slug"], g["slug"]), []), a["kickoff"])
                a["pred_start"] = p.get("start_prob") if p else None
                a["pred_proj"] = p.get("proj") if p else None
                if p and not a["pending"]:
                    key = f"{a['pos']}|{a['game_type']}"
                    grp = groups[key]
                    grp["n"] += 1
                    grp["start"].append((p.get("start_prob"), 1 if a["started"] else 0))
                    if a["mins"] and a["raw"] is not None and p.get("proj"):
                        grp["err"].append(p["proj"] - a["raw"])
            done = [a for a in l["apps"] if not a["pending"]]
            cap = next((a for a in l["apps"] if a["captain"]), None)
            if cap and done and not cap["pending"]:
                best = max(done, key=lambda a: a["raw"] or 0)
                l["captain"] = cap["player"]
                l["best_captain"] = best["player"]
                l["captain_loss"] = round(((best["raw"] or 0) - (cap["raw"] or 0)) * (cap_mult - 1), 1)
                cap_loss += l["captain_loss"]
        g.update({"total": round(tot, 1), "avg": round(tot / len(ls), 1) if ls else 0,
                  "dnp": dnps, "pending_games": pend, "captain_loss": round(cap_loss, 1)})

        state = " (läuft noch — vorläufig)" if running else ""
        print(f"\n## GW{g['gw']} {g['slug']}{state}: {len(ls)} Aufstellungen, Σ {tot:.0f}, "
              f"Ø {g['avg']:.0f} | Ausfälle {len(dnps)}"
              + (f": {', '.join(dnps)}" if dnps else "")
              + (f" | offene Spiele {pend}" if pend else "")
              + f" | Kapitäns-Verlust ~{cap_loss:.0f} P.")
        for l in sorted(ls, key=lambda l: -l["score"]):
            rw = (f"{l['rewards']} Reward(s)" + (f", {l['reward_eur']:.2f} €" if l["reward_eur"] else "")
                  + (f", {l['reward_cards']} Karte(n)" if l["reward_cards"] else "")) if l["rewards"] else "–"
            cap = (f"C {l['captain']}" + (f" (besser: {l['best_captain']}, −{l['captain_loss']:.0f})"
                                          if l.get("captain_loss", 0) > 0.5 else " ✓")) if l.get("captain") else ""
            print(f"  {l['competition'][:30]:<30} Platz {str(l['rank'] or '–'):>6}  {l['score']:6.1f}  "
                  f"{rw:<16} {cap}")

    if groups:
        print("\nPrognose vs. Ergebnis (aufgestellte Spieler, Position × Spieltyp):")
        print(f"  {'Gruppe':<24}{'n':>4}{'Ø Start-%':>10}{'real':>6}{'Proj-Bias':>11}{'MAE':>6}")
        for key, grp in sorted(groups.items(), key=lambda kv: -kv[1]["n"]):
            st = [s for s in grp["start"] if s[0] is not None]
            ps = sum(p for p, _ in st) / len(st) if st else None
            real = sum(y for _, y in st) / len(st) if st else None
            bias = sum(grp["err"]) / len(grp["err"]) if grp["err"] else None
            mae = sum(abs(e) for e in grp["err"]) / len(grp["err"]) if grp["err"] else None
            print(f"  {key:<24}{grp['n']:>4}"
                  f"{(f'{ps:.0%}' if ps is not None else '–'):>10}{(f'{real:.0%}' if real is not None else '–'):>6}"
                  f"{(f'{bias:+.1f}' if bias is not None else '–'):>11}{(f'{mae:.1f}' if mae is not None else '–'):>6}")
        print("  (Proj-Bias > 0 = überschätzt; Werte nur, wo eine Vorhersage im Log liegt)")
    else:
        print("\n(Keine Vorhersagen im Log für diese GWs — Prognose-Vergleich ab GW717.)")

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"updated": now.isoformat(), "captain_multiplier": cap_mult,
                       "gameweeks": gws,
                       "groups": {k: {"n": v["n"], "proj_err": v["err"], "start": v["start"]}
                                  for k, v in groups.items()}},
                      fh, ensure_ascii=False, indent=1)
        print(f"\nGeschrieben: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
