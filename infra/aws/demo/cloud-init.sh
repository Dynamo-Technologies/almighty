#!/bin/bash
# cloud-init userdata for almighty-demo EC2.
# Templated by render-userdata.sh (or by hand) before being passed to
# `aws ec2 run-instances --user-data file://...`.
#
# Idempotent enough to re-run safely if you SSH in and want to retry.
# Does NOT create the Route 53 A record — that's a manual step the
# operator does after this finishes (so they can verify the Tailscale IP
# before pointing DNS at it).
set -euxo pipefail

exec > >(tee /var/log/almighty-cloud-init.log | logger -t almighty -s 2>/dev/console) 2>&1

# 1. Tailscale install + join ------------------------------------------------
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up \
  --auth-key=__TAILSCALE_AUTH_KEY__ \
  --hostname=almighty-demo \
  --ssh

mkdir -p /etc/almighty
TS_IP=$(tailscale ip -4 | head -1)
echo "$TS_IP" > /etc/almighty/tailscale-ip

# 2. Docker + compose v2 + git ----------------------------------------------
# docker-compose-plugin is in Docker CE's apt repo, not Ubuntu's default;
# docker-compose-v2 in noble universe provides the `docker compose` CLI
# plugin and is sufficient for our needs. awscli is no longer needed (we
# don't talk to AWS from EC2 — Caddy reads creds from instance metadata).
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  docker.io docker-compose-v2 git rsync curl

systemctl enable --now docker

# 3. Clone almighty (branch templated in by render-userdata.sh) ------------
git clone https://github.com/Dynamo-Technologies/almighty /opt/almighty
cd /opt/almighty
test -n "${ALMIGHTY_BRANCH:-__ALMIGHTY_BRANCH__}" && git checkout "__ALMIGHTY_BRANCH__"

# 4. Build the web bundle on this box ---------------------------------------
# Mount the whole repo (not just web/renderer) — vite-plugin-static-copy
# pulls ../../czml/demos/*.czml during the build. Project uses pnpm via
# corepack (ships with node:20+); CI=true skips pnpm's no-TTY confirm.
docker run --rm -e CI=true -v /opt/almighty:/repo -w /repo/web/renderer node:20-bookworm-slim \
  sh -c "corepack enable && pnpm install --frozen-lockfile && pnpm run build"

# 5. Build the caddy image (with route53 dns-01 plugin) ---------------------
cd /opt/almighty/infra/aws/demo
docker build -t almighty-caddy:demo -f Dockerfile.caddy .

# 6. Write .env -------------------------------------------------------------
cat > .env <<EOF
SUPABASE_DATABASE_URL=__SUPABASE_DATABASE_URL__
JWT_PUBLIC_KEY=__JWT_PUBLIC_KEY__
AWS_REGION=__AWS_REGION__
TAILSCALE_IP=$TS_IP
EOF
chmod 600 .env

# 7. Bring up the stack -----------------------------------------------------
docker compose --env-file .env up -d

echo "------------------------------------------------------------------"
echo "almighty-demo cloud-init complete at $(date -Is)"
echo "Tailscale IP: $TS_IP"
echo "Manual next step: create Route 53 A record"
echo "  almightyengine.com  →  $TS_IP"
echo "------------------------------------------------------------------"
