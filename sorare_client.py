#!/usr/bin/env python3
"""Minimal, dependency-free client for the Sorare GraphQL API.

Reads the API key from the environment (SORARE_API_KEY) or from a local
.env.local file. Never hard-code the key in this file.

Public data (no login needed):
    python3 sorare_client.py ping                          # check connectivity
    python3 sorare_client.py player kylian-mbappe-lottin   # look up by slug
    python3 sorare_client.py query '{ players(slugs: ["kylian-mbappe-lottin"]) { displayName } }'

Your own account (OAuth login required -- see docs/oauth-setup.md):
    python3 sorare_client.py authurl        # print the Sorare authorize URL
    python3 sorare_client.py token <code>   # exchange ?code= for tokens -> .env.local
    python3 sorare_client.py refresh        # new access token via SORARE_REFRESH_TOKEN
    python3 sorare_client.py me             # who am I (needs SORARE_ACCESS_TOKEN)
    python3 sorare_client.py tokenfile <path>  # copy tokens to a file for env settings

Tokens are written to .env.local (gitignored, mode 600) and NEVER printed, so
they can't leak into a chat transcript or log. An expired/invalid token never
breaks the public-data scripts: on HTTP 401 the request is retried without it.

The API key is sent in the `APIKEY` header, as required by Sorare. When
SORARE_ACCESS_TOKEN is set, an `Authorization: Bearer` header is added so
requests run on behalf of the logged-in user.
Docs: https://developers.sorare.com/  and  https://github.com/sorare/api
"""
import calendar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPHQL_ENDPOINT = "https://api.sorare.com/graphql"
OAUTH_AUTHORIZE_URL = "https://sorare.com/oauth/authorize"
OAUTH_TOKEN_URL = "https://api.sorare.com/oauth/token"
DEFAULT_REDIRECT_URI = "http://localhost:3000/auth/sorare/callback"


def load_env(path=".env.local"):
    """Load KEY=VALUE lines from a local env file into os.environ.

    Values already set in the real environment take precedence and are
    not overwritten.
    """
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_ENV_LOADED = False


def _ensure_env():
    """Load .env.local once so importers get the key without each remembering.

    Scripts that call graphql() directly (lineup_suggest, rewards_by_player,
    ...) would otherwise run without SORARE_API_KEY -- dropping to the low
    (500) complexity limit instead of the 30000 an API key grants. Real
    environment values still win (load_env uses setdefault).
    """
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_env()
        _ENV_LOADED = True


def _token_rejected(result):
    errs = result.get("errors") or []
    return any(str(e.get("message", "")).startswith("Unauthorized") for e in errs)


def _drop_token(headers, payload):
    """Retry without the user token so public-data scripts keep working."""
    headers.pop("Authorization", None)
    os.environ.pop("SORARE_ACCESS_TOKEN", None)          # warn only once
    print("WARN: SORARE_ACCESS_TOKEN abgelehnt (abgelaufen?) -- weiter ohne. "
          "Erneuern: python3 sorare_client.py refresh", file=sys.stderr)
    return urllib.request.Request(
        GRAPHQL_ENDPOINT, data=payload, headers=headers, method="POST")


def graphql(query, variables=None, retries=3, timeout=45):
    """Execute a GraphQL request and return the parsed JSON response.

    The API key is optional here: if SORARE_API_KEY is set we send it in the
    APIKEY header ourselves. If it is not set, we send no key and rely on the
    request being enriched upstream -- e.g. a Claude Code cloud environment
    "API credential" that attaches the APIKEY header for api.sorare.com after
    the request leaves the session's VM. That way the key never has to live
    in the repo or the session at all.

    Transient network errors (timeouts, dropped connections) are retried with
    exponential backoff before giving up.
    """
    _ensure_env()
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "sorarebuddy/0.1",
    }
    api_key = os.environ.get("SORARE_API_KEY")
    if api_key:
        headers["APIKEY"] = api_key
    access_token = os.environ.get("SORARE_ACCESS_TOKEN")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = urllib.request.Request(
        GRAPHQL_ENDPOINT, data=payload, headers=headers, method="POST"
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
            # A bad/expired token comes back as HTTP 200 + "Unauthorized" error.
            if "Authorization" in headers and _token_rejected(result):
                req = _drop_token(headers, payload)
                continue
            return result
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            if exc.code == 401 and "Authorization" in headers:
                req = _drop_token(headers, payload)
                continue
            # 429/5xx are worth retrying; other HTTP errors are terminal.
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                last_err = f"HTTP {exc.code}"
                time.sleep(2 ** attempt)
                continue
            sys.exit(f"HTTP {exc.code} from Sorare API:\n{body}")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = getattr(exc, "reason", exc)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            sys.exit(
                f"Network error reaching {GRAPHQL_ENDPOINT}: {last_err}\n"
                "If you are on Claude Code on the web, the environment's network "
                "policy may block api.sorare.com. Run this locally or use an "
                "environment whose egress policy allows it."
            )


# --- Convenience queries -------------------------------------------------

PING_QUERY = "{ currentUser { nickname } }"

PLAYER_QUERY = """
query Player($slugs: [String!]) {
  players(slugs: $slugs) {
    slug
    displayName
    anyPositions
    activeClub { name }
  }
}
"""


def cmd_ping():
    print(json.dumps(graphql(PING_QUERY), indent=2, ensure_ascii=False))


def cmd_player(slug):
    # Sorare looks players up by slug (e.g. "kylian-mbappe-lottin"), not by
    # free-text name. Pass one or more comma-separated slugs.
    slugs = [s.strip() for s in slug.split(",") if s.strip()]
    print(json.dumps(graphql(PLAYER_QUERY, {"slugs": slugs}), indent=2, ensure_ascii=False))


def cmd_query(query):
    print(json.dumps(graphql(query), indent=2, ensure_ascii=False))


# --- OAuth (login on behalf of a user) -----------------------------------

def _require_env(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: {name} is not set (see docs/oauth-setup.md).")
    return value


def cmd_authurl():
    """Print the URL the user opens in a browser to authorize the app."""
    client_id = _require_env("SORARE_CLIENT_ID")
    redirect_uri = os.environ.get("SORARE_REDIRECT_URI", DEFAULT_REDIRECT_URI)
    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "",
        }
    )
    print(f"{OAUTH_AUTHORIZE_URL}?{params}")
    print(
        "\nOpen this in your browser, authorize, then copy the `code` value from "
        "the callback URL and run:  python3 sorare_client.py token <code>",
        file=sys.stderr,
    )


def _save_env(values, path=".env.local"):
    """Upsert KEY=VALUE lines in the gitignored env file (mode 600)."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines()
                     if l.partition("=")[0].strip() not in values]
    lines += [f"{k}={v}" for k, v in values.items()]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)
    os.environ.update(values)


def _token_request(fields, out=sys.stdout):
    """POST to the token endpoint; store tokens, print only non-secret info."""
    data = urllib.parse.urlencode(dict(fields,
        client_id=_require_env("SORARE_CLIENT_ID"),
        client_secret=_require_env("SORARE_CLIENT_SECRET"))).encode()
    req = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "sorarebuddy/0.1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        # error bodies carry only error/error_description, no tokens
        sys.exit(f"HTTP {exc.code} from token endpoint: {exc.read().decode(errors='replace')[:300]}")
    if "access_token" not in result:
        sys.exit(f"No access_token in response (fields: {sorted(result)})")
    values = {"SORARE_ACCESS_TOKEN": result["access_token"]}
    if result.get("refresh_token"):
        values["SORARE_REFRESH_TOKEN"] = result["refresh_token"]
    exp = result.get("expires_in")
    if exp:
        values["SORARE_ACCESS_TOKEN_EXPIRES"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + int(exp)))
    _save_env(values)
    print(f"OK: {', '.join(sorted(values))} in .env.local gespeichert (nicht angezeigt).", file=out)
    if exp:
        print(f"Access-Token gültig bis {values['SORARE_ACCESS_TOKEN_EXPIRES']} "
              f"(~{int(exp) // 86400} Tage), scope: {result.get('scope')!r}", file=out)


def ensure_user_token(margin_s=600):
    """True if a usable OAuth user token is set. Renews it quietly via the
    stored refresh token when it expires within `margin_s` seconds (Sorare
    access tokens live ~1 day; each refresh rotates the refresh token)."""
    load_env()
    if not os.environ.get("SORARE_ACCESS_TOKEN") and not os.environ.get("SORARE_REFRESH_TOKEN"):
        return False
    exp = os.environ.get("SORARE_ACCESS_TOKEN_EXPIRES")
    due = not os.environ.get("SORARE_ACCESS_TOKEN")
    if exp:
        try:
            due = due or calendar.timegm(time.strptime(exp, "%Y-%m-%dT%H:%M:%SZ")) \
                < time.time() + margin_s
        except ValueError:
            pass
    if due:
        if not (os.environ.get("SORARE_REFRESH_TOKEN") and os.environ.get("SORARE_CLIENT_ID")
                and os.environ.get("SORARE_CLIENT_SECRET")):
            return False
        try:
            _token_request({"refresh_token": os.environ["SORARE_REFRESH_TOKEN"],
                            "grant_type": "refresh_token"}, out=sys.stderr)
        except SystemExit as exc:          # _token_request exits on HTTP errors
            print(f"WARN: Token-Erneuerung fehlgeschlagen: {exc}", file=sys.stderr)
            return False
    return bool(os.environ.get("SORARE_ACCESS_TOKEN"))


def cmd_token(code):
    """Exchange the authorization code for access + refresh tokens."""
    _token_request({"code": code, "grant_type": "authorization_code",
                    "redirect_uri": os.environ.get("SORARE_REDIRECT_URI", DEFAULT_REDIRECT_URI)})


def cmd_refresh():
    """Get a fresh access token with the stored refresh token."""
    _token_request({"refresh_token": _require_env("SORARE_REFRESH_TOKEN"),
                    "grant_type": "refresh_token"})


def cmd_tokenfile(path):
    """Write the token lines to a file (for pasting into the environment's
    variables in the settings UI) -- without printing them."""
    keys = ("SORARE_ACCESS_TOKEN", "SORARE_REFRESH_TOKEN")
    values = {k: _require_env(k) for k in keys}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
    print(f"OK: {path} geschrieben (Inhalt nicht angezeigt).")


ME_QUERY = "{ currentUser { nickname } }"


def cmd_me():
    """Confirm the OAuth token works by fetching the logged-in user."""
    if not os.environ.get("SORARE_ACCESS_TOKEN"):
        sys.exit("ERROR: SORARE_ACCESS_TOKEN is not set (see docs/oauth-setup.md).")
    print(json.dumps(graphql(ME_QUERY), indent=2, ensure_ascii=False))


def main(argv):
    load_env()
    if not argv:
        print(__doc__)
        return
    command, rest = argv[0], argv[1:]
    if command == "ping":
        cmd_ping()
    elif command == "player" and rest:
        cmd_player(rest[0])
    elif command == "query" and rest:
        cmd_query(rest[0])
    elif command == "authurl":
        cmd_authurl()
    elif command == "token" and rest:
        cmd_token(rest[0])
    elif command == "refresh":
        cmd_refresh()
    elif command == "tokenfile" and rest:
        cmd_tokenfile(rest[0])
    elif command == "me":
        cmd_me()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
