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
    python3 sorare_client.py token <code>   # exchange the callback ?code= for tokens
    python3 sorare_client.py me             # who am I (needs SORARE_ACCESS_TOKEN)

The API key is sent in the `APIKEY` header, as required by Sorare. When
SORARE_ACCESS_TOKEN is set, an `Authorization: Bearer` header is added so
requests run on behalf of the logged-in user.
Docs: https://developers.sorare.com/  and  https://github.com/sorare/api
"""
import json
import os
import sys
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


def graphql(query, variables=None):
    """Execute a GraphQL request and return the parsed JSON response.

    The API key is optional here: if SORARE_API_KEY is set we send it in the
    APIKEY header ourselves. If it is not set, we send no key and rely on the
    request being enriched upstream -- e.g. a Claude Code cloud environment
    "API credential" that attaches the APIKEY header for api.sorare.com after
    the request leaves the session's VM. That way the key never has to live
    in the repo or the session at all.
    """
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
        GRAPHQL_ENDPOINT,
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        sys.exit(f"HTTP {exc.code} from Sorare API:\n{body}")
    except urllib.error.URLError as exc:
        sys.exit(
            f"Network error reaching {GRAPHQL_ENDPOINT}: {exc.reason}\n"
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


def cmd_token(code):
    """Exchange the authorization code for access + refresh tokens."""
    data = urllib.parse.urlencode(
        {
            "client_id": _require_env("SORARE_CLIENT_ID"),
            "client_secret": _require_env("SORARE_CLIENT_SECRET"),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": os.environ.get("SORARE_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        }
    ).encode()
    req = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        sys.exit(f"HTTP {exc.code} from token endpoint:\n{exc.read().decode(errors='replace')}")
    print(json.dumps(result, indent=2))
    if "access_token" in result:
        print(
            "\nStore this in .env.local (gitignored):\n"
            f"SORARE_ACCESS_TOKEN={result['access_token']}",
            file=sys.stderr,
        )


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
    elif command == "me":
        cmd_me()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
