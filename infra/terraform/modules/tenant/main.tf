###############################################################################
# Almighty per-tenant module — variable contract + resource skeleton
#
# All resources are gated by var.dry_run (default true) so that
# `terraform validate` and `terraform plan` exercise the contract while
# `terraform apply` is a no-op until the caller flips dry_run = false.
#
# When dry_run = false this module provisions the canonical per-tenant
# isolated set: VPC subnets, RDS Postgres, S3 + KMS, IAM role, and an ECS
# task family. EKS is not implemented yet (see README TODO).
###############################################################################

locals {
  enabled = var.dry_run ? 0 : 1

  name_prefix = "almighty-${var.tenant_id}-${var.env}"

  base_tags = merge(
    var.tags,
    {
      "almighty.tenant_id" = var.tenant_id
      "almighty.env"       = var.env
      "almighty.module"    = "tenant"
    }
  )

  # Carve var.cidr_block into two /28 subnets across two AZs. cidrsubnet
  # takes (parent, newbits, netnum). With a /27 parent we use newbits=1 to
  # split into two /28 ranges. Callers can pass a larger block; the first
  # two halves are always taken.
  subnet_newbits = 1
  subnet_cidr_a  = cidrsubnet(var.cidr_block, local.subnet_newbits, 0)
  subnet_cidr_b  = cidrsubnet(var.cidr_block, local.subnet_newbits, 1)
}

###############################################################################
# Networking — two /28 subnets in distinct AZs
###############################################################################

resource "aws_subnet" "tenant_a" {
  count             = local.enabled
  vpc_id            = var.parent_vpc_id
  cidr_block        = local.subnet_cidr_a
  availability_zone = var.availability_zones[0]

  tags = merge(local.base_tags, {
    Name = "${local.name_prefix}-subnet-a"
  })
}

resource "aws_subnet" "tenant_b" {
  count             = local.enabled
  vpc_id            = var.parent_vpc_id
  cidr_block        = local.subnet_cidr_b
  availability_zone = var.availability_zones[1]

  tags = merge(local.base_tags, {
    Name = "${local.name_prefix}-subnet-b"
  })
}

###############################################################################
# RDS Postgres — single instance, separate per-tenant database
###############################################################################

resource "aws_db_subnet_group" "tenant" {
  count = local.enabled
  name  = "${local.name_prefix}-db-subnets"
  subnet_ids = [
    aws_subnet.tenant_a[0].id,
    aws_subnet.tenant_b[0].id,
  ]

  tags = local.base_tags
}

resource "aws_security_group" "tenant_rds" {
  count       = local.enabled
  name        = "${local.name_prefix}-rds"
  description = "Per-tenant RDS access — locked down to tenant task role at apply time"
  vpc_id      = var.parent_vpc_id

  tags = local.base_tags
}

resource "random_password" "rds_master" {
  count   = local.enabled
  length  = 32
  special = true

  # TODO: store this in AWS Secrets Manager once the tenant lifecycle wires
  # the secret reference into the ECS task role. Tracked under WS-301
  # follow-up because the control plane needs the secret ARN at scenario
  # provisioning time.
}

resource "aws_db_instance" "tenant" {
  count                   = local.enabled
  identifier              = "${local.name_prefix}-pg"
  engine                  = "postgres"
  engine_version          = var.rds_postgres_version
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage_gb
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.tenant[0].arn
  db_subnet_group_name    = aws_db_subnet_group.tenant[0].name
  vpc_security_group_ids  = [aws_security_group.tenant_rds[0].id]
  username                = var.rds_master_username
  password                = random_password.rds_master[0].result
  db_name                 = var.rds_database_name
  publicly_accessible     = false
  skip_final_snapshot     = var.env != "prod"
  deletion_protection     = var.env == "prod"
  backup_retention_period = var.env == "prod" ? 7 : 1
  multi_az                = var.env == "prod"

  tags = local.base_tags
}

###############################################################################
# S3 + KMS — per-tenant bucket and CMK
###############################################################################

resource "aws_kms_key" "tenant" {
  count                   = local.enabled
  description             = "Per-tenant CMK for ${var.tenant_id} (${var.env}) — encrypts S3 and RDS at rest"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = local.base_tags
}

resource "aws_kms_alias" "tenant" {
  count         = local.enabled
  name          = "alias/${local.name_prefix}"
  target_key_id = aws_kms_key.tenant[0].key_id
}

resource "aws_s3_bucket" "tenant" {
  count  = local.enabled
  bucket = local.name_prefix

  tags = local.base_tags
}

resource "aws_s3_bucket_public_access_block" "tenant" {
  count                   = local.enabled
  bucket                  = aws_s3_bucket.tenant[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "tenant" {
  count  = local.enabled
  bucket = aws_s3_bucket.tenant[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tenant" {
  count  = local.enabled
  bucket = aws_s3_bucket.tenant[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.tenant[0].arn
    }
  }
}

###############################################################################
# IAM — per-tenant task role with scoped-down policies
###############################################################################

data "aws_iam_policy_document" "task_assume" {
  count = local.enabled

  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "tenant_task" {
  count              = local.enabled
  name               = "${local.name_prefix}-task-role"
  assume_role_policy = data.aws_iam_policy_document.task_assume[0].json

  tags = local.base_tags
}

data "aws_iam_policy_document" "tenant_task_policy" {
  count = local.enabled

  statement {
    sid     = "TenantBucketReadWrite"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.tenant[0].arn,
      "${aws_s3_bucket.tenant[0].arn}/*",
    ]
  }

  statement {
    sid       = "TenantKmsUse"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [aws_kms_key.tenant[0].arn]
  }

  statement {
    sid       = "TenantRdsConnect"
    actions   = ["rds-db:connect"]
    resources = ["arn:aws:rds-db:*:*:dbuser:${aws_db_instance.tenant[0].resource_id}/${var.rds_master_username}"]
  }
}

resource "aws_iam_role_policy" "tenant_task" {
  count  = local.enabled
  name   = "${local.name_prefix}-task-policy"
  role   = aws_iam_role.tenant_task[0].id
  policy = data.aws_iam_policy_document.tenant_task_policy[0].json
}

###############################################################################
# Compute — ECS task family (EKS path TODO)
###############################################################################

resource "aws_ecs_task_definition" "tenant" {
  count                    = local.enabled
  family                   = "${local.name_prefix}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  task_role_arn            = aws_iam_role.tenant_task[0].arn
  execution_role_arn       = aws_iam_role.tenant_task[0].arn

  container_definitions = jsonencode([
    {
      # Placeholder container. Real image is wired by the calling root
      # module per environment because the registry path differs across
      # dev/staging/prod accounts.
      name      = "almighty-tenant"
      image     = "public.ecr.aws/docker/library/busybox:stable"
      essential = true
      command   = ["sh", "-c", "echo 'tenant ${var.tenant_id} placeholder' && sleep 3600"]
    }
  ])

  tags = local.base_tags
}

# TODO (WS-004 follow-up): EKS namespace path. When `runtime_mode = "eks"`,
# we need to:
#   - take a kubernetes provider configured against the platform cluster
#   - declare a `kubernetes_namespace` resource named after local.name_prefix
#   - declare a `kubernetes_service_account` annotated with IRSA pointing at
#     aws_iam_role.tenant_task
#   - mirror the network policy boundary (NetworkPolicy resource) so cross-
#     namespace traffic is denied by default
# Variable validation already rejects runtime_mode != "ecs" so callers fail
# fast.
