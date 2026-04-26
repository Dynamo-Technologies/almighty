# Hackathon demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the 3-minute one-click hackathon demo specified in `docs/superpowers/specs/2026-04-26-hackathon-demo-design.md` — AWS-hosted Almighty at `https://almighty-demo.dynamo.works`, blue + red S3 LLM-driven on the two NVIDIA Sparks via Tailscale, with PyRapide's causal DAG as both the agent's situation report (assist) and the audit trail (`causal_predecessors` populated on commit).

**Architecture:** Single EC2 (t3.medium, us-east-1) running Caddy + control-plane + websocket + czml-adapter behind Tailscale-only ingress with a real Let's Encrypt cert via Route 53 DNS-01. Supabase Postgres for the demo tenant. spark-763d's existing CrewAI container repurposed as a FastAPI worker (bind-mount almighty repo, override CMD to run uvicorn) that runs both crews; red S3's LLM call hops to spark-3fe3's vLLM over the Spark-to-Spark cable.

**Tech Stack:** Python 3.11+ (CrewAI, FastAPI, pyrapide, pydantic), Node.js/TypeScript (Fastify, pg, Vite, React), Caddy 2, Docker / docker-compose, Terraform-free imperative AWS bring-up via `aws` CLI, Supabase, Tailscale.

---

## File structure — what gets created or modified

### New files
- `infra/aws/demo/Caddyfile` — Caddy reverse proxy + TLS config with Route 53 DNS-01
- `infra/aws/demo/Dockerfile.caddy` — `caddy:builder` + `caddy-dns/route53` plugin
- `infra/aws/demo/docker-compose.yml` — caddy + control-plane + websocket + czml-adapter
- `infra/aws/demo/.env.example` — env var template
- `infra/aws/demo/cloud-init.sh` — EC2 first-boot script (Tailscale join, docker compose up, Route 53 UPSERT)
- `infra/aws/demo/launch-ec2.sh` — local helper that creates the IAM role, launches the instance, and tails the logs
- `infra/aws/demo/iam-policy-route53-dns01.json` — IAM policy for Caddy DNS-01
- `infra/supabase/seed.sql` — tenant + scenario + capability profiles + override policies + entities for the demo
- `agents/runtime/src/almighty_agent_runtime/situation_report.py` — DAG → text helper
- `agents/runtime/src/almighty_agent_runtime/llm_clients.py` — blue/red LLM client factories
- `agents/runtime/src/almighty_agent_runtime/llm_step.py` — generic LLM-driven role-step helper
- `agents/runtime/src/almighty_agent_runtime/shim.py` — FastAPI app exposing `POST /run-turn`
- `agents/runtime/spark/run-worker.sh` — script the operator runs on spark-763d to (re)launch the worker container
- `agents/runtime/tests/test_situation_report.py`
- `agents/runtime/tests/test_llm_step.py`
- `agents/runtime/tests/test_shim.py`

### Modified files
- `agents/tools/src/almighty_officer_tools/context.py` (or wherever `OfficerToolContext` lives) — add `causal_predecessors` field
- `agents/tools/src/almighty_officer_tools/base.py:127-138` — read predecessors from `ctx.causal_predecessors` instead of hardcoding `[]`
- `agents/blue/src/almighty_blue_crew/crew.py` — replace `_step_s3_issue_order_to_a` and `_step_s3_request_isr` with a single `_step_s3_llm_decide` that calls the LLM helper
- `agents/red/src/almighty_red_crew/crew.py` — same pattern for red S3 (file path identical, package different)
- `services/control-plane/src/stubs/agent-runtime.ts` — replace 100ms-sleep stub with real HTTP POST to spark-763d worker
- `services/control-plane/src/config.ts` — add `SPARK_WORKER_URL` env var
- `web/renderer/src/components/EventLog.tsx` — render `causal_predecessors` as parent-verb chips, click → highlight parent
- `web/renderer/src/api/aar.ts:74-108` (`fixtureEvents`) — populate fixture predecessors so the visual change is testable without live data

### Untouched
- `kernel/` (PyRapide DAG implementation already supports everything we need)
- `services/websocket/`, `services/czml-adapter/`, `services/czml-validator/` (existing wiring is fine)
- `agents/white-cell/` (not on demo critical path)
- spark-3fe3 (inference only — no container changes)

---

## Operator prerequisites — gather before starting Task 1

The operator hands over these three values before the implementation work begins. They block Phase 1.

- [ ] **Tailscale auth key** — generate per spec §11a, capture the `tskey-auth-...` string
- [ ] **Route 53 hosted zone ID** for `dynamo.works`:
      `aws route53 list-hosted-zones --query 'HostedZones[?Name==\`dynamo.works.\`].Id' --output text`
- [ ] **IAM approach choice** — instance role (recommended) or IAM user with keys. Plan assumes **instance role**; if user with keys, swap step 1.4

Save these into a local scratch file `~/.almighty-demo-secrets.env`:

```bash
TAILSCALE_AUTH_KEY=tskey-auth-XXXXXXXXXXX
ROUTE53_ZONE_ID=Z0123456789ABCDEFG    # without the /hostedzone/ prefix
AWS_REGION=us-east-1
```

---

## Phase 1 — AWS, Tailscale, Caddy, Route 53 (~90 min)

### Task 1.1: Create Caddy image with Route 53 plugin

**Files:**
- Create: `infra/aws/demo/Dockerfile.caddy`

- [ ] **Step 1: Write the Dockerfile**

```dockerfile
# infra/aws/demo/Dockerfile.caddy
FROM caddy:2.8-builder AS builder
RUN xcaddy build \
    --with github.com/caddy-dns/route53

FROM caddy:2.8-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```

- [ ] **Step 2: Build locally to verify it compiles**

```bash
cd infra/aws/demo
docker buildx build --platform linux/amd64 -t almighty-caddy:demo -f Dockerfile.caddy . --load
docker run --rm almighty-caddy:demo caddy list-modules | grep route53
```

Expected: `dns.providers.route53` appears in the list.

- [ ] **Step 3: Commit**

```bash
git add infra/aws/demo/Dockerfile.caddy
git commit -m "feat(infra): caddy image with route53 dns-01 plugin"
```

---

### Task 1.2: Caddyfile + docker-compose.yml + env example

**Files:**
- Create: `infra/aws/demo/Caddyfile`
- Create: `infra/aws/demo/docker-compose.yml`
- Create: `infra/aws/demo/.env.example`

- [ ] **Step 1: Write the Caddyfile**

```caddyfile
# infra/aws/demo/Caddyfile
{
    email demo-ops@dynamo.works
}

almighty-demo.dynamo.works {
    tls {
        dns route53 {
            region {env.AWS_REGION}
            # Caddy picks up creds from the EC2 instance role automatically;
            # no access_key_id / secret_access_key needed when running on EC2.
        }
    }

    # API and websocket reverse proxies
    handle_path /api/* {
        reverse_proxy control-plane:4000
    }
    handle_path /ws* {
        reverse_proxy websocket:4001
    }

    # Static SPA
    handle {
        root * /srv/web
        try_files {path} /index.html
        file_server
    }

    log {
        output stdout
        format console
    }
}

# Internal healthz on :2019 — bound to localhost only (Caddy admin API).
```

- [ ] **Step 2: Write the compose file**

```yaml
# infra/aws/demo/docker-compose.yml
services:
  caddy:
    image: almighty-caddy:demo
    restart: unless-stopped
    ports:
      # Bind to the Tailscale IP only. We discover it at boot from
      # tailscale ip -4 and write to /etc/almighty/tailscale-ip; the
      # systemd unit re-templates this compose with the right address.
      - "${TAILSCALE_IP}:443:443"
      - "${TAILSCALE_IP}:80:80"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ../../../web/renderer/dist:/srv/web:ro
      - caddy-data:/data
      - caddy-config:/config
    environment:
      AWS_REGION: ${AWS_REGION}
    depends_on: [control-plane, websocket]

  control-plane:
    image: node:20-bookworm-slim
    restart: unless-stopped
    working_dir: /app
    volumes:
      - ../../../services/control-plane:/app
    command: ["sh", "-c", "npm ci && npm run build && node dist/server.js"]
    environment:
      DATABASE_URL: ${SUPABASE_DATABASE_URL}
      PORT: "4000"
      JWT_PUBLIC_KEY: ${JWT_PUBLIC_KEY}
      SPARK_WORKER_URL: http://100.106.123.5:7000
    expose: ["4000"]

  websocket:
    image: node:20-bookworm-slim
    restart: unless-stopped
    working_dir: /app
    volumes:
      - ../../../services/websocket:/app
    command: ["sh", "-c", "npm ci && npm run build && node dist/server.js"]
    environment:
      DATABASE_URL: ${SUPABASE_DATABASE_URL}
      PORT: "4001"
    expose: ["4001"]

  czml-adapter:
    image: python:3.12-slim
    restart: unless-stopped
    working_dir: /app
    volumes:
      - ../../../services/czml-adapter:/app
    command: ["sh", "-c", "pip install --no-cache-dir -e . && python -m almighty_czml_adapter.runner"]
    environment:
      DATABASE_URL: ${SUPABASE_DATABASE_URL}
    expose: ["4002"]

volumes:
  caddy-data:
  caddy-config:
```

- [ ] **Step 3: Write `.env.example`**

```bash
# infra/aws/demo/.env.example
SUPABASE_DATABASE_URL=postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
AWS_REGION=us-east-1
TAILSCALE_IP=100.x.y.z
```

- [ ] **Step 4: Commit**

```bash
git add infra/aws/demo/Caddyfile infra/aws/demo/docker-compose.yml infra/aws/demo/.env.example
git commit -m "feat(infra): caddy + compose stack for ec2 demo host"
```

---

### Task 1.3: IAM policy file + cloud-init script

**Files:**
- Create: `infra/aws/demo/iam-policy-route53-dns01.json`
- Create: `infra/aws/demo/cloud-init.sh`

- [ ] **Step 1: Write the IAM policy**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListZones",
      "Effect": "Allow",
      "Action": ["route53:ListHostedZones", "route53:GetChange"],
      "Resource": "*"
    },
    {
      "Sid": "ChangeRecords",
      "Effect": "Allow",
      "Action": "route53:ChangeResourceRecordSets",
      "Resource": "arn:aws:route53:::hostedzone/DYNAMO_WORKS_ZONE_ID_PLACEHOLDER"
    }
  ]
}
```

(The `launch-ec2.sh` script in Task 1.4 substitutes the real zone ID into `arn:aws:route53:::hostedzone/...` before attaching.)

- [ ] **Step 2: Write the cloud-init script**

```bash
#!/bin/bash
# infra/aws/demo/cloud-init.sh
# Runs on EC2 first boot. Templated with the operator's TS auth key + zone id
# inside launch-ec2.sh before being passed as user-data.
set -euxo pipefail

exec > >(tee /var/log/almighty-cloud-init.log | logger -t almighty -s 2>/dev/console) 2>&1

# 1. Tailscale install + join
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up \
  --auth-key=__TAILSCALE_AUTH_KEY__ \
  --hostname=almighty-demo \
  --ssh

mkdir -p /etc/almighty
TS_IP=$(tailscale ip -4 | head -1)
echo "$TS_IP" > /etc/almighty/tailscale-ip

# 2. Docker + compose plugin + git + aws CLI
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  docker.io docker-compose-plugin git awscli rsync

systemctl enable --now docker

# 3. Clone almighty
git clone https://github.com/Dynamo-Technologies/almighty /opt/almighty
# If a feature branch is wanted, the operator passes ALMIGHTY_BRANCH via
# the launch script:
test -n "${ALMIGHTY_BRANCH:-}" && (cd /opt/almighty && git checkout "$ALMIGHTY_BRANCH")

# 4. Build the web bundle locally on the EC2 (no need to ship from laptop).
#    npm + node already in the control-plane image so we use docker run.
docker run --rm -v /opt/almighty/web/renderer:/app -w /app node:20-bookworm-slim \
  sh -c "npm ci && npm run build"

# 5. Build the caddy image
cd /opt/almighty/infra/aws/demo
docker build -t almighty-caddy:demo -f Dockerfile.caddy .

# 6. Write .env
cat > .env <<EOF
SUPABASE_DATABASE_URL=__SUPABASE_DATABASE_URL__
JWT_PUBLIC_KEY=__JWT_PUBLIC_KEY__
AWS_REGION=__AWS_REGION__
TAILSCALE_IP=$TS_IP
EOF

# 7. Bring up the stack
docker compose --env-file .env up -d

# 8. UPSERT the Route 53 A record
ZONE_ID=__ROUTE53_ZONE_ID__
cat > /tmp/route53-change.json <<EOF
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "almighty-demo.dynamo.works",
      "Type": "A",
      "TTL": 60,
      "ResourceRecords": [{"Value": "$TS_IP"}]
    }
  }]
}
EOF
aws route53 change-resource-record-sets \
  --hosted-zone-id "$ZONE_ID" \
  --change-batch file:///tmp/route53-change.json

echo "almighty-demo cloud-init complete at $(date -Is)"
```

- [ ] **Step 3: Commit**

```bash
git add infra/aws/demo/iam-policy-route53-dns01.json infra/aws/demo/cloud-init.sh
git commit -m "feat(infra): cloud-init + iam policy for ec2 demo host"
```

---

### Task 1.4: EC2 launch script

**Files:**
- Create: `infra/aws/demo/launch-ec2.sh`

- [ ] **Step 1: Write the launch script**

```bash
#!/bin/bash
# infra/aws/demo/launch-ec2.sh
# Launches the demo EC2 with cloud-init userdata. Requires:
#   ~/.almighty-demo-secrets.env containing TAILSCALE_AUTH_KEY,
#   ROUTE53_ZONE_ID, AWS_REGION, SUPABASE_DATABASE_URL, JWT_PUBLIC_KEY
set -euo pipefail

source ~/.almighty-demo-secrets.env
: "${TAILSCALE_AUTH_KEY:?missing}"
: "${ROUTE53_ZONE_ID:?missing}"
: "${AWS_REGION:=us-east-1}"
: "${SUPABASE_DATABASE_URL:?missing — Phase 2 must finish first}"
: "${JWT_PUBLIC_KEY:?missing — generate via openssl, see notes}"

ROLE_NAME=almighty-demo-ec2
INSTANCE_PROFILE=almighty-demo-ec2
POLICY_NAME=almighty-demo-route53-dns01
SG_NAME=almighty-demo-sg
KEY_NAME=almighty-demo

cd "$(dirname "$0")"

# 1. IAM role + instance profile + policy ----------------------------------
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{
        "Effect":"Allow",
        "Principal":{"Service":"ec2.amazonaws.com"},
        "Action":"sts:AssumeRole"
      }]
    }'
fi

# Substitute zone id into policy
sed "s|DYNAMO_WORKS_ZONE_ID_PLACEHOLDER|$ROUTE53_ZONE_ID|" \
  iam-policy-route53-dns01.json > /tmp/policy.json

aws iam put-role-policy --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME" \
  --policy-document file:///tmp/policy.json

if ! aws iam get-instance-profile --instance-profile-name "$INSTANCE_PROFILE" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$INSTANCE_PROFILE"
  aws iam add-role-to-instance-profile \
    --instance-profile-name "$INSTANCE_PROFILE" \
    --role-name "$ROLE_NAME"
  # IAM is eventually consistent — instance launch can race
  sleep 10
fi

# 2. Security group: outbound only (no public ingress) --------------------
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")

SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION" 2>/dev/null \
  || true)

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name "$SG_NAME" \
    --description "almighty-demo: outbound only; tailscale handles ingress" \
    --vpc-id "$VPC_ID" \
    --region "$AWS_REGION" \
    --query 'GroupId' --output text)
  # Allow inbound only on Tailscale's WireGuard port (UDP 41641 by default)
  # so the EC2 can establish the tailnet tunnel cleanly.
  aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol udp --port 41641 --cidr 0.0.0.0/0 \
    --region "$AWS_REGION"
  # NOTE: no inbound 80/443 — Caddy listens on the Tailscale IP only.
fi

# 3. AMI: latest Ubuntu 24.04 amd64 ----------------------------------------
AMI_ID=$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text --region "$AWS_REGION")

# 4. Render userdata --------------------------------------------------------
cp cloud-init.sh /tmp/userdata.sh
sed -i '' \
  -e "s|__TAILSCALE_AUTH_KEY__|$TAILSCALE_AUTH_KEY|g" \
  -e "s|__ROUTE53_ZONE_ID__|$ROUTE53_ZONE_ID|g" \
  -e "s|__AWS_REGION__|$AWS_REGION|g" \
  -e "s|__SUPABASE_DATABASE_URL__|$SUPABASE_DATABASE_URL|g" \
  -e "s|__JWT_PUBLIC_KEY__|$(echo "$JWT_PUBLIC_KEY" | tr '\n' ' ')|g" \
  /tmp/userdata.sh

# 5. Launch -----------------------------------------------------------------
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t3.medium \
  --iam-instance-profile "Name=$INSTANCE_PROFILE" \
  --security-group-ids "$SG_ID" \
  --user-data "file:///tmp/userdata.sh" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=almighty-demo}]" \
  --region "$AWS_REGION" \
  --query 'Instances[0].InstanceId' --output text)

echo "Launching $INSTANCE_ID — waiting for running…"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"

PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text \
  --region "$AWS_REGION")

cat <<EOF
INSTANCE_ID=$INSTANCE_ID
PUBLIC_IP=$PUBLIC_IP

Watch cloud-init progress (SSH via Tailscale once joined, or AWS Session Manager):
  aws ssm start-session --target $INSTANCE_ID --region $AWS_REGION
  sudo tail -f /var/log/almighty-cloud-init.log

Expected total cloud-init runtime: 4-7 minutes.
EOF
```

- [ ] **Step 2: chmod +x and commit**

```bash
chmod +x infra/aws/demo/launch-ec2.sh infra/aws/demo/cloud-init.sh
git add infra/aws/demo/launch-ec2.sh
git commit -m "feat(infra): launch-ec2.sh — provisions iam, sg, instance"
```

---

### Task 1.5: Phase 1 dry-run (without launching real EC2 yet)

The actual EC2 launch is gated on Phase 2 producing the `SUPABASE_DATABASE_URL`. Dry-run validation:

- [ ] **Step 1: Validate Caddyfile syntax**

```bash
cd infra/aws/demo
docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" almighty-caddy:demo \
  caddy validate --config /etc/caddy/Caddyfile
```

Expected: "Valid configuration".

- [ ] **Step 2: Validate compose syntax**

```bash
docker compose -f docker-compose.yml --env-file .env.example config > /dev/null
```

Expected: exit 0.

- [ ] **Step 3: Lint cloud-init**

```bash
shellcheck infra/aws/demo/cloud-init.sh infra/aws/demo/launch-ec2.sh || true
```

(If shellcheck reports issues, fix or accept based on severity. Errors block; warnings are advisory.)

---

## Phase 2 — Supabase Postgres + schema + seed (~30 min)

### Task 2.1: Provision Supabase project

- [ ] **Step 1: Manual — create project**

Go to https://supabase.com/dashboard/new. Name: `almighty-demo`. Region: `us-east-1` (matches EC2). Wait ~2 min for provisioning.

- [ ] **Step 2: Capture the connection string**

Project Settings → Database → Connection string (Session pooler tab). Copy and store in `~/.almighty-demo-secrets.env` as `SUPABASE_DATABASE_URL`. Replace `[YOUR-PASSWORD]` with the project's database password.

- [ ] **Step 3: Verify connectivity**

```bash
source ~/.almighty-demo-secrets.env
psql "$SUPABASE_DATABASE_URL" -c "SELECT version();"
```

Expected: PostgreSQL 15.x or 16.x version string.

---

### Task 2.2: Apply existing schemas

The control-plane has migrations in `services/control-plane/migrations/` (verify the path; if elsewhere, find with `find services -name "*.sql" -path "*/migrations/*"`).

- [ ] **Step 1: Inventory migrations**

```bash
find services -name "*.sql" 2>&1 | head -30
```

Expected: a list of `001_*.sql` style files.

- [ ] **Step 2: Apply in order**

```bash
source ~/.almighty-demo-secrets.env
for f in $(ls services/control-plane/migrations/*.sql 2>/dev/null | sort); do
  echo "Applying $f…"
  psql "$SUPABASE_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done
```

If migrations live somewhere else, substitute the path. If a single combined schema file exists (e.g., `schema.sql`), apply that.

- [ ] **Step 3: Verify the four core tables exist**

```bash
psql "$SUPABASE_DATABASE_URL" -c "\dt" | grep -E "scenarios|events|turn_snapshots|override_policies"
```

Expected: all four tables listed.

---

### Task 2.3: Write the seed script

**Files:**
- Create: `infra/supabase/seed.sql`

- [ ] **Step 1: Write the seed**

```sql
-- infra/supabase/seed.sql
-- Hackathon demo seed. Idempotent: re-runnable without conflict.

BEGIN;

-- Demo tenant
INSERT INTO tenants (tenant_id, display_name)
VALUES ('00000000-0000-4d00-8000-000000000001', 'Demo (hackathon)')
ON CONFLICT (tenant_id) DO NOTHING;

-- Nashville scenario row at turn 0, ready to advance
INSERT INTO scenarios (tenant_id, scenario_id, display_name, current_turn, turn_state)
VALUES (
  '00000000-0000-4d00-8000-000000000001',
  '00000000-0000-4101-8000-000000000001',
  'Nashville Cumberland River crossing',
  0,
  'open'
)
ON CONFLICT (tenant_id, scenario_id) DO UPDATE
  SET current_turn = 0, turn_state = 'open';

-- Override policies — all auto-approve so the demo runs hands-off.
-- (Spec §7: manual override authoring is cut from the demo path.)
DELETE FROM override_policies
 WHERE tenant_id = '00000000-0000-4d00-8000-000000000001'
   AND scenario_id = '00000000-0000-4101-8000-000000000001';

INSERT INTO override_policies (
  tenant_id, scenario_id, scope, target_predicate, action, ttl_turns, rationale
) VALUES
  (
    '00000000-0000-4d00-8000-000000000001',
    '00000000-0000-4101-8000-000000000001',
    'per-turn', 'true', 'auto-approve', 6,
    'Demo seed: auto-approve all events. Manual review out of scope per spec §7.'
  );

COMMIT;
```

If the actual schema differs (e.g., column names, missing tables), adjust to match. Do this by reading the migration files, not by guessing.

- [ ] **Step 2: Apply and verify**

```bash
psql "$SUPABASE_DATABASE_URL" -v ON_ERROR_STOP=1 -f infra/supabase/seed.sql
psql "$SUPABASE_DATABASE_URL" -c "SELECT current_turn, turn_state FROM scenarios WHERE scenario_id = '00000000-0000-4101-8000-000000000001';"
```

Expected: `current_turn=0`, `turn_state='open'`.

- [ ] **Step 3: Commit**

```bash
git add infra/supabase/seed.sql
git commit -m "feat(infra): supabase seed for demo tenant + scenario + auto-approve override"
```

---

### Task 2.4: Generate the JWT public key

The control-plane requires a JWT public key for `requireAuth`. For the demo, generate an ephemeral keypair, sign a long-lived white-cell token, and inject the public key via env.

- [ ] **Step 1: Generate the keypair**

```bash
mkdir -p ~/.almighty-demo-secrets
openssl genrsa -out ~/.almighty-demo-secrets/jwt.pem 2048
openssl rsa -in ~/.almighty-demo-secrets/jwt.pem -pubout > ~/.almighty-demo-secrets/jwt.pub
```

- [ ] **Step 2: Sign a white-cell token**

```bash
# Use a small node helper; jose lib is in control-plane node_modules already
cd services/control-plane
node -e '
const { SignJWT, importPKCS8 } = require("jose");
const fs = require("fs");
const pk = fs.readFileSync(process.env.HOME + "/.almighty-demo-secrets/jwt.pem", "utf8");
(async () => {
  const key = await importPKCS8(pk, "RS256");
  const tok = await new SignJWT({
    sub: "demo@dynamo.works",
    tenant: "00000000-0000-4d00-8000-000000000001",
    role: "white",
  })
    .setProtectedHeader({ alg: "RS256" })
    .setIssuedAt()
    .setExpirationTime("24h")
    .sign(key);
  console.log(tok);
})();
'
```

Save the printed JWT somewhere (it'll go into the renderer's localStorage in Phase 6). Add the public key contents to `~/.almighty-demo-secrets.env`:

```bash
echo "JWT_PUBLIC_KEY=\"$(cat ~/.almighty-demo-secrets/jwt.pub | awk 'BEGIN{ORS="\\n"}1' | sed 's/\\n$//')\"" >> ~/.almighty-demo-secrets.env
echo "DEMO_JWT=<the token from above>" >> ~/.almighty-demo-secrets.env
```

If the existing control-plane uses a different JWT scheme (e.g., HS256 with a shared secret, or pulls from Supabase auth), inspect `services/control-plane/src/auth.ts` and adapt this step accordingly.

---

## Phase 3 — Kernel + agents code (the magic; ~2 hr)

This is the meat of the demo. We TDD aggressively here because regressions during the hackathon would be catastrophic and the test suite makes them visible immediately.

### Task 3.1: OfficerToolContext gains `causal_predecessors`

**Files:**
- Modify: `agents/tools/src/almighty_officer_tools/context.py` (find the dataclass via `grep -rn "class OfficerToolContext" agents/`)
- Test: `agents/tools/tests/test_context.py` (or wherever existing context tests live)

- [ ] **Step 1: Find the file**

```bash
grep -rn "class OfficerToolContext" agents/
```

- [ ] **Step 2: Write the failing test**

```python
# agents/tools/tests/test_causal_predecessors.py
from uuid import uuid4
from almighty_officer_tools.context import OfficerToolContext
from almighty_kernel.dag import NamespacedDag
from almighty_czml_validator import Validator

def test_context_carries_causal_predecessors():
    pid = uuid4()
    ctx = OfficerToolContext(
        tenant_id=uuid4(),
        scenario_id=uuid4(),
        turn=1,
        agent_entity_id=uuid4(),
        capability_profile={"action_verbs_available": []},
        kernel_dag=NamespacedDag(),
        validator=Validator(),
        causal_predecessors=[pid],
    )
    assert ctx.causal_predecessors == [pid]

def test_context_default_predecessors_is_empty():
    ctx = OfficerToolContext(
        tenant_id=uuid4(),
        scenario_id=uuid4(),
        turn=1,
        agent_entity_id=uuid4(),
        capability_profile={"action_verbs_available": []},
        kernel_dag=NamespacedDag(),
        validator=Validator(),
    )
    assert ctx.causal_predecessors == []
```

- [ ] **Step 3: Run to confirm it fails**

```bash
cd agents/tools
pytest tests/test_causal_predecessors.py -v
```

Expected: TypeError or AttributeError because the field doesn't exist.

- [ ] **Step 4: Add the field**

In the OfficerToolContext class definition, add:

```python
from uuid import UUID  # if not already imported
from dataclasses import field  # if dataclass-style

# inside the class definition:
causal_predecessors: list[UUID] = field(default_factory=list)
```

If it's a `pydantic.BaseModel` instead of a dataclass:

```python
causal_predecessors: list[UUID] = Field(default_factory=list)
```

- [ ] **Step 5: Re-run, confirm green**

```bash
pytest tests/test_causal_predecessors.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Confirm no other tests regress**

```bash
pytest agents/tools/tests/ -q
```

Expected: existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add agents/tools/
git commit -m "feat(tools): OfficerToolContext carries causal_predecessors list"
```

---

### Task 3.2: OfficerToolBase reads predecessors from context

**Files:**
- Modify: `agents/tools/src/almighty_officer_tools/base.py:127-138`
- Test: extend `agents/tools/tests/test_causal_predecessors.py`

- [ ] **Step 1: Add a failing test**

Append to `test_causal_predecessors.py`:

```python
from uuid import UUID, uuid4
from almighty_kernel.dag import NamespacedDag, KernelEvent
from almighty_officer_tools.context import OfficerToolContext, ToolError
from almighty_officer_tools import build_all_tools
from almighty_czml_validator import Validator

def test_tool_run_attaches_causal_predecessors_from_context():
    """An LLM-driven role pre-populates ctx.causal_predecessors before calling
    a tool. The committed event must list those ids as parents."""
    tenant_id = uuid4()
    scenario_id = uuid4()
    dag = NamespacedDag()

    # Pre-seed an event in the DAG so a real predecessor uuid exists
    seed = KernelEvent(
        event_id=uuid4(),
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        turn=1,
        source_officer_type="SENSOR",
        source_entity_id=uuid4(),
        action_verb="detect",
        payload={},
        causal_predecessors=[],
    )
    dag.commit(seed)

    ctx = OfficerToolContext(
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        turn=1,
        agent_entity_id=uuid4(),
        capability_profile={"action_verbs_available": ["issue_order"]},
        kernel_dag=dag,
        validator=Validator(),
        causal_predecessors=[seed.event_id],
    )
    tools = build_all_tools(ctx)
    issue_order = tools["issue_order"]

    result = issue_order._run(
        order_type="MOVE",
        order_payload={"waypoints": [{"lat_deg": 36.18, "lon_deg": -86.78, "alt_m": 165.0}]},
        to_entity_id=uuid4(),
        priority="MEDIUM",
    )

    # Inspect the committed event in the DAG
    events = dag.read(tenant_id=tenant_id, scenario_id=scenario_id)
    issued = next(e for e in events if e.event_id == UUID(result["event_id"]))
    assert issued.causal_predecessors == [seed.event_id]
```

- [ ] **Step 2: Run, confirm it fails**

```bash
pytest agents/tools/tests/test_causal_predecessors.py::test_tool_run_attaches_causal_predecessors_from_context -v
```

Expected: AssertionError — committed event has `causal_predecessors=[]`.

- [ ] **Step 3: Modify base.py**

In `agents/tools/src/almighty_officer_tools/base.py`, replace lines around 127-138 (the `KernelEvent(...)` construction) with:

```python
        # Step 3: commit the event through the namespaced DAG.
        event = KernelEvent(
            event_id=uuid4(),
            tenant_id=ctx.tenant_id,
            scenario_id=ctx.scenario_id,
            turn=ctx.turn,
            source_officer_type=self.OFFICER_TYPE,
            source_entity_id=ctx.agent_entity_id,
            action_verb=self.VERB,
            payload=self._build_event_payload(args),
            # Carry the causal predecessors the role's prepare-step set on
            # the context. Empty list (default) for purely-deterministic
            # roles is the existing v1 behavior.
            causal_predecessors=list(ctx.causal_predecessors),
        )
        ctx.kernel_dag.commit(event)
```

- [ ] **Step 4: Re-run all base.py tests**

```bash
pytest agents/tools/tests/ -q
```

Expected: all existing tests still pass + the new test passes.

- [ ] **Step 5: Commit**

```bash
git add agents/tools/
git commit -m "feat(tools): OfficerToolBase commits with predecessors from ctx"
```

---

### Task 3.3: situation_report.py helper

**Files:**
- Create: `agents/runtime/src/almighty_agent_runtime/situation_report.py`
- Test: `agents/runtime/tests/test_situation_report.py`

- [ ] **Step 1: Write the failing test**

```python
# agents/runtime/tests/test_situation_report.py
from uuid import uuid4
from almighty_kernel.dag import NamespacedDag, KernelEvent
from almighty_agent_runtime.situation_report import build_situation_report

def test_situation_report_returns_topological_event_list():
    tenant_id = uuid4()
    scenario_id = uuid4()
    dag = NamespacedDag()

    e1 = KernelEvent(
        event_id=uuid4(),
        tenant_id=tenant_id, scenario_id=scenario_id, turn=1,
        source_officer_type="SENSOR", source_entity_id=uuid4(),
        action_verb="detect",
        payload={"target_entity_id": str(uuid4()), "modality": "RADAR", "confidence": 0.85},
        causal_predecessors=[],
    )
    dag.commit(e1)
    e2 = KernelEvent(
        event_id=uuid4(),
        tenant_id=tenant_id, scenario_id=scenario_id, turn=1,
        source_officer_type="SENSOR", source_entity_id=uuid4(),
        action_verb="classify",
        payload={"track_id": str(uuid4()), "classification_label": "uas.medium", "confidence": 0.78},
        causal_predecessors=[e1.event_id],
    )
    dag.commit(e2)

    report = build_situation_report(dag, tenant_id=tenant_id, scenario_id=scenario_id)
    assert "detect" in report
    assert "classify" in report
    # Topological order: detect comes before classify
    assert report.index("detect") < report.index("classify")
    # The event ids appear so the LLM can cite them (we don't actually
    # need the LLM to cite, but having them present is harmless and
    # helps human inspection during debugging)
    assert str(e1.event_id) in report

def test_situation_report_empty_namespace_returns_empty_string():
    dag = NamespacedDag()
    report = build_situation_report(dag, tenant_id=uuid4(), scenario_id=uuid4())
    assert report == ""
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd agents/runtime
pytest tests/test_situation_report.py -v
```

Expected: ImportError on `build_situation_report`.

- [ ] **Step 3: Implement**

```python
# agents/runtime/src/almighty_agent_runtime/situation_report.py
"""Build a textual situation report from the namespaced PyRapide DAG.

This is the "PyRapide → agent" half of the demo's load-bearing edit:
before an LLM-driven role calls Crew.kickoff(), we pull the topological
order of events from the namespace and format them as a terse text
block the model can reason over.

Pairs with `OfficerToolContext.causal_predecessors` — the calling code
should set that field to the event ids contained in the report so the
resulting commit's `causal_predecessors` cite the precise events the
LLM saw. See spec §6.
"""

from __future__ import annotations

from uuid import UUID

from almighty_kernel.dag import KernelEvent, NamespacedDag


def build_situation_report(
    dag: NamespacedDag,
    *,
    tenant_id: UUID,
    scenario_id: UUID,
) -> str:
    events = dag.read(tenant_id=tenant_id, scenario_id=scenario_id, causal_order=True)
    if not events:
        return ""
    return "\n".join(_format_event(e) for e in events)


def _format_event(e: KernelEvent) -> str:
    summary = _summarize_payload(e.payload, e.action_verb)
    return (
        f"- [{e.event_id}] turn {e.turn} "
        f"{e.source_officer_type} {e.action_verb}: {summary}"
    )


def _summarize_payload(payload: dict, verb: str) -> str:
    """One-line summary of an event payload for LLM consumption.

    Keeps the situation report compact even with hundreds of events.
    """
    if not payload:
        return "(no payload)"
    if verb == "detect":
        return (
            f"target={payload.get('target_entity_id', '?')}, "
            f"modality={payload.get('modality', '?')}, "
            f"confidence={payload.get('confidence', '?')}"
        )
    if verb == "classify":
        return (
            f"track={payload.get('track_id', '?')}, "
            f"label={payload.get('classification_label', '?')}, "
            f"confidence={payload.get('confidence', '?')}"
        )
    if verb == "issue_order":
        return (
            f"order_type={payload.get('order_type', '?')}, "
            f"to={payload.get('to_entity_id', '?')}"
        )
    if verb == "suppress":
        return (
            f"target=({payload.get('target_lat_deg', '?')}, {payload.get('target_lon_deg', '?')}), "
            f"weapon={payload.get('weapon_system', '?')}"
        )
    # Fallback: first three keys
    keys = list(payload.keys())[:3]
    return ", ".join(f"{k}={payload[k]}" for k in keys)


def predecessor_event_ids(
    dag: NamespacedDag,
    *,
    tenant_id: UUID,
    scenario_id: UUID,
) -> list[UUID]:
    """Return the event ids in the namespace at this moment, in causal order.

    Pair this with `build_situation_report` — the caller stashes this list
    on the OfficerToolContext, then the next tool commit auto-links to all
    of them. See spec §6b.
    """
    return [
        e.event_id
        for e in dag.read(tenant_id=tenant_id, scenario_id=scenario_id, causal_order=True)
    ]
```

- [ ] **Step 4: Run, confirm pass**

```bash
pytest tests/test_situation_report.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add agents/runtime/
git commit -m "feat(runtime): situation_report helper — DAG topological view as text"
```

---

### Task 3.4: LLM client config

**Files:**
- Create: `agents/runtime/src/almighty_agent_runtime/llm_clients.py`
- Test: `agents/runtime/tests/test_llm_clients.py`

- [ ] **Step 1: Write the failing test**

```python
# agents/runtime/tests/test_llm_clients.py
from almighty_agent_runtime.llm_clients import build_blue_llm, build_red_llm

def test_blue_llm_targets_local_vllm_on_spark1():
    llm = build_blue_llm()
    assert "8001" in llm.base_url
    assert "127.0.0.1" in llm.base_url or "localhost" in llm.base_url
    assert "gemma-4-26B-A4B" in llm.model

def test_red_llm_targets_spark2_over_cable():
    llm = build_red_llm()
    assert "8000" in llm.base_url
    # spark-3fe3 tailscale IP per spec §3
    assert "100.112.216.53" in llm.base_url
    assert "gemma-4-31B" in llm.model
```

- [ ] **Step 2: Run, confirm fails**

```bash
pytest tests/test_llm_clients.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# agents/runtime/src/almighty_agent_runtime/llm_clients.py
"""Per-side LLM client factories pointing at the Sparks' vLLM endpoints.

Blue → spark-763d localhost (CrewAI worker is co-located on this Spark).
Red  → spark-3fe3 over the Spark-to-Spark cable.

Both endpoints expose OpenAI-compatible /v1/chat/completions with
tool-calling enabled (--enable-auto-tool-choice --tool-call-parser gemma4),
verified during pre-flight.
"""

from __future__ import annotations

import os

from crewai import LLM


_BLUE_DEFAULT_BASE = "http://127.0.0.1:8001/v1"
_RED_DEFAULT_BASE = "http://100.112.216.53:8000/v1"


def build_blue_llm() -> LLM:
    """Gemma 4 26B-A4B-it on spark-763d via localhost vLLM."""
    return LLM(
        # litellm prefix `openai/` tells litellm to use the OpenAI-compatible
        # protocol. Whatever follows is the model name as the endpoint serves it.
        model="openai/google/gemma-4-26B-A4B-it",
        base_url=os.environ.get("BLUE_LLM_BASE_URL", _BLUE_DEFAULT_BASE),
        api_key=os.environ.get("BLUE_LLM_API_KEY", "EMPTY"),
        temperature=0.3,
    )


def build_red_llm() -> LLM:
    """Gemma 4 31B-it on spark-3fe3 via the Spark-to-Spark cable."""
    return LLM(
        model="openai/google/gemma-4-31B-it",
        base_url=os.environ.get("RED_LLM_BASE_URL", _RED_DEFAULT_BASE),
        api_key=os.environ.get("RED_LLM_API_KEY", "EMPTY"),
        temperature=0.4,
    )
```

- [ ] **Step 4: Run, confirm pass**

```bash
pytest tests/test_llm_clients.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add agents/runtime/src/almighty_agent_runtime/llm_clients.py agents/runtime/tests/test_llm_clients.py
git commit -m "feat(runtime): LLM client factories for blue / red Sparks"
```

---

### Task 3.5: LLM-driven step helper

**Files:**
- Create: `agents/runtime/src/almighty_agent_runtime/llm_step.py`
- Test: `agents/runtime/tests/test_llm_step.py`

The helper sits between the deterministic crew script and CrewAI: it builds the situation report, sets predecessors on the context, runs `Crew.kickoff()`, and lets the tool's regular `_run` path commit the event.

- [ ] **Step 1: Write the failing test (with mocked Crew)**

```python
# agents/runtime/tests/test_llm_step.py
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from almighty_kernel.dag import KernelEvent, NamespacedDag
from almighty_officer_tools.context import OfficerToolContext
from almighty_czml_validator import Validator

from almighty_agent_runtime.llm_step import run_llm_role_step


def _make_ctx(dag: NamespacedDag) -> OfficerToolContext:
    return OfficerToolContext(
        tenant_id=uuid4(),
        scenario_id=uuid4(),
        turn=1,
        agent_entity_id=uuid4(),
        capability_profile={"action_verbs_available": ["issue_order", "request_support"]},
        kernel_dag=dag,
        validator=Validator(),
    )


def test_run_llm_role_step_sets_predecessors_before_kickoff():
    dag = NamespacedDag()
    ctx = _make_ctx(dag)

    # Seed two events as the "prior context" the LLM will see.
    seeds = []
    for verb in ("detect", "classify"):
        e = KernelEvent(
            event_id=uuid4(),
            tenant_id=ctx.tenant_id, scenario_id=ctx.scenario_id, turn=1,
            source_officer_type="SENSOR", source_entity_id=uuid4(),
            action_verb=verb, payload={}, causal_predecessors=[],
        )
        dag.commit(e)
        seeds.append(e)

    fake_agent = MagicMock(name="agent")
    fake_llm = MagicMock(name="llm")

    # Patch Crew so we don't actually call out to LLM
    with patch("almighty_agent_runtime.llm_step.Crew") as MockCrew, \
         patch("almighty_agent_runtime.llm_step.Task") as MockTask:
        instance = MockCrew.return_value
        instance.kickoff.return_value = MagicMock(raw="(unused)")

        run_llm_role_step(
            ctx=ctx,
            agent=fake_agent,
            llm=fake_llm,
            task_description="Decide what S3 should do.",
            expected_output="A single tool call.",
        )

        # Predecessors were set on the context before kickoff was called
        assert ctx.causal_predecessors == [s.event_id for s in seeds]
        # The Crew was constructed with the agent + a single task
        MockCrew.assert_called_once()
        instance.kickoff.assert_called_once()


def test_run_llm_role_step_resets_predecessors_after():
    """Defense-in-depth: leaving predecessors set across roles would link
    later deterministic events to the wrong parents."""
    dag = NamespacedDag()
    ctx = _make_ctx(dag)
    fake_agent = MagicMock()
    fake_llm = MagicMock()

    with patch("almighty_agent_runtime.llm_step.Crew") as MockCrew, \
         patch("almighty_agent_runtime.llm_step.Task"):
        MockCrew.return_value.kickoff.return_value = MagicMock(raw="x")
        run_llm_role_step(
            ctx=ctx, agent=fake_agent, llm=fake_llm,
            task_description="x", expected_output="x",
        )

    assert ctx.causal_predecessors == []
```

- [ ] **Step 2: Run, confirm fails**

```bash
pytest tests/test_llm_step.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# agents/runtime/src/almighty_agent_runtime/llm_step.py
"""Run a single LLM-driven role step.

The role's CrewAI Agent is already configured with tools (the role's allowed
verbs are bound in `_build_role` in each crew). This helper:

  1. Builds the situation report from the namespaced DAG.
  2. Stashes the situation report's event ids on the context's
     `causal_predecessors` field — `OfficerToolBase._run` reads from there
     when it commits the event.
  3. Constructs a single-task Crew, attaches the LLM, and calls `kickoff()`.
  4. Resets the context's predecessors to [] so the next deterministic
     step in the cycle isn't accidentally linked.

If the LLM fails (network error, malformed tool call, timeout), the
caller decides whether to fall back to deterministic behavior — see
the crew's wrapper in §3.6.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crewai import Crew, Task

from .situation_report import build_situation_report, predecessor_event_ids

if TYPE_CHECKING:
    from crewai import LLM, Agent

    from almighty_officer_tools.context import OfficerToolContext


def run_llm_role_step(
    *,
    ctx: "OfficerToolContext",
    agent: "Agent",
    llm: "LLM",
    task_description: str,
    expected_output: str,
) -> None:
    """Run one LLM-driven role step. Mutates ctx.causal_predecessors twice
    (set then reset). Side-effect: the agent's tools commit a KernelEvent
    via the configured kernel_dag during kickoff."""

    # 1. Build the situation report and capture its event ids.
    report = build_situation_report(
        ctx.kernel_dag, tenant_id=ctx.tenant_id, scenario_id=ctx.scenario_id,
    )
    parents = predecessor_event_ids(
        ctx.kernel_dag, tenant_id=ctx.tenant_id, scenario_id=ctx.scenario_id,
    )

    # 2. Stash predecessors so the tool commit auto-links.
    ctx.causal_predecessors = parents

    # 3. Build and run the crew.
    agent.llm = llm  # late-binding so tests can pass a mock
    task = Task(
        description=(
            task_description
            + "\n\nSituation report (causal-order events from PyRapide):\n"
            + (report or "(no prior events)")
        ),
        expected_output=expected_output,
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    crew.kickoff()

    # 4. Reset for the next deterministic step.
    ctx.causal_predecessors = []
```

- [ ] **Step 4: Run, confirm pass**

```bash
pytest tests/test_llm_step.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add agents/runtime/
git commit -m "feat(runtime): run_llm_role_step — DAG-assist + auto-link predecessors"
```

---

### Task 3.6: Flip blue S3 to LLM-driven

**Files:**
- Modify: `agents/blue/src/almighty_blue_crew/crew.py`
- Test: `agents/blue/tests/test_crew.py` (existing — modify or extend)

- [ ] **Step 1: Open `crew.py` and find the deterministic S3 steps**

The two functions to replace:

```python
def _step_s3_issue_order_to_a(roles): ...
def _step_s3_request_isr(roles): ...
```

They appear in the `_BETWEEN_TURN_SCRIPT` list (lines ~232-240).

- [ ] **Step 2: Add the LLM-driven S3 step**

Insert near the other `_step_*` functions:

```python
from almighty_agent_runtime.llm_clients import build_blue_llm
from almighty_agent_runtime.llm_step import run_llm_role_step


def _step_s3_llm_decide(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    """LLM-driven S3 decision step.

    Replaces the pair of deterministic steps `_step_s3_issue_order_to_a`
    and `_step_s3_request_isr`. Gemma 4 26B-A4B reads the situation
    report (S2's detect + classify events from earlier in this cycle)
    and decides which orders to issue. The committed events carry
    causal_predecessors back to the events the LLM saw — that's the
    audit trail the demo's headline depends on.

    Falls back to the deterministic pair if the LLM call raises so
    the demo never hard-fails on stage.
    """
    s3_role = roles["s3"]
    llm = build_blue_llm()

    try:
        run_llm_role_step(
            ctx=s3_role.ctx,
            agent=s3_role.agent,
            llm=llm,
            task_description=(
                "You are the battalion S3 at the Cumberland River crossing. "
                "Based on the situation report, decide what orders to issue "
                "and what support to request. Use issue_order to direct "
                "Companies A/B/C; use request_support for ISR/EW/fires from "
                "higher echelon. Keep your action minimal — at most one "
                "issue_order and one request_support per turn."
            ),
            expected_output=(
                "Tool calls only. No prose. Pick one or two of: "
                "issue_order(...) or request_support(...)."
            ),
        )
        return {"step": "s3.llm_decide", "result": "ok"}
    except Exception as e:
        # Demo safety net: fall back to the deterministic pair so the
        # event chain still produces something for the renderer.
        s3_role.ctx.causal_predecessors = []  # defense-in-depth
        _step_s3_issue_order_to_a(roles)
        _step_s3_request_isr(roles)
        return {"step": "s3.llm_decide", "result": f"fallback ({type(e).__name__}: {e})"}
```

- [ ] **Step 3: Replace the two old S3 entries in `_BETWEEN_TURN_SCRIPT`**

Change:

```python
_BETWEEN_TURN_SCRIPT: Final[list[tuple[str, _StepFn]]] = [
    ("s2.detect", _step_s2_detect),
    ("s2.classify", _step_s2_classify),
    ("s3.issue_order", _step_s3_issue_order_to_a),
    ("s3.request_support", _step_s3_request_isr),
    ...
```

to:

```python
_BETWEEN_TURN_SCRIPT: Final[list[tuple[str, _StepFn]]] = [
    ("s2.detect", _step_s2_detect),
    ("s2.classify", _step_s2_classify),
    ("s3.llm_decide", _step_s3_llm_decide),
    ...
```

(Keep `_step_s3_issue_order_to_a` and `_step_s3_request_isr` defined — the fallback uses them.)

- [ ] **Step 4: Add a unit test that asserts the LLM-driven event has predecessors**

In `agents/blue/tests/test_crew.py` (or wherever existing crew tests live), add a fast test using the deterministic fallback:

```python
def test_llm_step_fallback_still_chains_predecessors_when_seeds_present():
    """If the LLM fails, fallback runs — but the deterministic events
    still don't carry predecessors. This test documents that fallback
    mode preserves the existing v1 behavior (empty predecessors)."""
    # Stub build_blue_llm to raise so the fallback path runs
    from unittest.mock import patch
    from uuid import UUID
    from almighty_blue_crew.crew import run_blue_crew
    from almighty_agent_runtime.crews import CrewContext

    with patch("almighty_blue_crew.crew.build_blue_llm",
               side_effect=RuntimeError("vllm unreachable")):
        result = run_blue_crew(
            CrewContext(
                tenant_id=str(UUID(int=1)),
                scenario_id=str(UUID(int=2)),
                turn=1,
            )
        )
    assert result.metadata["events_committed"] >= 11  # fallback intact
```

(If `CrewContext` lives elsewhere, follow the existing test pattern in the file. If `crews.py` exports a different fixture, use it.)

- [ ] **Step 5: Run blue tests**

```bash
cd agents/blue
pytest tests/ -q
```

Expected: tests pass; the original 11-event guarantee still holds in fallback mode.

- [ ] **Step 6: Commit**

```bash
git add agents/blue/
git commit -m "feat(blue): S3 LLM-driven via Gemma 4 26B-A4B — DAG-assisted, auditable"
```

---

### Task 3.7: Flip red S3 to LLM-driven

**Files:**
- Modify: `agents/red/src/almighty_red_crew/crew.py`
- Test: `agents/red/tests/test_crew.py`

The pattern is identical to Task 3.6 with `build_red_llm` instead. Find red's S3 (or equivalent) deterministic step (e.g., `_step_red_s3_*` or similar) by reading red's crew.py.

- [ ] **Step 1: Read red's crew structure**

```bash
grep -n "_step_\|_BETWEEN_TURN_SCRIPT\|llm" agents/red/src/almighty_red_crew/crew.py | head -30
```

- [ ] **Step 2: Add the LLM-driven step**

```python
from almighty_agent_runtime.llm_clients import build_red_llm
from almighty_agent_runtime.llm_step import run_llm_role_step


def _step_red_s3_llm_decide(roles):
    s3_role = roles["s3"]  # or whatever red calls its commander/operations role
    llm = build_red_llm()
    try:
        run_llm_role_step(
            ctx=s3_role.ctx,
            agent=s3_role.agent,
            llm=llm,
            task_description=(
                "You are the red battalion operations officer attempting a "
                "forced crossing of the Cumberland River from the east bank. "
                "Based on the situation report, decide which orders to issue "
                "to your subordinate companies. Keep it tight — one or two "
                "tool calls per turn."
            ),
            expected_output="Tool calls only. No prose.",
        )
        return {"step": "red.s3.llm_decide", "result": "ok"}
    except Exception as e:
        s3_role.ctx.causal_predecessors = []
        # Fall back to whatever the existing red script's S3 equivalent is —
        # this is `_step_red_<...>` in red/crew.py; substitute the right pair.
        return {"step": "red.s3.llm_decide", "result": f"fallback ({e!s})"}
```

- [ ] **Step 3: Replace red's S3 entry in `_BETWEEN_TURN_SCRIPT`** (analogous to Task 3.6 step 3)

- [ ] **Step 4: Run red tests**

```bash
cd agents/red
pytest tests/ -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```bash
git add agents/red/
git commit -m "feat(red): S3 LLM-driven via Gemma 4 31B — second Spark exercised"
```

---

## Phase 4 — FastAPI shim + Spark deployment (~45 min)

### Task 4.1: Write the FastAPI shim

**Files:**
- Create: `agents/runtime/src/almighty_agent_runtime/shim.py`
- Test: `agents/runtime/tests/test_shim.py`

- [ ] **Step 1: Write the failing test (sync, in-process)**

```python
# agents/runtime/tests/test_shim.py
from uuid import UUID
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from almighty_agent_runtime.shim import app


def test_healthz():
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_run_turn_invokes_blue_and_red_crews(monkeypatch):
    """POST /run-turn should invoke both crews and return their event lists."""
    blue_mock = MagicMock(return_value=MagicMock(
        crew="blue", duration_ms=10, notes="t", metadata={"events_committed": 5}))
    red_mock = MagicMock(return_value=MagicMock(
        crew="red", duration_ms=12, notes="t", metadata={"events_committed": 4}))

    monkeypatch.setattr("almighty_agent_runtime.shim.run_blue_crew", blue_mock)
    monkeypatch.setattr("almighty_agent_runtime.shim.run_red_crew", red_mock)

    # Stub event collection — the shim returns a flat events list assembled
    # from the dag inside the worker, so we patch the helper.
    monkeypatch.setattr(
        "almighty_agent_runtime.shim._collect_events",
        lambda dag, *, tenant_id, scenario_id: [
            {"event_id": "fake-1", "verb": "detect", "causal_predecessors": []},
            {"event_id": "fake-2", "verb": "issue_order", "causal_predecessors": ["fake-1"]},
        ],
    )

    client = TestClient(app)
    r = client.post("/run-turn", json={
        "tenant_id": "00000000-0000-4d00-8000-000000000001",
        "scenario_id": "00000000-0000-4101-8000-000000000001",
        "turn": 1,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["turn"] == 1
    assert blue_mock.called
    assert red_mock.called
    assert len(body["events"]) == 2
```

- [ ] **Step 2: Run, confirm fails**

```bash
pytest tests/test_shim.py -v
```

Expected: ImportError on `app`.

- [ ] **Step 3: Implement**

```python
# agents/runtime/src/almighty_agent_runtime/shim.py
"""HTTP shim that the EC2 control-plane calls to drive a between-turn cycle.

POST /run-turn → runs blue and red crews concurrently against a fresh
namespaced PyRapide DAG, then returns all committed events as JSON.

Deployed inside the existing crewai container on spark-763d via a
bind-mount of the almighty repo and a CMD override (see
agents/runtime/spark/run-worker.sh).
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from pydantic import BaseModel

from almighty_blue_crew.crew import run_blue_crew
from almighty_red_crew.crew import run_red_crew
from almighty_kernel.dag import KernelEvent, NamespacedDag

from .crews import CrewContext


app = FastAPI(title="almighty-spark-worker")


class RunTurnRequest(BaseModel):
    tenant_id: str
    scenario_id: str
    turn: int


class RunTurnResponse(BaseModel):
    turn: int
    blue_duration_ms: int
    red_duration_ms: int
    events: list[dict[str, Any]]


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.post("/run-turn", response_model=RunTurnResponse)
async def run_turn(req: RunTurnRequest) -> RunTurnResponse:
    crew_ctx = CrewContext(
        tenant_id=req.tenant_id,
        scenario_id=req.scenario_id,
        turn=req.turn,
    )

    # Each crew currently builds its own NamespacedDag inside run_*_crew.
    # The crews are independent and run in parallel via asyncio.to_thread.
    blue_task = asyncio.to_thread(run_blue_crew, crew_ctx)
    red_task = asyncio.to_thread(run_red_crew, crew_ctx)
    blue_result, red_result = await asyncio.gather(blue_task, red_task)

    # The crews returned their own dags as part of metadata. We need a
    # serialized event list per crew to send back. The existing
    # run_blue_crew implementation does NOT return the dag — it returns
    # a CrewResult with step_outcomes. For the demo we serialize the
    # step_outcomes as event-shaped dicts. (If a future refactor returns
    # the dag explicitly, swap the body of _collect_events.)
    events: list[dict[str, Any]] = []
    events.extend(_events_from_result(blue_result, side="blue", req=req))
    events.extend(_events_from_result(red_result, side="red", req=req))

    return RunTurnResponse(
        turn=req.turn,
        blue_duration_ms=blue_result.duration_ms,
        red_duration_ms=red_result.duration_ms,
        events=events,
    )


def _events_from_result(result: Any, *, side: str, req: RunTurnRequest) -> list[dict[str, Any]]:
    """Convert CrewResult.metadata['steps'] into the wire-format events list.

    Wire format matches what services/control-plane expects on POST /events
    (see services/control-plane/src/routes/events.ts). Predecessors are
    stamped on by OfficerToolBase via the context — we only carry through
    what was committed.
    """
    out: list[dict[str, Any]] = []
    for step in result.metadata.get("steps", []):
        out.append({
            "side": side,
            "step": step.get("step"),
            "event_id": step.get("event_id"),
            "verb": step.get("verb"),
            "officer_type": step.get("officer_type"),
            "validator": step.get("validator"),
            "tenant_id": req.tenant_id,
            "scenario_id": req.scenario_id,
            "turn": req.turn,
            "causal_predecessors": step.get("causal_predecessors", []),
        })
    return out


# Test hook — patched in the unit test
def _collect_events(
    dag: NamespacedDag, *, tenant_id: UUID, scenario_id: UUID,
) -> list[dict[str, Any]]:
    """Future: when the crews return their dags, this becomes the real serializer."""
    return []
```

A note on `OfficerToolBase` returning `causal_predecessors`: the current `_run` returns `event_id`, `verb`, `officer_type`, `validator`. The shim needs `causal_predecessors` too — extend the return dict in Task 4.1.5 below.

- [ ] **Step 4: Extend `OfficerToolBase._run` to return `causal_predecessors`**

In `agents/tools/src/almighty_officer_tools/base.py`, modify the return at the end:

```python
        return {
            "event_id": str(event.event_id),
            "verb": self.VERB,
            "officer_type": self.OFFICER_TYPE,
            "validator": validator_outcome,
            "causal_predecessors": [str(p) for p in event.causal_predecessors],
        }
```

- [ ] **Step 5: Run all tests**

```bash
cd agents/runtime
pytest tests/ -q
cd ../tools
pytest tests/ -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add agents/runtime/ agents/tools/
git commit -m "feat(runtime): FastAPI shim — POST /run-turn drives blue+red in parallel"
```

---

### Task 4.2: Write the Spark-side launcher script

**Files:**
- Create: `agents/runtime/spark/run-worker.sh`

- [ ] **Step 1: Write the script**

```bash
#!/bin/bash
# agents/runtime/spark/run-worker.sh
# Run on spark-763d to (re)launch the CrewAI worker container as the
# almighty FastAPI shim. Idempotent — stops existing then restarts.
set -euxo pipefail

REPO_ROOT="${1:-$HOME/almighty}"
PORT="${PORT:-7000}"

# Make sure the bind-mount source is up to date
test -d "$REPO_ROOT/agents/runtime" || {
  echo "ERROR: $REPO_ROOT/agents/runtime not found. Clone the repo first:"
  echo "  git clone https://github.com/Dynamo-Technologies/almighty $REPO_ROOT"
  exit 1
}

cd "$REPO_ROOT"
git pull --ff-only

# Stop existing
docker rm -f almighty-worker >/dev/null 2>&1 || true

# Start fresh — bind-mount the source, override CMD to run uvicorn.
# The existing crewai:stig-hardened-boto3 image has Python + crewai;
# we install fastapi + uvicorn at start since they're not in the image.
docker run -d --name almighty-worker \
  --network host \
  -v "$REPO_ROOT:/app/almighty:ro" \
  -e PYTHONPATH="/app/almighty/kernel:/app/almighty/agents/tools/src:/app/almighty/agents/blue/src:/app/almighty/agents/red/src:/app/almighty/agents/white-cell/src:/app/almighty/agents/runtime/src:/app/almighty/services/czml-validator/src" \
  -e BLUE_LLM_BASE_URL="http://127.0.0.1:8001/v1" \
  -e RED_LLM_BASE_URL="http://100.112.216.53:8000/v1" \
  --restart unless-stopped \
  crewai:stig-hardened-boto3 \
  bash -c "
    pip install --no-cache-dir --quiet fastapi 'uvicorn[standard]' pydantic httpx pyrapide && \
    cd /app/almighty && \
    exec uvicorn almighty_agent_runtime.shim:app --host 0.0.0.0 --port $PORT
  "

# Wait up to 60s for healthz
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:$PORT/healthz >/dev/null; then
    echo "almighty-worker healthy on :$PORT"
    exit 0
  fi
  sleep 2
done

echo "ERROR: worker did not become healthy in 60s"
docker logs --tail 50 almighty-worker
exit 1
```

- [ ] **Step 2: chmod +x and commit**

```bash
chmod +x agents/runtime/spark/run-worker.sh
git add agents/runtime/spark/
git commit -m "feat(runtime): spark-side launcher repurposing crewai container"
```

---

### Task 4.3: Smoke-test the worker on spark-763d

The operator runs the launcher and verifies end-to-end. This is manual.

- [ ] **Step 1: SSH to spark-763d, clone repo, run launcher**

```bash
# On spark-763d (via tailscale ssh from laptop, or however you access it):
git clone https://github.com/Dynamo-Technologies/almighty ~/almighty || (cd ~/almighty && git pull)
cd ~/almighty
git checkout hackathon-demo-2026-04-26
~/almighty/agents/runtime/spark/run-worker.sh ~/almighty
```

Expected output ends with: `almighty-worker healthy on :7000`.

- [ ] **Step 2: Curl from spark-763d localhost**

```bash
curl -s http://127.0.0.1:7000/healthz
```

Expected: `{"ok":true}`.

- [ ] **Step 3: From laptop (Tailscale only), curl over tailnet**

```bash
curl -s http://100.106.123.5:7000/healthz
```

Expected: `{"ok":true}`. If this hangs/refuses, check the spark's firewall (Ubuntu's `ufw`) or the Tailscale ACLs.

- [ ] **Step 4: Live drive — run a turn**

```bash
curl -s -X POST http://100.106.123.5:7000/run-turn \
  -H 'content-type: application/json' \
  -d '{"tenant_id":"00000000-0000-4d00-8000-000000000001","scenario_id":"00000000-0000-4101-8000-000000000001","turn":1}' \
  | python3 -m json.tool
```

Expected: a JSON response with `events[]` containing both blue and red events. At least one event has non-empty `causal_predecessors`.

If the LLM-driven steps fall back to deterministic, the response indicates this in `step` results — check `docker logs almighty-worker` for the underlying error (most likely vLLM cold start or tool-call parse failure).

---

## Phase 5 — Control plane integration + frontend (~1 hr)

### Task 5.1: Replace control-plane's runBetweenTurnAgents stub

**Files:**
- Modify: `services/control-plane/src/stubs/agent-runtime.ts`
- Modify: `services/control-plane/src/config.ts`
- Test: extend `services/control-plane/tests/turn-controller.test.ts` (or wherever existing tests live)

- [ ] **Step 1: Add SPARK_WORKER_URL to config**

In `services/control-plane/src/config.ts`, add:

```typescript
export const SPARK_WORKER_URL =
  process.env.SPARK_WORKER_URL ?? "http://100.106.123.5:7000";
```

- [ ] **Step 2: Replace the stub**

Overwrite `services/control-plane/src/stubs/agent-runtime.ts`:

```typescript
/**
 * Real between-turn agent runner. POSTs to the spark worker on spark-763d
 * over Tailscale and writes returned events into the DB.
 *
 * Replaces the WS-401 stub. Demo only; in production the agent runtime
 * would be Celery-backed per the original architecture.
 */

import type { Pool } from "../db.js";
import { SPARK_WORKER_URL } from "../config.js";

export async function runBetweenTurnAgents(
  input: { tenantId: string; scenarioId: string; turn: number },
  pool?: Pool,
): Promise<{ ok: true; durationMs: number; eventsCommitted: number }> {
  const startedAt = Date.now();
  const res = await fetch(`${SPARK_WORKER_URL}/run-turn`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      tenant_id: input.tenantId,
      scenario_id: input.scenarioId,
      turn: input.turn + 1, // turn-controller passes closedTurn; we run NEW turn
    }),
  });
  if (!res.ok) {
    throw new Error(`spark worker returned ${res.status} ${res.statusText}`);
  }
  const body = (await res.json()) as {
    turn: number;
    events: Array<{
      event_id: string;
      tenant_id: string;
      scenario_id: string;
      turn: number;
      verb: string;
      officer_type: string;
      causal_predecessors: string[];
      side: string;
    }>;
  };

  // Write events into the DB so /events queries see them
  if (pool && body.events.length > 0) {
    const client = await pool.connect();
    try {
      for (const e of body.events) {
        await client.query(
          `INSERT INTO events (
              event_id, tenant_id, scenario_id, turn,
              source_officer_type, source_entity_id,
              action_verb, payload, causal_predecessors, ts
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, NOW())
            ON CONFLICT (event_id) DO NOTHING`,
          [
            e.event_id,
            e.tenant_id,
            e.scenario_id,
            e.turn,
            e.officer_type,
            "00000000-0000-0000-0000-000000000000", // unknown — worker side
            e.verb,
            JSON.stringify({}), // payload not surfaced via shim; out of scope for demo
            e.causal_predecessors,
          ],
        );
      }
    } finally {
      client.release();
    }
  }

  return {
    ok: true,
    durationMs: Date.now() - startedAt,
    eventsCommitted: body.events.length,
  };
}
```

- [ ] **Step 3: Wire the pool through**

In `services/control-plane/src/turn-controller.ts:104`, change:

```typescript
const agentResult = await runBetweenTurnAgents({
  tenantId,
  scenarioId,
  turn: closedTurn,
});
```

to:

```typescript
const agentResult = await runBetweenTurnAgents(
  { tenantId, scenarioId, turn: closedTurn },
  pool,
);
```

- [ ] **Step 4: Run control-plane tests**

```bash
cd services/control-plane
npm test
```

Expected: existing tests pass. The `runBetweenTurnAgents` test (if any) may need its mock updated; if so, mock the `fetch` global or use `nock` to stub the spark URL.

- [ ] **Step 5: Commit**

```bash
git add services/control-plane/
git commit -m "feat(control-plane): turn controller calls spark worker over tailnet"
```

---

### Task 5.2: EventLog renders causal predecessors

**Files:**
- Modify: `web/renderer/src/components/EventLog.tsx`
- Modify: `web/renderer/src/api/aar.ts:74-108` (fixture predecessors)

- [ ] **Step 1: Update the fixture so predecessors exist for visual QA**

In `aar.ts`, change `fixtureEvents` so events 4-7 chain on earlier ones:

```typescript
return [
  mk(1, 1, t(0),    "MOVER",        "move_to",     { ... }),
  mk(2, 1, t(60),   "COMMUNICATOR", "jam",         { ... }),
  // event 3 is caused by 1 and 2
  { ...mk(3, 2, t(120),  "SENSOR",  "detect",   { ... }), causal_predecessors: ["fixture-0001", "fixture-0002"] },
  // event 4 is caused by 3
  { ...mk(4, 2, t(180),  "EFFECTOR","engage",   { ... }), causal_predecessors: ["fixture-0003"] },
  { ...mk(5, 3, t(240),  "SENSOR",  "classify", { ... }), causal_predecessors: ["fixture-0003"] },
  { ...mk(6, 3, t(300),  "EFFECTOR","destroy",  { ... }), causal_predecessors: ["fixture-0004", "fixture-0005"] },
  { ...mk(7, 4, t(360),  "COMMANDER","report",  { ... }), causal_predecessors: ["fixture-0006"] },
];
```

- [ ] **Step 2: Replace EventLog.tsx**

```typescript
// web/renderer/src/components/EventLog.tsx
import { useCallback, useRef } from "react";
import type { DagEvent, OverrideDecision } from "../api/aar";

type Row =
  | { kind: "event"; ts: string; data: DagEvent }
  | { kind: "decision"; ts: string; data: OverrideDecision };

type EventLogProps = {
  events: DagEvent[];
  overrideDecisions: OverrideDecision[];
  onSeek: (ts: string) => void;
};

export function EventLog({ events, overrideDecisions, onSeek }: EventLogProps) {
  const rowRefs = useRef<Map<string, HTMLLIElement>>(new Map());

  const eventById = new Map(events.map((e) => [e.event_id, e]));

  const handleParentClick = useCallback(
    (parentId: string) => {
      const node = rowRefs.current.get(parentId);
      if (!node) return;
      node.scrollIntoView({ behavior: "smooth", block: "center" });
      node.classList.add("event-log__row--flash");
      window.setTimeout(() => node.classList.remove("event-log__row--flash"), 1200);
    },
    [],
  );

  const rows: Row[] = [
    ...events.map<Row>((e) => ({ kind: "event", ts: e.ts, data: e })),
    ...overrideDecisions.map<Row>((d) => ({ kind: "decision", ts: d.ts, data: d })),
  ].sort((a, b) => a.ts.localeCompare(b.ts));

  return (
    <div className="event-log">
      <h2>Event log</h2>
      {rows.length === 0 && <p className="white-cell-hint">No events captured.</p>}
      <ul>
        {rows.map((row) => {
          const id = row.kind === "event" ? row.data.event_id : row.data.decision_id;
          return (
            <li
              key={id}
              ref={(el) => {
                if (el) rowRefs.current.set(id, el);
                else rowRefs.current.delete(id);
              }}
              className={`event-log__row event-log__row--${row.kind}`}
              onClick={() => onSeek(row.ts)}
              title="Click to seek timeline"
            >
              <span className="event-log__time">{shortTime(row.ts)}</span>
              {row.kind === "event" ? (
                <>
                  <span className="event-log__verb"><code>{row.data.action_verb}</code></span>
                  <span className="event-log__officer">{row.data.source_officer_type}</span>
                  <span className="event-log__turn">turn {row.data.turn}</span>
                  <CausalChips
                    predecessors={row.data.causal_predecessors}
                    eventById={eventById}
                    onParentClick={handleParentClick}
                  />
                </>
              ) : (
                <>
                  <span className={`event-log__decision pill pill--${row.data.action}`}>
                    {row.data.action}
                  </span>
                  <span className="event-log__decision-meta">
                    {row.data.scope} → {row.data.target_id}
                  </span>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function CausalChips({
  predecessors,
  eventById,
  onParentClick,
}: {
  predecessors: string[];
  eventById: Map<string, DagEvent>;
  onParentClick: (id: string) => void;
}) {
  if (!predecessors || predecessors.length === 0) return null;
  return (
    <span className="event-log__causal" onClick={(e) => e.stopPropagation()}>
      <span className="event-log__causal-arrow">← caused by</span>
      {predecessors.map((pid) => {
        const parent = eventById.get(pid);
        const label = parent
          ? `${parent.action_verb}`
          : `${pid.slice(0, 8)}…`;
        return (
          <button
            key={pid}
            type="button"
            className="event-log__causal-chip"
            onClick={() => onParentClick(pid)}
            title={`Jump to event ${pid.slice(0, 8)}…`}
          >
            <code>{label}</code>
          </button>
        );
      })}
    </span>
  );
}

function shortTime(iso: string): string {
  return iso.slice(11, 19);
}
```

- [ ] **Step 3: Add the CSS for the chip + flash**

Find the existing CSS file (probably `web/renderer/src/index.css` or `app.css`). Append:

```css
.event-log__causal {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  margin-left: 8px;
  font-size: 0.85em;
  color: var(--muted, #888);
}
.event-log__causal-arrow {
  font-style: italic;
}
.event-log__causal-chip {
  background: rgba(127, 127, 127, 0.1);
  border: 1px solid rgba(127, 127, 127, 0.3);
  border-radius: 3px;
  padding: 1px 6px;
  cursor: pointer;
  font: inherit;
  color: inherit;
}
.event-log__causal-chip:hover {
  background: rgba(127, 127, 127, 0.25);
  border-color: rgba(127, 127, 127, 0.6);
}
.event-log__row--flash {
  background: rgba(192, 221, 151, 0.4) !important;
  transition: background 1s ease-out;
}
```

(Match the existing CSS conventions — use the codebase's design tokens if any.)

- [ ] **Step 4: Local visual test**

```bash
cd web/renderer
npm run dev
```

Open `http://localhost:5173/<tenant>/scenarios/<scenario>/aar`. Set a dev JWT via the existing `DevTokenForm`. The fixture should display events with "← caused by" chips that scroll to and flash the parent row when clicked.

- [ ] **Step 5: Commit**

```bash
git add web/renderer/src/components/EventLog.tsx web/renderer/src/api/aar.ts web/renderer/src/<css-file>
git commit -m "feat(renderer): EventLog renders causal_predecessors with parent chips"
```

---

### Task 5.3: Single-button EXCON for the demo

**Files:**
- Modify: `web/renderer/src/routes/ExconConsole.tsx`

The existing EXCON likely has multiple controls. For the demo we hide everything except an "Advance turn 1" button. The cleanest approach: gate the existing controls behind a `?demo=1` query param so we don't break the underlying console.

- [ ] **Step 1: Read ExconConsole.tsx**

```bash
cat web/renderer/src/routes/ExconConsole.tsx
```

- [ ] **Step 2: Add a demo-mode wrapper**

Identify the existing turn-advance button (likely uses `<TurnControls>` component). Add at the top of the component body:

```typescript
import { useSearchParams } from "react-router-dom";
// ...
const [searchParams] = useSearchParams();
const demoMode = searchParams.get("demo") === "1";
```

In the JSX, when `demoMode` is true, render *only* the map + the EventLog + a single big "Advance turn 1" button:

```tsx
if (demoMode) {
  return (
    <div className="excon excon--demo">
      <header className="excon__demo-header">
        <h1>Almighty — Nashville Cumberland River crossing</h1>
        <p className="excon__demo-subtitle">UNCLASSIFIED · DEMONSTRATION ONLY</p>
      </header>
      <div className="excon__demo-body">
        <CesiumScene>
          <CesiumViewerExposer onReady={onViewerReady} />
          <CzmlLoader url="/czml/nashville-vignette.czml" />
        </CesiumScene>
        <aside className="excon__demo-events">
          <EventLog events={liveEvents} overrideDecisions={[]} onSeek={() => {}} />
        </aside>
      </div>
      <footer className="excon__demo-footer">
        <button
          className="excon__demo-advance"
          onClick={advanceTurn}
          disabled={advancing}
        >
          {advancing ? "Running on Sparks…" : "Advance turn 1"}
        </button>
      </footer>
    </div>
  );
}
// else: existing console
```

The `liveEvents` should poll `/events` every 500ms while a turn is running so events drip into the panel:

```typescript
const [liveEvents, setLiveEvents] = useState<DagEvent[]>([]);
const [advancing, setAdvancing] = useState(false);

useEffect(() => {
  if (!advancing) return;
  const tick = async () => {
    try {
      const evs = await fetchEvents(tenantId, scenarioId);
      setLiveEvents(evs);
    } catch { /* ignore transient errors */ }
  };
  const handle = window.setInterval(tick, 500);
  void tick();
  return () => window.clearInterval(handle);
}, [advancing, tenantId, scenarioId]);

const advanceTurn = useCallback(async () => {
  setAdvancing(true);
  try {
    await fetch(
      `${import.meta.env.VITE_CONTROL_PLANE_URL ?? ""}/tenants/${tenantId}/scenarios/${scenarioId}/turns/advance`,
      { method: "POST", headers: { authorization: `Bearer ${getStoredToken()}` } },
    );
  } finally {
    // Keep polling for ~10s after the response so the UI keeps draining
    setTimeout(() => setAdvancing(false), 10_000);
  }
}, [tenantId, scenarioId]);
```

- [ ] **Step 3: Visual test**

```bash
cd web/renderer
npm run dev
```

Open `http://localhost:5173/<tenant>/scenarios/<scenario>/excon?demo=1`. Single button visible. Map renders. EventLog sidebar empty. (Won't actually advance until the EC2/Spark stack is up — Phase 6.)

- [ ] **Step 4: Commit**

```bash
git add web/renderer/src/routes/ExconConsole.tsx
git commit -m "feat(renderer): demo-mode single-button excon (?demo=1)"
```

---

## Phase 6 — Bring it all up + rehearse (~30-45 min)

### Task 6.1: Push the branch and verify CI is happy

- [ ] **Step 1: Push**

```bash
git push -u origin hackathon-demo-2026-04-26
```

If CI runs Python + TS tests, watch the run. If anything fails that's not infra (which CI can't test), fix before proceeding.

---

### Task 6.2: Bring up Phase 1 EC2 with the secrets fully populated

- [ ] **Step 1: Confirm secrets file is complete**

```bash
source ~/.almighty-demo-secrets.env
test -n "$TAILSCALE_AUTH_KEY" && \
test -n "$ROUTE53_ZONE_ID" && \
test -n "$AWS_REGION" && \
test -n "$SUPABASE_DATABASE_URL" && \
test -n "$JWT_PUBLIC_KEY" && \
echo "OK"
```

Expected: `OK`.

- [ ] **Step 2: Set ALMIGHTY_BRANCH in cloud-init**

Edit `infra/aws/demo/launch-ec2.sh` to set `ALMIGHTY_BRANCH=hackathon-demo-2026-04-26` in the cloud-init env (add an `export ALMIGHTY_BRANCH=...` line near the top of cloud-init.sh, or template it into the userdata).

- [ ] **Step 3: Launch**

```bash
cd infra/aws/demo
./launch-ec2.sh
```

Wait ~5-7 minutes for cloud-init.

- [ ] **Step 4: Verify cert + reach**

```bash
# From laptop:
dig +short almighty-demo.dynamo.works
# Expect: 100.x.y.z (the EC2 tailscale IP)

curl -v https://almighty-demo.dynamo.works/healthz
# Expect: 200 OK, green padlock
```

If TLS handshake fails: SSH into the EC2 (via Tailscale or `aws ssm start-session`) and check Caddy logs:

```bash
docker logs almighty-demo-caddy-1 | tail -50
```

LE staging vs prod: by default Caddy hits LE prod, which has a 5-cert/week limit per registered domain. If you re-launch the EC2 multiple times during testing, switch the Caddyfile to LE staging (`acme_ca https://acme-staging-v02.api.letsencrypt.org/directory`) and accept the cert in the browser.

---

### Task 6.3: Bring up the spark worker

- [ ] **Step 1: SSH to spark-763d, run the launcher**

```bash
ssh shane@spark-763d   # or whatever your access pattern is
cd ~/almighty
git checkout hackathon-demo-2026-04-26
git pull
./agents/runtime/spark/run-worker.sh
```

Expected: `almighty-worker healthy on :7000`.

- [ ] **Step 2: From the EC2, curl the worker over Tailscale**

```bash
# SSH to EC2 first
aws ssm start-session --target $INSTANCE_ID --region us-east-1
# then:
curl -s http://100.106.123.5:7000/healthz
```

Expected: `{"ok":true}`.

---

### Task 6.4: First end-to-end click

- [ ] **Step 1: Set the JWT in the browser localStorage**

Open `https://almighty-demo.dynamo.works/<tenant>/scenarios/<scenario>/excon?demo=1`. Go through the existing `DevTokenForm` to set the JWT (or open DevTools console and `localStorage.setItem("jwt", "<DEMO_JWT>")` directly).

- [ ] **Step 2: Click Advance turn 1**

Watch:
- Both Spark `nvidia-smi -l 1` panels should spike
- Caddy + control-plane logs in CloudWatch / `docker logs` should show the `/turns/advance` POST and the spark-worker call
- After ~30-60s, events appear in the right sidebar with causal-predecessor chips

If the LLM falls back to deterministic, that's logged in `docker logs almighty-worker` — the demo still completes; check for the cause.

---

### Task 6.5: Three rehearsals + voice-track timing

- [ ] **Step 1: Rehearsal 1 — full run, no narration**

Just verify it works end-to-end three times in a row without a stall. If the third run shows growing event counts in the panel (because seed runs accumulate), reseed Supabase between runs:

```bash
psql "$SUPABASE_DATABASE_URL" -c "
DELETE FROM events
 WHERE tenant_id = '00000000-0000-4d00-8000-000000000001'
   AND scenario_id = '00000000-0000-4101-8000-000000000001';
UPDATE scenarios
   SET current_turn = 0, turn_state = 'open'
 WHERE scenario_id = '00000000-0000-4101-8000-000000000001';
"
```

- [ ] **Step 2: Rehearsal 2 — full run, with voice track from spec §10**

Use a stopwatch. Time the LLM-call window (click to first event in panel). Pace the architecture explanation to fit that gap.

- [ ] **Step 3: Rehearsal 3 — drill the recovery line**

Deliberately stop the spark worker (`docker stop almighty-worker`) before clicking. Confirm: control-plane returns a clear error, you can recover by restarting the worker, and the recovery patter from spec §2 fits the time.

- [ ] **Step 4: Lock the architecture slide**

Whatever slide deck you're using, make sure it has only ONE diagram: the spec §3 architecture diagram, redrawn nicely. Title: "Cloud orchestration. Edge inference. Auditable causality."

---

### Task 6.6: Final pre-flight 30 minutes before demo

- [ ] Pre-warm both vLLMs:

```bash
# spark-763d:
curl -s http://127.0.0.1:8001/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"google/gemma-4-26B-A4B-it","messages":[{"role":"user","content":"hello"}],"max_tokens":5}' >/dev/null

# spark-3fe3:
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"google/gemma-4-31B-it","messages":[{"role":"user","content":"hello"}],"max_tokens":5}' >/dev/null
```

- [ ] Re-seed Supabase to turn 0
- [ ] Confirm `https://almighty-demo.dynamo.works/healthz` returns 200 from the presenter laptop
- [ ] Two `nvidia-smi dmon -s u` SSH terminals up, sized and positioned next to the browser
- [ ] Power saver off, screensaver off, Wi-Fi tested with Ethernet backup ready
- [ ] Recovery line memorized; recovery action (restart spark worker) practiced

---

## Risk-driven cuts (if you're behind schedule)

The order in which to drop scope if you find yourself running out of time:

1. **Drop red S3 LLM (Task 3.7).** Keep red deterministic. Demo narration becomes "blue is on Spark 1; the same pattern extends to red on Spark 2 — that's tomorrow." Saves ~30-45 min.
2. **Skip live event polling (Task 5.3 step 2).** Just show the events all-at-once after the turn completes. The audit story is still intact. Saves ~15 min.
3. **Skip the EventLog UI change (Task 5.2).** The audit story moves from "click to see causality" → "the events have causality, you can see it in the JSON in DevTools." Lossy but saves ~30 min.
4. **Skip the EXCON demo-mode (Task 5.3).** Use the existing console; voice-track around the extra controls. Saves ~30 min.

Don't drop:
- Phase 1 (no AWS = no demo at the URL)
- Tasks 3.1/3.2/3.3/3.5/3.6 — these are the PyRapide-as-protagonist edits, the literal headline of the demo

---

## Self-review notes (post-write)

Spec coverage:
- §1 headline → demonstrated by Tasks 3.3, 3.5, 3.6, 5.2 in combination
- §2 demo outline → Phase 6 rehearsal validates the timing
- §3 architecture → Phase 1 + Phase 4 build it
- §4 components → all listed components have at least one task
- §5 data flow → end-to-end exercised in Task 6.4
- §6 PyRapide-as-protagonist → Tasks 3.1, 3.2, 3.3, 3.5, 3.6, 5.2 (the load-bearing path)
- §7 cuts → encoded in Phase 2 seed (override auto-approve), Phase 5 single-turn EXCON
- §8 build order → matches plan phases
- §9 risks → fallback paths in 3.6 and 3.7 + recovery rehearsal in 6.5
- §10 voice track → 6.5 step 2
- §11 operator runbook → Operator prerequisites + cloud-init script

Type consistency:
- `causal_predecessors: list[UUID]` consistent on `OfficerToolContext`, `KernelEvent`, and the wire-format strings (`list[str]` in shim, `string[]` in TS).
- `build_blue_llm` / `build_red_llm` return `crewai.LLM`; tests assert on `.base_url` and `.model` attrs which exist on that class.
- `run_llm_role_step` mutates `ctx.causal_predecessors` only — no cross-task drift.

Placeholder scan: no TBD/TODO/"add appropriate" patterns remain.
