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
Reachable from the Claude Code cloud container since at least 2026-10-07
(lineup_suggest.py uses it by default; ``--no-sofascore`` turns it off).

Team ids and fetched XIs are cached on disk (``.cache/``; XIs for
XI_TTL seconds) so back-to-back optimizer runs don't hammer the API.

CLI:
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
CACHE_DIR = os.environ.get("SORAREBUDDY_CACHE", ".cache")
_TEAM_CACHE = os.path.join(CACHE_DIR, "sofa_teams.json")
_XI_CACHE = os.path.join(CACHE_DIR, "sofa_xi.json")
XI_TTL = 30 * 60   # seconds; a predicted XI rarely changes within half an hour


# letters NFKD does not decompose (Groß/Gross, Sørloth, Łukasz ...)
_TRANS = str.maketrans({"ß": "ss", "æ": "ae", "ø": "o", "œ": "oe", "ł": "l",
                        "đ": "d", "ð": "d", "þ": "th", "ı": "i"})


def _norm(s):
    """Accent-fold + lowercase + strip non-alphanumerics for name matching."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s.lower().translate(_TRANS))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s)


# Sponsor / legal / city tokens that make Sorare's long club names miss on
# SofaScore ("SK Puntigamer Sturm Graz" -> "Sturm Graz", "Trabzonspor Kulübü"
# -> "Trabzonspor", "Kieler SV Holstein 1900" -> "Holstein").
_STOP = {"spor", "kulubu", "calcio", "sv", "sk", "fc", "cs", "cf", "ac", "ca", "sc", "cd",
         "ud", "de", "futbol", "bergamasca", "puntigamer", "tumosan", "yeni", "deportivo",
         "funchal", "kieler", "1900", "1895", "1902", "club", "clube"}
_ALIASES = {"fcinternazionalemilano": "Inter",
            "realsociedaddefutboliisanse": "Real Sociedad B"}


def _candidates(name):
    """Search strings to try for a Sorare team name, most specific first."""
    out = [name]
    alias = _ALIASES.get(_norm(name))
    if alias:
        out.append(alias)
    toks = [t for t in name.split() if _norm(t) and _norm(t) not in _STOP]
    stripped = " ".join(toks)
    if stripped and stripped != name:
        out.append(stripped)
    if len(toks) >= 2:                      # "N.E.C. Nijmegen" -> "Nijmegen"
        for t in (toks[-1], toks[0]):
            if len(_norm(t)) >= 6 and t not in out:
                out.append(t)
    return out


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


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_json(path, obj):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False)
    except Exception:
        pass


def _load_team_cache():
    return _load_json(_TEAM_CACHE)


def _save_team_cache(c):
    _save_json(_TEAM_CACHE, c)


def search_team(name, cache=None):
    """Return a SofaScore team id for a club name (best match), or None."""
    if cache is None:
        cache = _load_team_cache()
    key = _norm(name)
    if cache.get(key):
        return cache[key]
    tid = None
    for q in _candidates(name):
        try:
            d = _get("/search/all?q=" + urllib.parse.quote(q))
            # men's teams only: "RCD Espanyol de Barcelona" is SofaScore's name
            # for the WOMEN's side (gender F), the men play as "Espanyol"
            cands = [(r.get("entity") or {}) for r in (d.get("results") or [])
                     if r.get("type") == "team"
                     and (r.get("entity") or {}).get("gender") != "F"]
        except Exception as e:
            print(f"  search '{q}' failed: {type(e).__name__}", file=sys.stderr)
            cands = []
        time.sleep(PACE)
        if not cands:
            continue
        # exact normalized match (on the Sorare name or this query) first,
        # else the first team SofaScore ranks for the query
        qk = _norm(q)
        best = next((ent for ent in cands
                     if _norm(ent.get("name")) in (key, qk)
                     or _norm(ent.get("shortName")) in (key, qk)), cands[0])
        tid = best.get("id")
        if tid:
            break
    if tid:                                  # misses are retried next run
        cache[key] = tid
        _save_team_cache(cache)
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


def team_xi(team_id, xi_cache=None):
    """Return (confirmed: bool|None, {norm_name: started_bool}, meta) for the
    team's next match, or (None, {}, {}) if no lineup is available yet.
    meta carries the event id, opponent name and ``start`` (unix ts) so the
    caller can make sure it is the SAME game it plans for. Results are cached
    for XI_TTL seconds when ``xi_cache`` (a dict) is given."""
    key = str(team_id)
    if xi_cache is not None:
        hit = xi_cache.get(key)
        if hit and time.time() - hit.get("ts", 0) < XI_TTL:
            return hit["confirmed"], hit["players"], hit["meta"]
    ev = _next_event(team_id)
    if not ev:
        return None, {}, {}
    home = (ev.get("homeTeam") or {}).get("id")
    away = (ev.get("awayTeam") or {}).get("id")
    side = "home" if team_id == home else ("away" if team_id == away else None)
    if side is None:
        return None, {}, {}
    meta = {"event": ev.get("id"), "start": ev.get("startTimestamp"),
            "opponent": ((ev.get("awayTeam") if side == "home" else ev.get("homeTeam")) or {}).get("name")}
    lu = _event_lineups(ev.get("id"))
    time.sleep(PACE)
    if not lu or side not in lu:
        res = (None, {}, meta)
    else:
        confirmed = bool(lu.get("confirmed"))
        out = {}
        for p in (lu.get(side) or {}).get("players") or []:
            pl = p.get("player") or {}
            nm = _norm(pl.get("name") or pl.get("shortName"))
            if nm:
                out[nm] = not bool(p.get("substitute"))
        res = (confirmed, out, meta)
    if xi_cache is not None:
        xi_cache[key] = {"ts": time.time(), "confirmed": res[0],
                         "players": res[1], "meta": res[2]}
    return res


def build_club_index(club_names, verbose=True):
    """Map each team name -> {'confirmed':bool|None, 'players':{norm:started},
    'opponent':str, 'start': unix ts|None, 'found': bool}. Teams without an
    available lineup get an empty players dict. Team ids are cached to disk
    across runs, fetched XIs for XI_TTL seconds."""
    cache = _load_team_cache()
    xi_cache = _load_json(_XI_CACHE)
    index = {}
    uniq = sorted({c for c in club_names if c})
    for i, name in enumerate(uniq, 1):
        tid = search_team(name, cache)
        if not tid:
            index[name] = {"confirmed": None, "players": {}, "opponent": None,
                           "start": None, "found": False}
            continue
        confirmed, players, meta = team_xi(tid, xi_cache)
        index[name] = {"confirmed": confirmed, "players": players,
                       "opponent": meta.get("opponent"), "start": meta.get("start"),
                       "found": True}
        if verbose:
            state = ("confirmed" if confirmed else "predicted") if players else "no lineup"
            print(f"  [{i}/{len(uniq)}] {name}: {state} "
                  f"({sum(1 for v in players.values() if v)} starters)", file=sys.stderr)
    _save_json(_XI_CACHE, xi_cache)
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
