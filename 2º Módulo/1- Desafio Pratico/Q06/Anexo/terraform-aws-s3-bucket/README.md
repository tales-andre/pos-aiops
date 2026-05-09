# Módulo Terraform AWS S3 Bucket

Módulo reutilizável para criação de buckets S3 na AWS em conformidade com os padrões de segurança e compliance da empresa.

## 🔒 Padrões de Segurança Implementados

Este módulo implementa automaticamente todos os requisitos de segurança obrigatórios:

- ✅ **Tags obrigatórias**: Owner, CostCenter e Environment em todos os recursos
- ✅ **Nomenclatura padronizada**: Todos os recursos com prefixo `hvt-`
- ✅ **Criptografia**: SSE-S3 (mínimo) ou SSE-KMS configurada por padrão
- ✅ **Versionamento**: Habilitado automaticamente
- ✅ **Block Public Access**: Bloqueio total de acesso público
- ✅ **Logging**: Configurado automaticamente em bucket dedicado

## 📋 Recursos Criados

- Bucket S3 principal com todas as configurações de segurança
- Bucket S3 dedicado para armazenamento de logs de acesso
- Configurações de versionamento em ambos os buckets
- Configurações de criptografia (SSE-S3 ou SSE-KMS)
- Block Public Access em ambos os buckets
- Logging de acesso configurado
- (Opcional) Lifecycle policies para gestão de dados

## 🚀 Uso Básico

```hcl
module "data_lake_bucket" {
  source = "git::https://github.com/sua-org/terraform-aws-s3-bucket.git?ref=v1.0.0"

  bucket_name = "data-lake"
  environment = "production"
  owner       = "data-engineering"
  cost_center = "CC-1234"
}
```

## 📖 Exemplos

### Exemplo 1: Bucket Simples (SSE-S3)

```hcl
module "app_assets" {
  source = "../../"

  bucket_name = "app-assets"
  environment = "production"
  owner       = "platform-team"
  cost_center = "CC-5678"

  additional_tags = {
    Project = "EcommercePlatform"
    Tier    = "Critical"
  }
}
```

### Exemplo 2: Bucket com KMS e Lifecycle

```hcl
module "backup_bucket" {
  source = "../../"

  bucket_name = "database-backups"
  environment = "production"
  owner       = "database-team"
  cost_center = "CC-9012"
  
  # Criptografia com KMS
  kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
  
  # Lifecycle para otimizar custos
  enable_lifecycle_rules = true
  lifecycle_rules = [
    {
      id                                 = "transition-to-glacier"
      enabled                            = true
      expiration_days                    = null
      noncurrent_version_expiration_days = 90
      transitions = [
        {
          days          = 30
          storage_class = "STANDARD_IA"
        },
        {
          days          = 90
          storage_class = "GLACIER"
        }
      ]
    }
  ]
  
  # Retenção de logs
  logs_retention_days = 180
}
```

### Exemplo 3: Bucket de Desenvolvimento

```hcl
module "dev_artifacts" {
  source = "../../"

  bucket_name = "build-artifacts"
  environment = "dev"
  owner       = "devops-team"
  cost_center = "CC-3456"
  
  # Logs expiram em 30 dias no ambiente de dev
  logs_retention_days = 30
  
  # Lifecycle para limpar artifacts antigos
  enable_lifecycle_rules = true
  lifecycle_rules = [
    {
      id                                 = "cleanup-old-artifacts"
      enabled                            = true
      expiration_days                    = 30
      noncurrent_version_expiration_days = 7
      transitions                        = []
    }
  ]
}
```

## 📥 Inputs

| Nome | Descrição | Tipo | Padrão | Obrigatório |
|------|-----------|------|--------|:-----------:|
| bucket_name | Nome base do bucket (será prefixado com 'hvt-' e sufixado com environment) | `string` | - | sim |
| environment | Nome do ambiente (dev, staging, production) | `string` | - | sim |
| owner | Time ou pessoa responsável (tag obrigatória) | `string` | - | sim |
| cost_center | Centro de custo (tag obrigatória) | `string` | - | sim |
| kms_key_id | ID da chave KMS para SSE-KMS (opcional) | `string` | `null` | não |
| additional_tags | Tags adicionais além das obrigatórias | `map(string)` | `{}` | não |
| logs_retention_days | Dias para reter logs (0 = sem expiração) | `number` | `90` | não |
| enable_lifecycle_rules | Habilitar regras de lifecycle | `bool` | `false` | não |
| lifecycle_rules | Lista de regras de lifecycle | `list(object)` | `[]` | não |

## 📤 Outputs

| Nome | Descrição |
|------|-----------|
| bucket_id | ID do bucket S3 criado |
| bucket_arn | ARN do bucket S3 criado |
| bucket_name | Nome completo do bucket (com prefixo hvt-) |
| bucket_domain_name | Domain name do bucket S3 |
| bucket_regional_domain_name | Regional domain name do bucket S3 |
| logging_bucket_id | ID do bucket de logs |
| logging_bucket_arn | ARN do bucket de logs |
| logging_bucket_name | Nome do bucket de logs |

## 🔧 Requisitos

- Terraform >= 1.5.0
- AWS Provider >= 5.0.0

## 📝 Nomenclatura dos Recursos

- **Bucket principal**: `hvt-{bucket_name}-{environment}`
- **Bucket de logs**: `hvt-{bucket_name}-logs-{environment}`

**Exemplo**: Para `bucket_name = "data-lake"` e `environment = "production"`:
- Bucket principal: `hvt-data-lake-production`
- Bucket de logs: `hvt-data-lake-logs-production`

## ⚠️ Observações Importantes

1. **Destruição de buckets**: Buckets com objetos não podem ser destruídos pelo Terraform. É necessário esvaziar manualmente ou usar `force_destroy = true` (não recomendado para produção).

2. **Custos de logging**: O bucket de logs armazenará todos os access logs. Configure `logs_retention_days` adequadamente para controlar custos.

3. **KMS**: Ao usar SSE-KMS, certifique-se de que a chave KMS tenha as permissões adequadas para o S3.

4. **Block Public Access**: Este módulo sempre bloqueia acesso público. Se precisar de bucket público, este módulo não é adequado.

## 🤝 Contribuindo

Para contribuir com melhorias neste módulo, entre em contato com o time de Platform Engineering.

## 📄 Licença

Uso interno - Junto Seguros
