# sorarebuddy

Helper tooling for working with the [Sorare](https://sorare.com) GraphQL API.

## Setup

1. Copy the example env file and add your key (the key is kept out of git):

   ```bash
   cp .env.example .env.local
   # then edit .env.local and set SORARE_API_KEY=...
   ```

   `.env.local` is listed in `.gitignore` and must **never** be committed.

2. Run the client (no dependencies required, uses only the Python stdlib):

   ```bash
   python3 sorare_client.py ping                          # verify connectivity
   python3 sorare_client.py player kylian-mbappe-lottin   # look up player(s) by slug
   python3 sorare_client.py query '{ players(slugs: ["kylian-mbappe-lottin"]) { displayName activeClub { name } } }'
   ```

   Note: the API key authenticates the *application*, not a user. User-specific
   fields like `currentUser` return `null` unless you also supply a signed-in
   JWT; public data (players, clubs, competitions, cards) works with the key
   alone. Players are looked up by **slug** (e.g. `kylian-mbappe-lottin`), not
   by free-text name.

## How the key is used

The API key is sent to `https://api.sorare.com/graphql` in the `APIKEY`
request header, as required by Sorare. See the
[Sorare developer docs](https://developers.sorare.com/).

## Network access on Claude Code on the web

If you run this inside a Claude Code web session, the environment's
**network policy may block `api.sorare.com`**. In that case live API calls
fail with a proxy `403`. The recommended fix (Pro/Max) is to store the key as
an **API credential** on the cloud environment so the proxy attaches the
`APIKEY` header for `api.sorare.com` automatically — the key never enters the
session. Full step-by-step instructions (and the Custom-allowlist alternative
for Team/Enterprise) are in [`docs/network-setup.md`](docs/network-setup.md).

When the credential is configured this way, `SORARE_API_KEY` does not need to
be set locally: the client sends no key and the proxy injects it.

## Security

- Never commit `.env.local` or paste your API key into shared chats.
- If your key is ever exposed, **rotate it** in your Sorare account settings.
