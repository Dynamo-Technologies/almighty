# Almighty

Multi-tenant unclassified war simulation platform for Dynamo Technologies.

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

## Architecture

Four-tier architecture with cross-cutting concerns:

1. **Renderer** — Resium 3D battlespace, EXCON consoles, white cell UI, AAR
2. **Orchestration** — Multi-tenant control plane, override gateway, turn controller
3. **Agents** — CrewAI crews per echelon, between-turn execution, officer interface tools
4. **Kernel** — PyRapide DAG, DIS/HLA-adaptable schema, capability profiles

Cross-cutting: per-tenant AWS isolation, unclassified banner, capability-gated CZML templates, override policy plane.

See [docs/architecture.md](docs/architecture.md) for the full plan and [docs/diagrams/architecture-v1.svg](docs/diagrams/architecture-v1.svg) for the four-tier diagram.

## Notional theater

Nashville, TN — Cumberland River crossing.

## LLM endpoints — pluggable

Tier 3 agents (blue/red battalion S3) make LLM tool-calling requests
during the between-turn cycle. The provider is selected per side via
env var, which means the same crew code runs against either an on-prem
GPU or a cloud LLM with no other changes.

**vLLM (default — on-prem path).** `BLUE_LLM_PROVIDER=vllm` (default)
calls an OpenAI-compatible `/v1/chat/completions` endpoint at
`BLUE_LLM_BASE_URL`. Built around NVIDIA Sparks running Gemma 4
(26B-A4B-it for blue, 31B-it for red) under vLLM with
`--enable-auto-tool-choice --tool-call-parser gemma4`. Sparks reachable
from the cloud control plane via Tailscale; `BLUE_LLM_BASE_URL` /
`RED_LLM_BASE_URL` point at the tailnet IPs.

**Bedrock (fallback — cloud path).** `BLUE_LLM_PROVIDER=bedrock` calls
the AWS Bedrock Converse API on `BLUE_LLM_MODEL_ID` (default
`us.anthropic.claude-sonnet-4-5-20250929-v1:0` — the cross-region
inference profile). The worker container running on the
control-plane EC2 picks up creds from the instance metadata service;
the EC2 role grants `bedrock:InvokeModel` and `bedrock:Converse` on
the target model arns.

Same `_LLM_PROVIDER` flag for red: `RED_LLM_PROVIDER`. The two sides
can target different providers (useful if one Spark is up and the
other isn't, or for A/B comparison).

The crew code is provider-agnostic. Both paths return events with
`causal_predecessors` populated by the LLM-driven role-step's
auto-link, so the audit-trail story is identical regardless of which
LLM did the reasoning.

## Running the demo

Three deployment shapes. Pick the one that matches your environment.

### Prerequisites

- Docker + Docker Compose v2
- Node.js 20+ with pnpm via corepack (`corepack enable`)
- Python 3.11+ (for tests / local worker; production deploy doesn't need it)
- A Postgres database (Supabase free tier works; AWS RDS works; local Postgres works)
- One LLM source — either a self-hosted vLLM endpoint with tool-calling enabled,
  or AWS Bedrock access in your account

### Environment variables (complete list)

Required for the control-plane:
- `DATABASE_URL` — Postgres connection string
- `JWT_SECRET` — 32+ char random; HS256 signing for white-cell JWTs
- `SPARK_WORKER_URL` — base URL of the worker (default `http://localhost:7000`)

Required for the worker (FastAPI shim that calls the LLM):
- `BLUE_LLM_PROVIDER` — `vllm` (default) or `bedrock`
- `RED_LLM_PROVIDER` — `vllm` (default) or `bedrock`
- `AWS_REGION` — Bedrock region if `*_PROVIDER=bedrock` (e.g. `us-east-1`)

Per-provider:
- vLLM: `BLUE_LLM_BASE_URL` / `RED_LLM_BASE_URL` (e.g. `http://vllm-host:8001/v1`),
  optional `*_API_KEY` (default `EMPTY` for self-hosted)
- Bedrock: `BLUE_LLM_MODEL_ID` / `RED_LLM_MODEL_ID` (default
  `us.anthropic.claude-sonnet-4-5-20250929-v1:0`); AWS creds via instance role
  (preferred on EC2) or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`

Renderer build-time:
- `VITE_CONTROL_PLANE_URL` — defaults to `/api` so Caddy's reverse proxy
  picks it up; override to `http://localhost:4000` for direct local dev.

### Path A — local dev with a local vLLM

Fastest if you have a GPU on hand or remote vLLM access. Skips AWS entirely.

```bash
# 1. Clone + JS deps
git clone https://github.com/Dynamo-Technologies/almighty && cd almighty
(cd services/control-plane && pnpm install)
(cd web/renderer && pnpm install)

# 2. Postgres — one-shot in Docker
docker run -d --name almighty-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=almighty postgres:16

# 3. Schema + seed
export DATABASE_URL=postgres://postgres:demo@localhost:5432/almighty
(cd services/control-plane && pnpm run migrate)
docker run --rm -e PGURL="$DATABASE_URL" --network host \
  -v "$PWD:/repo" postgres:16 \
  sh -c 'psql "$PGURL" -f /repo/infra/supabase/seed.sql'

# 4. Run a vLLM endpoint somewhere reachable, then:
export BLUE_LLM_PROVIDER=vllm
export BLUE_LLM_BASE_URL=http://localhost:8001/v1
export RED_LLM_PROVIDER=vllm
export RED_LLM_BASE_URL=http://localhost:8001/v1   # same vLLM is fine for dev
export JWT_SECRET=$(openssl rand -base64 36)
export SPARK_WORKER_URL=http://localhost:7000

# 5. Worker (Python)
(cd agents/runtime && pip install -e ../tools -e ../blue -e ../red \
   -e ../../kernel -e ../../services/czml-validator -e .
   pip install fastapi 'uvicorn[standard]' httpx boto3
   PYTHONPATH=src uvicorn almighty_agent_runtime.shim:app --port 7000) &

# 6. Control-plane + renderer (in separate terminals)
(cd services/control-plane && pnpm run dev) &
(cd web/renderer && VITE_CONTROL_PLANE_URL=http://localhost:4000 pnpm run dev) &
```

Reference vLLM launch line for Gemma 4:

```bash
docker run --gpus all -p 8001:8000 vllm/vllm-openai:latest \
  --model google/gemma-4-26B-A4B-it \
  --enable-auto-tool-choice --tool-call-parser gemma4 \
  --max-model-len 32768
```

### Path B — local dev with AWS Bedrock

Same as Path A through step 3, then swap step 4 for:

```bash
export BLUE_LLM_PROVIDER=bedrock
export RED_LLM_PROVIDER=bedrock
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=...      # or use `aws sso login`
export AWS_SECRET_ACCESS_KEY=...
export JWT_SECRET=$(openssl rand -base64 36)
export SPARK_WORKER_URL=http://localhost:7000
```

The IAM principal needs `bedrock:InvokeModel` + `bedrock:Converse` on
the model arn (see [`infra/aws/demo/iam-policy-route53-dns01.json`](infra/aws/demo/iam-policy-route53-dns01.json)
for the full policy template). Model access for Claude Sonnet 4.5 must be
enabled in your Bedrock console first.

### Path C — full AWS deploy (control-plane on EC2 + Bedrock)

Step-by-step runbook: [`infra/aws/demo/RUNBOOK.md`](infra/aws/demo/RUNBOOK.md).
TL;DR: one `t3.medium` EC2 in a default VPC, joined to a Tailscale net,
running the [`infra/aws/demo/docker-compose.yml`](infra/aws/demo/docker-compose.yml)
stack (Caddy + control-plane + websocket + worker). Caddy gets a real LE cert
via DNS-01 against Route 53; instance role grants `route53:ChangeResourceRecordSets`
+ `bedrock:InvokeModel`.

### Auth — minting a demo JWT

The control-plane signs/verifies HS256 JWTs with `JWT_SECRET`. Mint one:

```bash
JWT_SECRET="$JWT_SECRET" python3 - <<'PY'
import os, json, base64, hmac, hashlib, time
def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
secret = os.environ['JWT_SECRET'].encode()
header = {"alg":"HS256","typ":"JWT"}
now = int(time.time())
claims = {
    "tenant_id":"00000000-0000-4d00-8000-000000000001",
    "cell_role":"white",
    "sub":"demo@example.com",
    "iat":now, "exp":now+24*3600,
}
hb = b64u(json.dumps(header,separators=(',',':')).encode())
cb = b64u(json.dumps(claims,separators=(',',':')).encode())
sig = hmac.new(secret, f"{hb}.{cb}".encode(), hashlib.sha256).digest()
print(f"{hb}.{cb}.{b64u(sig)}")
PY
```

Open the demo route with the token as a query param — it gets stored in
`localStorage` and stripped from the URL on first load:

```
http://localhost:5173/00000000-0000-4d00-8000-000000000001/scenarios/00000000-0000-4101-8000-000000000001/demo?token=<paste>
```

Then click **Advance turn 1** and watch events stream into the right
sidebar with their `causal_predecessors` chips.

### Tests

Python (kernel + agents):
```bash
(cd agents/tools && pytest)
(cd agents/runtime && pytest --ignore=tests/test_chain.py --ignore=tests/test_empty_crew.py)
(cd agents/blue && pytest)
(cd agents/red && pytest)
(cd kernel && pytest)
```

TypeScript (control-plane + renderer):
```bash
(cd services/control-plane && pnpm run typecheck && pnpm test)
(cd web/renderer && pnpm run typecheck)
```

## Contributors

- [@shanedynamo](https://github.com/shanedynamo) — Director of Innovation, Tier 4 lead
- [@alexcurnowdynamo](https://github.com/alexcurnowdynamo) — Full-Stack Developer, Tier 1 + Tier 2 lead
- [@devindynamo](https://github.com/devindynamo) — ML/AI Engineer, Tier 3 lead

## Repository structure

```
docs/         architecture, schemas, diagrams, glossary
infra/        Terraform, per-tenant AWS isolation
services/     control plane, websocket, CZML validator, CZML adapter
web/          Resium renderer, EXCON consoles, white cell console
agents/       CrewAI runtime, officer tools, blue/red/white crews
kernel/       PyRapide DAG, schema DDL, capability profiles
czml/         packet templates, static demo files
```

## Status

Pre-build. Issues tracked in the project board: [Almighty Build](../../projects).
