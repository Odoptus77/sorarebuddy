# Deploy the sorarebuddy backend to a VPS

> On **Hostinger**? Follow `deploy/hostinger.md` — a tailored walkthrough
> (pick the OS, set the DNS A record in hPanel, open the firewall) that wraps
> the generic steps below.

The backend is pure Python 3 stdlib — no pip install. You need:

- a VPS (Debian/Ubuntu assumed) with root/sudo and Python 3,
- a **domain name** with an `A`/`AAAA` record pointing at the VPS
  (HTTPS needs it; the app and the dashboard artifact can't call plain HTTP),
- ports **80** and **443** open; keep **8080 closed** to the internet.

## 1. Get the code onto the VPS

```bash
sudo git clone https://github.com/Odoptus77/sorarebuddy /opt/sorarebuddy
cd /opt/sorarebuddy
sudo bash deploy/install.sh
```

`install.sh` creates a `sorarebuddy` system user, a cache dir under
`/var/lib/sorarebuddy`, the secrets file `/etc/sorarebuddy/env`, and a systemd
service (enabled, not yet started).

## 2. Put in your secrets

```bash
sudo nano /etc/sorarebuddy/env      # set SORARE_API_KEY and APP_TOKEN
sudo systemctl restart sorarebuddy
sudo systemctl status sorarebuddy   # active (running)
curl -s http://127.0.0.1:8080/health # {"ok": true, ...}
```

Generate a token with `openssl rand -hex 24`. The service binds `127.0.0.1`
only — it is reachable from the internet solely through the reverse proxy.

## 3. HTTPS in front of it

### Option A — Caddy (automatic certificates, easiest)

```bash
# install Caddy (official repo): https://caddyserver.com/docs/install
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

# edit the domain in the Caddyfile, then install it
sudo cp /opt/sorarebuddy/deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile        # replace sorarebuddy.example.com
sudo systemctl reload caddy
```

Caddy fetches a Let's Encrypt cert automatically. Done.

### Option B — nginx + certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo cp /opt/sorarebuddy/deploy/nginx-sorarebuddy.conf /etc/nginx/sites-available/sorarebuddy
sudo nano /etc/nginx/sites-available/sorarebuddy     # replace the domain
sudo ln -s /etc/nginx/sites-available/sorarebuddy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d sorarebuddy.example.com      # issues the cert
```

## 4. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80,443/tcp
sudo ufw enable          # note: 8080 stays closed — proxy only
```

## 5. Verify from the outside

```bash
curl -s https://sorarebuddy.example.com/health
curl -s "https://sorarebuddy.example.com/api/lineups?slug=nicktd7&rarities=limited,rare" \
     -H "Authorization: Bearer <APP_TOKEN>" | head -c 200
```

## 6. Point the apps at it

- **Dashboard artifact:** ⚙ button → Backend-URL `https://sorarebuddy.example.com`,
  slug, rarities, App-Token → Speichern. Then ⟳ Aktualisieren.
- **iOS app:** Einstellungen → same URL + token.

## 7. Keep the cache warm (optional but nice)

A cold `rewards`/`club` run scans a lot; prewarm hourly so taps feel instant:

```bash
# crontab -e  (as the sorarebuddy user or root)
0 * * * * curl -fsS "https://sorarebuddy.example.com/api/bundle?slug=nicktd7" -H "Authorization: Bearer <APP_TOKEN>" >/dev/null
```

## Updating later

```bash
cd /opt/sorarebuddy && sudo bash deploy/update.sh   # git pull + restart + health
```

## Logs & troubleshooting

```bash
journalctl -u sorarebuddy -f          # backend logs
sudo systemctl status sorarebuddy caddy
```

- 401 from the API → the `Authorization: Bearer` token doesn't match `APP_TOKEN`.
- First call is slow → cold cache; prewarm (step 7) or just wait it out once.
- The dashboard says "Refresh fehlgeschlagen" → check the URL is `https://`,
  reachable, and the token matches.

## Security

- `SORARE_API_KEY` lives only in `/etc/sorarebuddy/env` (chmod 600). Never in
  the app, the artifact, or git.
- Keep `APP_TOKEN` set so only you can trigger the (costly) Sorare fetches.
- If the key was ever shared, rotate it in Sorare settings and update the env.
