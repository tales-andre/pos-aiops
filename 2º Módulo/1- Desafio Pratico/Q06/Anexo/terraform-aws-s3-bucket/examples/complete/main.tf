terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# Exemplo 1: Bucket básico para aplicação (SSE-S3)
module "app_assets" {
  source = "../../"

  bucket_name = "app-assets"
  environment = "production"
  owner       = "platform-team"
  cost_center = "CC-5678"

  additional_tags = {
    Project     = "EcommercePlatform"
    Tier        = "Critical"
    Description = "Assets estáticos da aplicação web"
  }
}

# Exemplo 2: Bucket com criptografia KMS para dados sensíveis
module "customer_data" {
  source = "../../"

  bucket_name = "customer-data"
  environment = "production"
  owner       = "data-team"
  cost_center = "CC-1234"

  # Usar KMS para maior controle de criptografia
  kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"

  logs_retention_days = 180 # 6 meses de logs para compliance

  additional_tags = {
    DataClassification = "Confidential"
    Compliance         = "LGPD"
  }
}

# Exemplo 3: Bucket de desenvolvimento com lifecycle para limpeza automática
module "dev_artifacts" {
  source = "../../"

  bucket_name = "build-artifacts"
  environment = "dev"
  owner       = "devops-team"
  cost_center = "CC-3456"

  logs_retention_days = 30 # Menos retenção em dev

  enable_lifecycle_rules = true
  lifecycle_rules = [
    {
      id                                 = "cleanup-old-artifacts"
      enabled                            = true
      expiration_days                    = 30 # Artifacts expiram em 30 dias
      noncurrent_version_expiration_days = 7  # Versões antigas expiram em 7 dias
      transitions                        = []
    }
  ]

  additional_tags = {
    AutoCleanup = "true"
  }
}

# Exemplo 4: Bucket de backups com transição para classes de storage mais baratas
module "database_backups" {
  source = "../../"

  bucket_name = "database-backups"
  environment = "production"
  owner       = "database-team"
  cost_center = "CC-9012"

  kms_key_id          = "arn:aws:kms:us-east-1:123456789012:key/87654321-4321-4321-4321-210987654321"
  logs_retention_days = 365 # 1 ano de logs para backups

  enable_lifecycle_rules = true
  lifecycle_rules = [
    {
      id                                 = "transition-to-glacier"
      enabled                            = true
      expiration_days                    = null # Não expira
      noncurrent_version_expiration_days = 90   # Versões antigas expiram em 90 dias
      transitions = [
        {
          days          = 30 # Após 30 dias vai para IA
          storage_class = "STANDARD_IA"
        },
        {
          days          = 90 # Após 90 dias vai para Glacier
          storage_class = "GLACIER"
        }
      ]
    }
  ]

  additional_tags = {
    BackupType = "Database"
    Retention  = "LongTerm"
  }
}

# Outputs para referência
output "app_assets_bucket_name" {
  description = "Nome do bucket de assets da aplicação"
  value       = module.app_assets.bucket_name
}

output "app_assets_bucket_arn" {
  description = "ARN do bucket de assets da aplicação"
  value       = module.app_assets.bucket_arn
}

output "customer_data_bucket_name" {
  description = "Nome do bucket de dados de clientes"
  value       = module.customer_data.bucket_name
}

output "dev_artifacts_bucket_name" {
  description = "Nome do bucket de artifacts de desenvolvimento"
  value       = module.dev_artifacts.bucket_name
}

output "database_backups_bucket_name" {
  description = "Nome do bucket de backups de database"
  value       = module.database_backups.bucket_name
}
