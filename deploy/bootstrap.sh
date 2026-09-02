#!/usr/bin/env bash
#
# One-shot provisioning for a single-box DataChecker deployment on a Saudi VPS.
#
# Topology (all-in-one — no relay, no second host):
#
#   visitor → Caddy :443 → frontend nginx :3000 → backend :8000 → open.data.gov.sa
#                                                      └── postgres :5432
#
# The relay in relay/ exists only for hosts OUTSIDE Saudi Arabia. On a Saudi box
# the backend calls the portal directly, so PORTAL_BASE_URL keeps its default and
# nothing here mentions the relay.
#
# Run as root on a fresh Ubuntu 24.04 box:
#
#   DOMAIN=auditor.otaibifmf.com ./bootstrap.sh
#
# Set DOMAIN= empty to skip the Caddy/TLS step (useful while DNS is still
# propagating — the stack still comes up on localhost).

set -euo pipefail

DOMAIN="${DOMAIN:-}"
REPO="${REPO:-https://github.com/Otaibifmf/DatasetAuditor.git}"
APP_DIR="${APP_DIR:-/opt/datasetauditor}"

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[31mFAILED: %s\033[0m\n' "$*" >&2; exit 1; }

# ── Gate 1 — does THIS box's IP reach the portal? ────────────────────────────
# Everything downstream is pointless if this fails, and it costs one request to
# find out. A Saudi *consumer ISP* address is known to pass; whether this
# provider's *datacenter* range does is exactly what this test answers.
log "Gate 1/2/3 — testing portal access from this host"

http_code=$(curl -s -o /tmp/gate1.txt -w '%{http_code}' --max-time 25 \
  "https://open.data.gov.sa/data/api/datasets?version=-1&dataset=test" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" \
  -H "Accept: application/json, */*" \
  -H "Accept-Language: en-US,en;q=0.9,ar;q=0.8" || true)

if [ "$http_code" = "000" ]; then
  die "ConnectTimeout — this host's IP is blocked at the network layer (gate 1).
     Destroy this box and try another Saudi provider. Do NOT continue here."
fi
if grep -qi "Request Rejected" /tmp/gate1.txt 2>/dev/null; then
  die "WAF 'Request Rejected' — reached the portal but headers/path were refused (gate 2/3).
     The IP is fine; check BROWSER_HEADERS drift in backend/ckan_client.py."
fi
if [ "$http_code" != "404" ]; then
  die "Unexpected HTTP $http_code. Expected 404 'Dataset Not Found' for the fake id.
     Body: $(head -c 200 /tmp/gate1.txt)"
fi
grep -q "Dataset Not Found" /tmp/gate1.txt \
  || die "HTTP 404 but not the portal's JSON. Body: $(head -c 200 /tmp/gate1.txt)"

log "Gate test PASSED — this host can reach the portal."

# Confirmation with a REAL dataset id. The 404 above is the durable gate test —
# it proves the request cleared all three gates without depending on any dataset
# continuing to exist. This second call proves real data actually comes back.
# Non-fatal: if this id is ever retired the 404 test is still the real verdict.
REAL_ID="${REAL_ID:-587635b0-055c-40c9-b71d-efdf7ec52a92}"   # "AlUla Agriculture Nursery 2024"
real_code=$(curl -s -o /tmp/gate1_real.txt -w '%{http_code}' --max-time 25 \
  "https://open.data.gov.sa/data/api/datasets?version=-1&dataset=${REAL_ID}" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" \
  -H "Accept: application/json, */*" \
  -H "Accept-Language: en-US,en;q=0.9,ar;q=0.8" || true)

if [ "$real_code" = "200" ]; then
  log "Real dataset fetched OK: $(grep -o '\"titleEn\":\"[^\"]*\"' /tmp/gate1_real.txt | head -1)"
else
  printf '\033[33mNote: real-id check returned HTTP %s (gate test still passed).\033[0m\n' "$real_code"
fi

log "Proceeding with install."

# ── Docker ────────────────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi

# ── Code ──────────────────────────────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
  log "Updating $APP_DIR"
  git -C "$APP_DIR" pull --ff-only
else
  log "Cloning into $APP_DIR"
  git clone "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

# ── Environment ───────────────────────────────────────────────────────────────
# Two things matter here and both are security-relevant:
#
#  1. The compose file publishes every port as "${VAR:-default}:internal". The
#     left side is a full bind spec, so setting DB_PORT=127.0.0.1:5432 binds to
#     loopback instead of 0.0.0.0. This is NOT cosmetic: Docker writes its own
#     iptables DNAT rules that bypass ufw entirely, so a 0.0.0.0 publish is
#     reachable from the internet even with the firewall "closed". Only Caddy
#     should face outward.
#  2. The compose default DB password is the literal 'datachecker'. Generated
#     here instead, and DATABASE_URL is set to match (the backend reads the URL,
#     not the individual POSTGRES_* vars).
if [ ! -f .env ]; then
  log "Generating .env (random DB password, loopback-only port binds)"
  DB_PASS=$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)
  # Same-origin in practice (nginx proxies /api), so this is belt-and-braces.
  if [ -n "$DOMAIN" ]; then CORS="https://$DOMAIN"; else CORS="*"; fi
  cat > .env <<EOF
# Generated by deploy/bootstrap.sh — this file is gitignored, keep it that way.
POSTGRES_USER=datachecker
POSTGRES_PASSWORD=${DB_PASS}
POSTGRES_DB=datachecker
DATABASE_URL=postgresql+asyncpg://datachecker:${DB_PASS}@db:5432/datachecker

# Loopback-only. Caddy is the only thing bound to a public interface.
DB_PORT=127.0.0.1:5432
BACKEND_PORT=127.0.0.1:8000
FRONTEND_PORT=127.0.0.1:3000

# Saudi host → the backend calls the portal directly. No relay, no RELAY_KEY.
PORTAL_BASE_URL=https://open.data.gov.sa

# Same-origin through nginx, so no cross-origin request is ever made.
CORS_ORIGINS=${CORS}

# Fan-out endpoints stay off in a public deployment (they return 403).
ENABLE_BULK_ENDPOINTS=false
EOF
  chmod 600 .env
else
  log ".env already exists — leaving it alone"
fi

# ── Stack ─────────────────────────────────────────────────────────────────────
log "Building and starting the stack"
docker compose up -d --build

log "Waiting for the backend to report healthy"
for i in $(seq 1 40); do
  if curl -fs --max-time 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 3
  [ "$i" = 40 ] && die "Backend never became healthy. Check: docker compose logs backend"
done
curl -s http://127.0.0.1:8000/health; echo

# ── TLS ───────────────────────────────────────────────────────────────────────
if [ -n "$DOMAIN" ]; then
  if ! command -v caddy >/dev/null 2>&1; then
    log "Installing Caddy"
    apt-get update
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
      | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
      | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update
    apt-get install -y caddy
  fi

  log "Configuring Caddy for $DOMAIN"
  sed "s/{\$DOMAIN}/$DOMAIN/g" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
  systemctl reload caddy || systemctl restart caddy
  log "Caddy is serving $DOMAIN (certificate issues on first request)"
fi

# ── Backups ───────────────────────────────────────────────────────────────────
# A dead free-tier Postgres is what killed the Render deployment. This one lives
# as long as the box does, which is only worth something if it's dumped.
log "Installing nightly pg_dump cron"
mkdir -p /var/backups/datachecker
cat > /etc/cron.daily/datachecker-backup <<'EOF'
#!/bin/sh
cd /opt/datasetauditor || exit 0
docker compose exec -T db pg_dump -U datachecker datachecker \
  | gzip > "/var/backups/datachecker/$(date +%F).sql.gz"
find /var/backups/datachecker -name '*.sql.gz' -mtime +14 -delete
EOF
chmod +x /etc/cron.daily/datachecker-backup

log "Done."
cat <<EOF

  Stack:    docker compose ps          (in $APP_DIR)
  Logs:     docker compose logs -f backend
  Health:   curl localhost:8000/health
  Backups:  /var/backups/datachecker/  (nightly, 14-day retention)
${DOMAIN:+  Live:     https://$DOMAIN}

  Next: run one real audit through the UI and confirm the row persists
        and the PDF exports.
EOF
