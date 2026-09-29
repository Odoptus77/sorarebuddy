#!/usr/bin/env python3
"""Injury & suspension feed from API-Football (api-sports.io, v3).

Fills the gap the Sorare API leaves: fixture-specific injury AND suspension
reports (incl. yellow-card bans), e.g. type "Missing Fixture" / "Questionable"
with reason "Suspended 3 matches" / "Knee Injury". lineup_suggest.py reads it
automatically when the host is reachable and falls back silently otherwise.

Key handling (never put the key in the repo or the chat):
  - preferred: a Claude Code cloud-environment API credential for
    v3.football.api-sports.io that attaches the `x-apisports-key` header
    after the request leaves the session (the key never enters it);
  - fallback: APIFOOTBALL_KEY in the environment / .env.local (gitignored).

Quota: the free plan allows ~100 requests/day. One request per calendar day of
the gameweek window, cached for CACHE_TTL_H hours in .cache/ (gitignored).

Usage:
    python3 injuries_feed.py status               # plan + requests used today
    python3 injuries_feed.py date 2026-10-01      # injuries/suspensions that day
    python3 injuries_feed.py selftest             # offline check of the matcher
"""
import datetime as dt
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from sorare_client import load_env

BASE = "https://v3.football.api-sports.io"
CACHE_DIR = os.path.join(".cache", "apifootball")
CACHE_TTL_H = 3
TIMEOUT = 30
KICKOFF_TOLERANCE = dt.timedelta(hours=36)   # injury row fixture vs our kickoff

# Words that carry no identity in club names ("SK Sturm Graz" == "Sturm Graz").
_TEAM_STOP = {"fc", "sc", "sk", "cf", "ac", "afc", "cd", "sv", "fk", "club",
              "de", "the", "calcio", "football", "futbol", "sad", "1"}


class FeedUnavailable(Exception):
    """Host blocked / key missing / quota or plan error -> caller falls back."""


class PlanRestricted(FeedUnavailable):
    """The plan doesn't cover this date/season. Verified 2026-09-29: the FREE
    plan serves current data only for fixtures from yesterday to tomorrow
    (and seasons 2022-2024 for league/season queries). Rejected calls do not
    count against the daily quota."""


def _norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    for ch in ".-'’,()":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def _get(path, params=None):
    load_env()
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    headers = {"User-Agent": "sorarebuddy/0.1", "Accept": "application/json"}
    key = os.environ.get("APIFOOTBALL_KEY")
    if key:                         # fallback path; the credential proxy wins
        headers["x-apisports-key"] = key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise FeedUnavailable(
            f"HTTP {exc.code} from {BASE} — host not allowed by the network "
            "policy or no API credential/key configured") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise FeedUnavailable(f"cannot reach {BASE}: {getattr(exc, 'reason', exc)}") from exc
    errs = data.get("errors")
    if errs:                        # api-sports reports auth/plan/quota errors here
        if isinstance(errs, dict) and "plan" in errs:
            raise PlanRestricted(errs["plan"])
        raise FeedUnavailable(f"API-Football error: {errs}")
    return data


def _cache_path(day):
    return os.path.join(CACHE_DIR, f"injuries_{day}.json")


def fetch_day(day, use_cache=True):
    """Raw /injuries rows for one calendar day (YYYY-MM-DD), cached."""
    path = _cache_path(day)
    if use_cache and os.path.exists(path):
        if time.time() - os.path.getmtime(path) < CACHE_TTL_H * 3600:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    rows, page = [], 1
    while True:
        params = {"date": day, "timezone": "UTC"}
        if page > 1:
            params["page"] = page
        data = _get("/injuries", params)
        rows.extend(data.get("response") or [])
        paging = data.get("paging") or {}
        if page >= (paging.get("total") or 1):
            break
        page += 1
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return rows


def _parse(row):
    p, t, f = row.get("player") or {}, row.get("team") or {}, row.get("fixture") or {}
    when = None
    if f.get("date"):
        try:
            when = dt.datetime.fromisoformat(f["date"].replace("Z", "+00:00"))
        except ValueError:
            when = None
    return {"name": p.get("name") or "", "type": p.get("type") or "",
            "reason": p.get("reason") or "", "team": t.get("name") or "",
            "fixture_id": f.get("id"), "when": when,
            "league": (row.get("league") or {}).get("name")}


def fetch_window(ws, we):
    """(rows, skipped_days) for every calendar day of [ws, we]. Days the plan
    doesn't cover (free plan: only yesterday..tomorrow) are skipped, not fatal;
    a real outage (host/key/quota) still raises FeedUnavailable."""
    out, skipped, seen, day = [], [], set(), ws.date()
    while day <= we.date():
        try:
            for r in map(_parse, fetch_day(day.isoformat())):
                # adjacent day queries can return the same late-night fixture
                key = (r["fixture_id"], _norm(r["name"]), r["type"])
                if key not in seen:
                    seen.add(key)
                    out.append(r)
        except PlanRestricted:
            skipped.append(day.isoformat())
        day += dt.timedelta(days=1)
    return out, skipped


def name_matches(api_name, display_name):
    """API-Football names come as 'Leo Baptistao', 'M. Svidersky',
    'R. de Tomas' or a single 'Marcao'; Sorare uses the display name."""
    a, s = _norm(api_name).split(), _norm(display_name).split()
    if not a or not s:
        return False
    if a == s:
        return True
    if len(a[0]) == 1 and len(a) >= 2:            # initial + surname
        sur = a[1:]
        return len(s) > len(sur) and s[-len(sur):] == sur and s[0][0] == a[0]
    if len(a) == 1:                               # mononym
        return a[0] in s
    return a[0] == s[0] and a[-1] == s[-1]        # first + last (middle names)


def team_matches(api_team, our_team):
    a = {w for w in _norm(api_team).split() if w not in _TEAM_STOP}
    b = {w for w in _norm(our_team).split() if w not in _TEAM_STOP}
    return bool(a and b) and (a <= b or b <= a)


def lookup(rows, display_name, team_name, kickoff):
    """The single injury row for this player & game, or None (no/ambiguous)."""
    try:
        ko = dt.datetime.fromisoformat(kickoff.replace("Z", "+00:00")) if kickoff else None
    except ValueError:
        ko = None
    hits = [r for r in rows
            if name_matches(r["name"], display_name)
            and team_matches(r["team"], team_name or "")
            and (ko is None or r["when"] is None or abs(r["when"] - ko) <= KICKOFF_TOLERANCE)]
    if len({_norm(r["name"]) for r in hits}) != 1:   # none, or two players match
        return None
    # the same player can appear twice (e.g. injury + suspension): worst wins
    return sorted(hits, key=lambda r: r["type"] != "Missing Fixture")[0]


def is_intl_duty(row):
    """API-Football lists national call-ups as 'Missing Fixture' with reason
    'International duty' -- for ANY confederation, i.e. also the non-UEFA
    call-ups (Gabon/Korea/Jamaica ...) that Sorare's API can't see."""
    return "international" in (row.get("reason") or "").lower()


def is_suspension(row):
    r = (row.get("reason") or "").lower()
    return any(w in r for w in ("suspend", "card", "ban"))


def _selftest():
    rows = [_parse(x) for x in [
        {"player": {"name": "M. Svidersky", "type": "Missing Fixture", "reason": "Knee Injury"},
         "team": {"name": "SK Sturm Graz"}, "fixture": {"id": 1, "date": "2026-10-03T15:00:00+00:00"}},
        {"player": {"name": "R. de Tomas", "type": "Missing Fixture", "reason": "Suspended 1 match"},
         "team": {"name": "Rayo Vallecano"}, "fixture": {"id": 2, "date": "2026-10-03T19:00:00+00:00"}},
        {"player": {"name": "Marcao", "type": "Questionable", "reason": "Muscle Injury"},
         "team": {"name": "Sevilla FC"}, "fixture": {"id": 3, "date": "2026-10-04T19:00:00+00:00"}},
        {"player": {"name": "A. Martin", "type": "Missing Fixture", "reason": "Yellow Cards"},
         "team": {"name": "Getafe CF"}, "fixture": {"id": 4, "date": "2026-10-04T12:00:00+00:00"}},
    ]]
    cases = [
        ("Max Svidersky", "Sturm Graz", "2026-10-03T15:00:00Z", "Knee Injury"),
        ("Raúl de Tomás", "Rayo Vallecano", "2026-10-03T19:00:00Z", "Suspended 1 match"),
        ("Marcão", "Sevilla", "2026-10-04T19:00:00Z", "Muscle Injury"),
        ("Álex Martín", "Getafe", "2026-10-04T12:00:00Z", "Yellow Cards"),
        ("Max Svidersky", "Sturm Graz", "2026-10-10T15:00:00Z", None),   # other game
        ("Mario Svidersky", "Rapid Wien", "2026-10-03T15:00:00Z", None), # other club
        ("Moritz Oswald", "Sturm Graz", "2026-10-03T15:00:00Z", None),   # other player
    ]
    ok = True
    for name, team, ko, want in cases:
        got = lookup(rows, name, team, ko)
        got = got["reason"] if got else None
        flag = "OK " if got == want else "FAIL"
        ok &= got == want
        print(f"  {flag} {name:<16} {team:<15} -> {got}")
    print("selftest", "passed" if ok else "FAILED")
    return ok


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "selftest":
        return 0 if _selftest() else 1
    try:
        if cmd == "status":
            r = (_get("/status").get("response") or {})
            sub, req = r.get("subscription") or {}, r.get("requests") or {}
            print(f"Plan: {sub.get('plan')} (aktiv: {sub.get('active')}, bis {sub.get('end')})")
            print(f"Requests heute: {req.get('current')} / {req.get('limit_day')}")
            return 0
        if cmd == "date" and len(argv) > 1:
            rows = [_parse(r) for r in fetch_day(argv[1], use_cache=False)]
            print(f"{len(rows)} Einträge am {argv[1]}")
            for r in rows[:60]:
                kind = "SPERRE" if is_suspension(r) else "Verletzung"
                print(f"  {r['type']:<15} {kind:<10} {r['name']:<22} {r['team']:<22} {r['reason']}")
            return 0
    except FeedUnavailable as exc:
        print(f"API-Football nicht verfügbar: {exc}", file=sys.stderr)
        return 2
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
