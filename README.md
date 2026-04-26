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
