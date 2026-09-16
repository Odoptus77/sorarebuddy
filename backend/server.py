#!/usr/bin/env python3
"""Tiny dependency-free HTTP API in front of the sorarebuddy pipeline.

The heavy lifting (Sorare fetch + club valuation + reward attribution + the
max-profit lineup optimiser with the Startelf score) stays in the existing
Python scripts. This server just runs them on demand, caches the JSON, and
serves it to the SwiftUI app so the Sorare API key never leaves the server.

Endpoints (all return JSON):
    GET /health                                  -> {"ok": true}
    GET /api/club?slug=nicktd7&rarities=limited,rare
    GET /api/rewards?slug=nicktd7
    GET /api/lineups?slug=nicktd7&rarities=limited,rare
    GET /api/bundle?slug=nicktd7                 -> {club, rewards, lineups}

Auth (optional but recommended when deployed): set APP_TOKEN and the app must
send  Authorization: Bearer <APP_TOKEN>.

Caching: results are cached on disk per (endpoint, params) with a TTL
(CACHE_TTL seconds, default 1800). A stale entry is served immediately while a
fresh copy is computed in the background, so the app stays responsive even
though a cold fetch takes 1-2 minutes.

Config via environment:
    SORARE_API_KEY   the Sorare key (required on a real server; here the proxy
                     injects it, so it may be unset locally)
    APP_TOKEN        shared secret the app must present (optional)
    PORT             listen port (default 8080)
    CACHE_TTL        seconds a cache entry stays fresh (default 1800)
    CACHE_DIR        where to store cached JSON (default backend/cache)
    DEFAULT_SLUG     manager slug used when a request omits ?slug=

Run:
    SORARE_API_KEY=... python3 backend/server.py
"""
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.environ.get("CACHE_DIR", os.path.join(os.path.dirname(__file__), "cache"))
CACHE_TTL = int(os.environ.get("CACHE_TTL", "1800"))
APP_TOKEN = os.environ.get("APP_TOKEN", "")
DEFAULT_SLUG = os.environ.get("DEFAULT_SLUG", "")
PORT = int(os.environ.get("PORT", "8080"))
JOB_TIMEOUT = int(os.environ.get("JOB_TIMEOUT", "600"))

os.makedirs(CACHE_DIR, exist_ok=True)
_locks = {}
_locks_guard = threading.Lock()


def _lock_for(key):
    with _locks_guard:
        lk = _locks.get(key)
        if lk is None:
            lk = _locks[key] = threading.Lock()
        return lk


def _cache_path(key):
    h = hashlib.sha1(key.encode()).hexdigest()[:16]
    return os.path.join(CACHE_DIR, h + ".json")


def _read_cache(key):
    p = _cache_path(key)
    try:
        st = os.stat(p)
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data, (time.time() - st.st_mtime)
    except Exception:
        return None, None


def _write_cache(key, data):
    p = _cache_path(key)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(tmp, p)


def _run_script(script, slug, extra=None):
    """Run a pipeline script that writes JSON to a temp file; return the parsed
    JSON. Raises on failure."""
    out = os.path.join(CACHE_DIR, f"_tmp_{script}_{os.getpid()}_{threading.get_ident()}.json")
    cmd = [sys.executable, os.path.join(ROOT, script), slug, "--json", out]
    if extra:
        cmd += extra
    env = dict(os.environ)
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                          text=True, timeout=JOB_TIMEOUT)
    if proc.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"{script} failed (rc={proc.returncode}): "
                           f"{proc.stderr[-500:]}")
    try:
        with open(out, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    finally:
        try:
            os.remove(out)
        except OSError:
            pass
    return data


def _producer(kind, slug, rarities):
    if kind == "club":
        return _run_script("club_overview.py", slug, ["--rarities", rarities])
    if kind == "rewards":
        return _run_script("rewards_by_player.py", slug)
    if kind == "lineups":
        return _run_script("lineup_suggest.py", slug, ["--rarities", rarities])
    raise ValueError(kind)


def get_data(kind, slug, rarities, force=False):
    """Return (data, age_seconds). Serves fresh cache directly; serves stale
    while refreshing in the background; blocks only on a cold miss.
    force=True skips the cache and recomputes now (single-flight)."""
    key = f"{kind}|{slug}|{rarities}"
    if force:
        lk = _lock_for(key)
        with lk:
            fresh = _producer(kind, slug, rarities)
            _write_cache(key, fresh)
            return fresh, 0.0
    data, age = _read_cache(key)
    if data is not None and age is not None and age < CACHE_TTL:
        return data, age

    if data is not None:
        # stale: refresh in background, serve stale now
        def _bg():
            lk = _lock_for(key)
            if not lk.acquire(blocking=False):
                return
            try:
                fresh = _producer(kind, slug, rarities)
                _write_cache(key, fresh)
            except Exception as e:
                sys.stderr.write(f"[bg refresh {key}] {e}\n")
            finally:
                lk.release()
        threading.Thread(target=_bg, daemon=True).start()
        return data, age

    # cold miss: block (single-flight via lock)
    lk = _lock_for(key)
    with lk:
        data, age = _read_cache(key)          # another thread may have filled it
        if data is not None and age is not None and age < CACHE_TTL:
            return data, age
        fresh = _producer(kind, slug, rarities)
        _write_cache(key, fresh)
        return fresh, 0.0


class Handler(BaseHTTPRequestHandler):
    server_version = "sorarebuddy/1.0"

    def _send(self, code, obj, cache_age=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if cache_age is not None:
            self.send_header("X-Cache-Age", str(int(cache_age)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _authok(self):
        if not APP_TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {APP_TOKEN}"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path.rstrip("/") or "/"
        if path == "/health":
            return self._send(200, {"ok": True, "ttl": CACHE_TTL})
        if not self._authok():
            return self._send(401, {"error": "unauthorized"})
        q = parse_qs(u.query)
        slug = (q.get("slug", [DEFAULT_SLUG])[0] or "").strip().lower()
        rarities = (q.get("rarities", ["limited,rare"])[0] or "limited,rare").strip()
        force = (q.get("refresh", q.get("force", ["0"]))[0] or "0").lower() in ("1", "true", "yes")
        if not slug:
            return self._send(400, {"error": "missing slug"})
        try:
            if path == "/api/club":
                data, age = get_data("club", slug, rarities, force)
                return self._send(200, data, age)
            if path == "/api/rewards":
                data, age = get_data("rewards", slug, rarities, force)
                return self._send(200, data, age)
            if path == "/api/lineups":
                data, age = get_data("lineups", slug, rarities, force)
                return self._send(200, data, age)
            if path == "/api/bundle":
                club, a1 = get_data("club", slug, rarities, force)
                rewards, a2 = get_data("rewards", slug, rarities, force)
                lineups, a3 = get_data("lineups", slug, rarities, force)
                return self._send(200, {"club": club, "rewards": rewards,
                                        "lineups": lineups},
                                  max(a1 or 0, a2 or 0, a3 or 0))
        except subprocess.TimeoutExpired:
            return self._send(504, {"error": "pipeline timeout"})
        except Exception as e:
            return self._send(500, {"error": str(e)[:400]})
        return self._send(404, {"error": "not found"})

    do_HEAD = do_GET


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    sys.stderr.write(f"sorarebuddy backend on :{PORT}  (ttl={CACHE_TTL}s, "
                     f"auth={'on' if APP_TOKEN else 'off'})\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
