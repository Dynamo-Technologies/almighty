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
