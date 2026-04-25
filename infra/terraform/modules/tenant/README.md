# Almighty — Per-tenant Terraform module

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

Skeleton Terraform module for per-tenant AWS isolation. Provisions the
canonical per-tenant resource set: VPC subnets, Postgres RDS, KMS-encrypted
S3 bucket, IAM task role, and an ECS task family.

This module is the IaC half of the WS-004 contract. Application-side
isolation (control plane RBAC, JWT-scoped queries, WebSocket fan-out) is
covered by WS-301 / WS-304.

## Status — `dry_run` is on by default

Every resource is gated by `var.dry_run` (default `true`) so:

- `terraform validate` — exercises the contract.
- `terraform plan` — produces an empty plan. Useful in CI to confirm the
  module is syntactically clean against new provider versions.
- `terraform apply` — **no-op** until the calling root module passes
  `dry_run = false`.

This was preferred over `count = 0` directly in the module so callers can
exercise variables in CI without flipping a workspace into a partial-apply
state.

## Module contract

| Input | Type | Required | Default | Notes |
|---|---|---|---|---|
| `tenant_id` | `string` | yes | — | Lowercase, 3-32 chars, alphanumeric or hyphen. Validated. |
| `env` | `string` | yes | — | One of `dev`, `staging`, `prod`. Validated. |
| `parent_vpc_id` | `string` | yes | — | Platform-shared VPC. |
| `cidr_block` | `string` | yes | — | Use `/27` minimum — module splits into two `/28` subnets across two AZs. |
| `availability_zones` | `list(string)` | yes | — | Exactly two AZ names. Validated. |
| `runtime_mode` | `string` | no | `"ecs"` | Currently only `ecs`. EKS is a TODO — see below. |
| `ecs_cluster_arn` | `string` | no | `""` | Platform-shared ECS cluster ARN. Required when `runtime_mode = "ecs"` and `dry_run = false`. |
| `rds_instance_class` | `string` | no | `db.t4g.medium` | |
| `rds_postgres_version` | `string` | no | `16.3` | |
| `rds_allocated_storage_gb` | `number` | no | `20` | |
| `rds_master_username` | `string` | no | `almighty_admin` | |
| `rds_database_name` | `string` | no | `almighty` | Per-tenant **database**, not schema. |
| `tags` | `map(string)` | no | `{}` | Merged into every taggable resource. |
| `dry_run` | `bool` | no | `true` | Flip to `false` to actually provision. |

| Output | Description |
|---|---|
| `vpc_subnet_id` | Primary AZ subnet ID. |
| `vpc_subnet_id_b` | Secondary AZ subnet ID — needed for the DB subnet group. |
| `rds_endpoint` | `host:port` of the tenant Postgres instance. |
| `rds_database_name` | Logical database name. |
| `rds_master_username` | Master username. |
| `s3_bucket_arn` / `s3_bucket_name` | Per-tenant S3 bucket. |
| `kms_key_id` / `kms_key_arn` | Per-tenant CMK. |
| `task_role_arn` | IAM role assumed by tenant ECS tasks. Consumed by WS-401 agent runtime. |
| `ecs_task_family` | ECS task family. Null when `runtime_mode != "ecs"`. |

## Tenant lifecycle

The lifecycle of a tenant in Almighty maps onto the lifecycle of one
invocation of this module from a calling root module.

### 1. Provision

```hcl
# infra/terraform/envs/dev/tenants.tf  (caller — example)
module "tenant_acme" {
  source = "../../modules/tenant"

  tenant_id          = "acme"
  env                = "dev"
  parent_vpc_id      = aws_vpc.platform.id
  cidr_block         = "10.42.0.0/27"
  availability_zones = ["us-east-1a", "us-east-1b"]

  # Default dry_run = true means this validates only. Flip to false when
  # you actually want resources to land.
  dry_run = false
}

output "acme_rds_endpoint" {
  value = module.tenant_acme.rds_endpoint
}

output "acme_task_role" {
  value = module.tenant_acme.task_role_arn
}
```

Run order:

```bash
terraform -chdir=infra/terraform/envs/dev init
terraform -chdir=infra/terraform/envs/dev plan -out=acme.tfplan
terraform -chdir=infra/terraform/envs/dev apply acme.tfplan
```

The control plane (WS-301) reads the outputs to register the tenant in its
own registry and to wire the agent runtime (WS-401) into the tenant's
`task_role_arn`.

### 2. Run

The module produces immutable infrastructure for a tenant. Per-scenario
state lives in:

- The tenant's RDS database — events table per WS-101 schema, snapshots per
  WS-302 turn controller.
- The tenant's S3 bucket — AAR exports per WS-506.
- The tenant's CMK — encrypts both.

There is nothing scenario-specific in this module. The control plane
manages scenario lifecycle inside an already-provisioned tenant.

### 3. Teardown

```bash
terraform -chdir=infra/terraform/envs/dev destroy -target=module.tenant_acme
```

Caveats:

- **RDS deletion protection** is enabled when `env = "prod"`. The destroy
  will fail until you flip `deletion_protection = false` and re-apply.
  This is intentional.
- **S3 bucket** has versioning enabled. Destroy fails if the bucket is
  non-empty. Use `aws s3 rm s3://<bucket> --recursive` and remove all
  versions before retrying, or accept data loss and use a `force_destroy`
  override (not currently exposed — open a follow-up issue if needed).
- **KMS key** enters a 30-day deletion window; the alias can be reused
  after the window closes. If you need to redeploy the same `tenant_id`
  within 30 days, change the alias suffix in the calling root module or
  cancel the key deletion in the AWS console.

## Open TODOs

- **EKS path.** `runtime_mode = "eks"` is rejected at variable validation
  today. When the platform decides EKS is needed (likely Phase 4+ when
  agent crews need k8s ergonomics for sidecars), wire:
  - kubernetes provider against the platform cluster
  - `kubernetes_namespace` resource named `${local.name_prefix}`
  - `kubernetes_service_account` annotated with IRSA pointing at
    `aws_iam_role.tenant_task`
  - default-deny `NetworkPolicy` so cross-namespace traffic is blocked
  See `main.tf` bottom for the inline TODO comment.
- **Secrets Manager for the RDS master password.** Currently stored only
  in the random_password resource (which is in state). Tracked as a
  follow-up to WS-301 — the control plane needs the secret ARN at
  scenario-provisioning time.
- **Outbound egress controls.** The tenant security group is created but
  no egress rules are defined. v1 allows everything; tighten when the
  agent runtime knows which external services it needs.

## Local development

To exercise the contract without an AWS account:

```bash
cd infra/terraform/modules/tenant
terraform init
terraform validate
```

`terraform plan` against this module on its own does not work (the module
has required variables); add a `terraform.tfvars.example` to the calling
root module instead.

## References

- Architecture diagram: [`docs/diagrams/architecture-v1.svg`](../../../../docs/diagrams/architecture-v1.svg) (WS-002)
- Glossary — tenant isolation: [`docs/glossary.md#tenant-isolation`](../../../../docs/glossary.md#tenant-isolation) (WS-003)
- Control plane consumer: WS-301 (#17)
- Agent runtime consumer: WS-401 (#21)
- AAR exporter consumer: WS-506 (#31)
