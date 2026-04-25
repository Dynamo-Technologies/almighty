output "vpc_subnet_id" {
  description = "ID of the primary tenant subnet (AZ a). The secondary AZ subnet is exposed via vpc_subnet_id_b for callers that need both."
  value       = var.dry_run ? null : aws_subnet.tenant_a[0].id
}

output "vpc_subnet_id_b" {
  description = "ID of the secondary tenant subnet (AZ b). Required for the RDS DB subnet group; surfaced for callers that need both AZs."
  value       = var.dry_run ? null : aws_subnet.tenant_b[0].id
}

output "rds_endpoint" {
  description = "Connection endpoint for the per-tenant Postgres instance (host:port)."
  value       = var.dry_run ? null : aws_db_instance.tenant[0].endpoint
}

output "rds_database_name" {
  description = "Logical database name on the per-tenant Postgres instance."
  value       = var.rds_database_name
}

output "rds_master_username" {
  description = "Master username for the per-tenant Postgres instance. Password lives in random_password.rds_master and (TODO) Secrets Manager."
  value       = var.rds_master_username
}

output "s3_bucket_arn" {
  description = "ARN of the per-tenant S3 bucket. KMS-encrypted, public access blocked, versioning on."
  value       = var.dry_run ? null : aws_s3_bucket.tenant[0].arn
}

output "s3_bucket_name" {
  description = "Name of the per-tenant S3 bucket. Pattern: almighty-<tenant_id>-<env>."
  value       = var.dry_run ? null : aws_s3_bucket.tenant[0].bucket
}

output "kms_key_id" {
  description = "ID of the per-tenant CMK. Used to encrypt the S3 bucket and the RDS instance at rest."
  value       = var.dry_run ? null : aws_kms_key.tenant[0].key_id
}

output "kms_key_arn" {
  description = "ARN of the per-tenant CMK."
  value       = var.dry_run ? null : aws_kms_key.tenant[0].arn
}

output "task_role_arn" {
  description = "ARN of the per-tenant IAM role assumed by tenant ECS tasks (and consumed by the agent runtime per WS-401)."
  value       = var.dry_run ? null : aws_iam_role.tenant_task[0].arn
}

output "ecs_task_family" {
  description = "ECS task family for the tenant. Null when runtime_mode != 'ecs' (EKS path is TODO)."
  value       = var.dry_run ? null : aws_ecs_task_definition.tenant[0].family
}
