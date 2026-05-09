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

# Exemplo mínimo: apenas os parâmetros obrigatórios
module "simple_bucket" {
  source = "../../"

  bucket_name = "meu-bucket"
  environment = "dev"
  owner       = "meu-time"
  cost_center = "CC-0001"
}

# Outputs
output "bucket_name" {
  description = "Nome completo do bucket criado"
  value       = module.simple_bucket.bucket_name
}

output "bucket_arn" {
  description = "ARN do bucket criado"
  value       = module.simple_bucket.bucket_arn
}
