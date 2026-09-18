# Deploy on a Hostinger VPS (step by step)

Tailored walkthrough for a Hostinger **VPS** (not shared hosting — shared
hosting can't run a long-lived Python service). It builds on `deploy/README.md`;
here are the Hostinger-specific parts.

## 0. What you need

- A Hostinger **VPS** plan.
- A **domain or subdomain** you can point at the VPS (for HTTPS). It can be a
  Hostinger domain or one anywhere else — you only need to add one DNS record.
- Your **Sorare API key**.

## 1. Create the VPS with a clean OS

In **hPanel → VPS → your server**:

1. Go to **OS & Panel → Operating System**.
2. Choose a **plain Ubuntu 24.04** (or 22.04) image — *without* a control panel
   (avoid the CyberPanel/CloudPanel templates; they occupy ports 80/443 that
   Caddy needs).
3. Set/reset the **root password** (VPS → Settings → **SSH access** / Root
   password). Note the server's **IP address** shown on the VPS overview.

## 2. Point your domain at the VPS

You need an **A record** `sorarebuddy.yourdomain.com → <VPS-IP>`.

- **Domain at Hostinger:** hPanel → **Domains → your domain → DNS / Nameservers
  → DNS records**. Add: Type `A`, Name `sorarebuddy` (or `@` for the root),
  Points to `<VPS-IP>`, TTL default.
- **Domain elsewhere:** add the same A record in that registrar's DNS panel.

Check it resolves (wait a few minutes for DNS):

```bash
dig +short sorarebuddy.yourdomain.com     # should print your VPS IP
```

## 3. Open the firewall

Two layers can block ports on Hostinger — handle both:

- **Hostinger firewall** (hPanel → VPS → **Firewall**): if it's active, add
  rules to **accept TCP 80 and 443** (and keep 22 for SSH). If you don't use
  it, leave it off.
- **On the server** (below) we use `ufw` and open 80/443 only. Never expose 8080.

## 4. Connect and install

From your computer:

```bash
ssh root@<VPS-IP>
```

Then on the server:

```bash
apt update && apt install -y git python3
git clone https://github.com/Odoptus77/sorarebuddy /opt/sorarebuddy
cd /opt/sorarebuddy
bash deploy/install.sh
nano /etc/sorarebuddy/env         # set SORARE_API_KEY and APP_TOKEN (openssl rand -hex 24)
systemctl restart sorarebuddy
curl -s http://127.0.0.1:8080/health   # {"ok": true, ...}
```

## 5. HTTPS with Caddy (automatic certificate)

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy

cp /opt/sorarebuddy/deploy/Caddyfile /etc/caddy/Caddyfile
nano /etc/caddy/Caddyfile          # replace sorarebuddy.example.com with your domain
systemctl reload caddy

# server-side firewall
ufw allow OpenSSH && ufw allow 80,443/tcp && ufw --force enable
```

Caddy now fetches a Let's Encrypt certificate automatically (needs the DNS
record from step 2 and ports 80/443 reachable).

## 6. Test from outside and wire up the app

```bash
curl -s https://sorarebuddy.yourdomain.com/health
```

- **Dashboard artifact:** ⚙ → Backend-URL `https://sorarebuddy.yourdomain.com`,
  slug, rarities, App-Token → **Speichern** → **⟳ Aktualisieren**.
- **iOS app:** Einstellungen → same URL + token.

## 7. Keep it fresh (optional)

```bash
crontab -e
# hourly prewarm so taps are instant:
0 * * * * curl -fsS "https://sorarebuddy.yourdomain.com/api/bundle?slug=nicktd7" -H "Authorization: Bearer <APP_TOKEN>" >/dev/null
```

## Updating later

```bash
cd /opt/sorarebuddy && bash deploy/update.sh
```

## If something's off

```bash
journalctl -u sorarebuddy -f      # backend logs
systemctl status sorarebuddy caddy
```

- Caddy can't get a cert → DNS A record not propagated yet, or 80/443 blocked
  (check the Hostinger firewall panel *and* `ufw status`).
- `502`/connection refused via HTTPS → the backend isn't running
  (`systemctl status sorarebuddy`) or `BIND`/`PORT` don't match the Caddyfile.
- Dashboard "Refresh fehlgeschlagen" → wrong URL/token, or the cert isn't ready.
