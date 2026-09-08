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
   python3 sorare_client.py ping                 # verify the key works
   python3 sorare_client.py player "Kylian Mbappe"
   python3 sorare_client.py query '{ currentUser { nickname } }'
   ```

## How the key is used

The API key is sent to `https://api.sorare.com/graphql` in the `APIKEY`
request header, as required by Sorare. See the
[Sorare developer docs](https://developers.sorare.com/).

## Network access on Claude Code on the web

If you run this inside a Claude Code web session, the environment's
**network policy may block `api.sorare.com`**. In that case live API calls
fail with a proxy `403`. To make live calls work either:

- run the client on your own machine, or
- use / configure an environment whose egress policy allows `api.sorare.com`
  (see https://code.claude.com/docs/en/claude-code-on-the-web).

## Security

- Never commit `.env.local` or paste your API key into shared chats.
- If your key is ever exposed, **rotate it** in your Sorare account settings.
