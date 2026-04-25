variable "tenant_id" {
  description = "Stable identifier for the tenant. Used in resource names; must be lowercase, 3-32 chars, alphanumeric or hyphen."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{2,31}$", var.tenant_id))
    error_message = "tenant_id must be 3-32 chars, lowercase alphanumeric or hyphen, starting with alphanumeric."
  }
}

variable "env" {
  description = "Deployment environment. One of: dev, staging, prod."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of dev, staging, prod."
  }
}

variable "parent_vpc_id" {
  description = "ID of the platform-shared VPC into which the tenant's subnets are allocated."
  type        = string
}

variable "cidr_block" {
  description = "CIDR block carved out of parent VPC for this tenant. Internally split into two /28 subnets across two AZs to satisfy RDS DB subnet group requirements. Use a /27 minimum."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.cidr_block))
    error_message = "cidr_block must be a valid CIDR notation."
  }
}

variable "availability_zones" {
  description = "Two AZ names to spread the tenant subnets across. Must be in the same region as the parent VPC."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "Exactly two availability_zones are required for RDS HA."
  }
}

variable "runtime_mode" {
  description = "Compute runtime for tenant workloads. Currently supports 'ecs'. EKS support is a TODO — see README."
  type        = string
  default     = "ecs"

  validation {
    condition     = contains(["ecs"], var.runtime_mode)
    error_message = "runtime_mode currently only supports 'ecs'. EKS is not yet implemented."
  }
}

variable "ecs_cluster_arn" {
  description = "ARN of the platform-shared ECS cluster (the tenant gets a task family and role inside it). Required when runtime_mode = 'ecs'."
  type        = string
  default     = ""
}

variable "rds_instance_class" {
  description = "RDS instance class for the tenant's Postgres database."
  type        = string
  default     = "db.t4g.medium"
}

variable "rds_postgres_version" {
  description = "RDS Postgres engine version."
  type        = string
  default     = "16.3"
}

variable "rds_allocated_storage_gb" {
  description = "Initial allocated storage for the tenant's RDS instance in GB."
  type        = number
  default     = 20
}

variable "rds_master_username" {
  description = "Master username for the tenant's Postgres instance. The password is generated and stored in Secrets Manager (TODO — see README)."
  type        = string
  default     = "almighty_admin"
}

variable "rds_database_name" {
  description = "Name of the per-tenant logical database created on the RDS instance. Each tenant gets a separate database (NOT a separate schema)."
  type        = string
  default     = "almighty"
}

variable "tags" {
  description = "Additional tags merged into every taggable resource."
  type        = map(string)
  default     = {}
}

variable "dry_run" {
  description = "When true, all resources are declared with count = 0 so the module is validate-only and apply is a no-op. Default true; flip to false in the calling root module to actually provision."
  type        = bool
  default     = true
}
