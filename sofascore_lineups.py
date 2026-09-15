#!/usr/bin/env python3
"""Fetch predicted / confirmed starting XIs from SofaScore.

SofaScore exposes the (voraussichtliche) lineup for a match via an
undocumented public JSON API. When the lineup is not yet official the payload
carries ``confirmed: false`` -- that is the *predicted* XI; once the teamsheet
drops it flips to ``confirmed: true``. Predicted XIs typically appear ~1-2 days
before kickoff, confirmed ones ~1h before.

This module is dependency-free and defensive: every network call is wrapped so
a blocked egress policy (HTTP 403 tunnel) or a missing lineup simply yields
"no data", and the caller falls back to its own model.

Requires the environment network policy to allow the website
``api.sofascore.com`` (no API key needed). See docs/network-setup.md.

CLI (once the domain is allowed):
    python3 sofascore_lineups.py "Real Madrid"      # show next-match XI
    python3 sofascore_lineups.py --ping             # connectivity check
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

BASE = "https://api.sofascore.com/api/v1"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PACE = 0.4
CACHE_DIR = os.environ.get("SORAREBUDDY_CACHE", ".")
_TEAM_CACHE = os.path.join(CACHE_DIR, "sofa_teams.json")


def _norm(s):
    """Accent-fold + lowercase + strip non-alphanumerics for name matching."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _get(path):
    url = BASE + path
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json",
        "Referer": "https://www.sofascore.com/",
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def ping():
    try:
        _get("/sport/football/events/live")
        return True
    except Exception as e:
        print(f"SofaScore unreachable: {type(e).__name__}: {str(e)[:160]}",
              file=sys.stderr)
        return False


def _load_team_cache():
    try:
        with open(_TEAM_CACHE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_team_cache(c):
    try:
        with open(_TEAM_CACHE, "w", encoding="utf-8") as fh:
            json.dump(c, fh, ensure_ascii=False)
    except Exception:
        pass


def search_team(name, cache=None):
    """Return a SofaScore team id for a club name (best match), or None."""
    if cache is None:
        cache = _load_team_cache()
    key = _norm(name)
    if key in cache:
        return cache[key]
    tid = None
    try:
        d = _get("/search/all?q=" + urllib.parse.quote(name))
        results = d.get("results") or []
        cands = []
        for r in results:
            if r.get("type") == "team":
                ent = r.get("entity") or {}
                if (ent.get("sport") or {}).get("name", "Football") == "Football" or True:
                    cands.append(ent)
        # exact normalized match first, else first football team
        best = None
        for ent in cands:
            if _norm(ent.get("name")) == key or _norm(ent.get("shortName")) == key:
                best = ent
                break
        if best is None and cands:
            best = cands[0]
        if best:
            tid = best.get("id")
    except Exception as e:
        print(f"  search '{name}' failed: {type(e).__name__}", file=sys.stderr)
    cache[key] = tid
    _save_team_cache(cache)
    time.sleep(PACE)
    return tid


def _next_event(team_id):
    try:
        d = _get(f"/team/{team_id}/events/next/0")
        evs = d.get("events") or []
        return evs[0] if evs else None
    except Exception:
        return None


def _event_lineups(event_id):
    try:
        return _get(f"/event/{event_id}/lineups")
    except Exception:
        return None


def team_xi(team_id):
    """Return (confirmed: bool|None, {norm_name: started_bool}, meta) for the
    team's next match, or (None, {}, {}) if no lineup is available yet."""
    ev = _next_event(team_id)
    if not ev:
        return None, {}, {}
    home = (ev.get("homeTeam") or {}).get("id")
    away = (ev.get("awayTeam") or {}).get("id")
    side = "home" if team_id == home else ("away" if team_id == away else None)
    if side is None:
        return None, {}, {}
    lu = _event_lineups(ev.get("id"))
    time.sleep(PACE)
    if not lu or side not in lu:
        return None, {}, {"event": ev.get("id")}
    confirmed = bool(lu.get("confirmed"))
    players = (lu.get(side) or {}).get("players") or []
    out = {}
    for p in players:
        pl = p.get("player") or {}
        nm = _norm(pl.get("name") or pl.get("shortName"))
        if not nm:
            continue
        started = not bool(p.get("substitute"))
        out[nm] = started
    meta = {"event": ev.get("id"),
            "opponent": (ev.get("awayTeam") if side == "home" else ev.get("homeTeam") or {}).get("name")}
    return confirmed, out, meta


def build_club_index(club_names, verbose=True):
    """Map each club name -> {'confirmed':bool|None, 'players':{norm:started},
    'opponent':str}. Clubs without an available lineup get an empty players
    dict. Team-id lookups are cached to disk across runs."""
    cache = _load_team_cache()
    index = {}
    uniq = sorted({c for c in club_names if c})
    for i, name in enumerate(uniq, 1):
        tid = search_team(name, cache)
        if not tid:
            index[name] = {"confirmed": None, "players": {}, "opponent": None}
            continue
        confirmed, players, meta = team_xi(tid)
        index[name] = {"confirmed": confirmed, "players": players,
                       "opponent": meta.get("opponent")}
        if verbose:
            state = ("confirmed" if confirmed else "predicted") if players else "no lineup"
            print(f"  [{i}/{len(uniq)}] {name}: {state} "
                  f"({sum(1 for v in players.values() if v)} starters)", file=sys.stderr)
    return index


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    if argv[0] == "--ping":
        print("OK" if ping() else "UNREACHABLE")
        return
    name = argv[0]
    tid = search_team(name)
    if not tid:
        print(f"No team found for '{name}'")
        return
    print(f"team id: {tid}")
    confirmed, players, meta = team_xi(tid)
    if not players:
        print("No lineup available yet for the next match.")
        return
    print(f"next vs {meta.get('opponent')} — {'CONFIRMED' if confirmed else 'PREDICTED'} XI:")
    for nm, started in sorted(players.items(), key=lambda x: (not x[1], x[0])):
        print(f"  {'START' if started else 'bench'}  {nm}")


if __name__ == "__main__":
    main(sys.argv[1:])
