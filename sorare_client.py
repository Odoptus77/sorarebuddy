#!/usr/bin/env python3
"""Minimal, dependency-free client for the Sorare GraphQL API.

Reads the API key from the environment (SORARE_API_KEY) or from a local
.env.local file. Never hard-code the key in this file.

Usage:
    python3 sorare_client.py ping                 # check auth (currentUser)
    python3 sorare_client.py player "Kylian Mbappe"
    python3 sorare_client.py query '{ currentUser { nickname } }'

The API key is sent in the `APIKEY` header, as required by Sorare.
Docs: https://developers.sorare.com/
"""
import json
import os
import sys
import urllib.error
import urllib.request

GRAPHQL_ENDPOINT = "https://api.sorare.com/graphql"


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


def get_api_key():
    key = os.environ.get("SORARE_API_KEY")
    if not key:
        sys.exit(
            "ERROR: SORARE_API_KEY is not set.\n"
            "Set it in the environment or in .env.local (see .env.example)."
        )
    return key


def graphql(query, variables=None):
    """Execute a GraphQL request and return the parsed JSON response."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        GRAPHQL_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "APIKEY": get_api_key(),
            "User-Agent": "sorarebuddy/0.1",
        },
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
query Player($name: String!) {
  players(name: $name) {
    slug
    displayName
    position
    activeClub { name }
  }
}
"""


def cmd_ping():
    print(json.dumps(graphql(PING_QUERY), indent=2, ensure_ascii=False))


def cmd_player(name):
    print(json.dumps(graphql(PLAYER_QUERY, {"name": name}), indent=2, ensure_ascii=False))


def cmd_query(query):
    print(json.dumps(graphql(query), indent=2, ensure_ascii=False))


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
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
