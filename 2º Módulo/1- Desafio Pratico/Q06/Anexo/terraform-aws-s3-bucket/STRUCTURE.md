# Estrutura do Módulo terraform-aws-s3-bucket

```
terraform-aws-s3-bucket/
│
├── main.tf                      # Recursos principais do módulo
├── variables.tf                 # Declaração de variáveis de entrada
├── outputs.tf                   # Declaração de outputs do módulo
├── versions.tf                  # Requisitos de versão do Terraform e providers
├── README.md                    # Documentação completa do módulo
├── .gitignore                   # Arquivos a serem ignorados pelo Git
│
└── examples/                    # Exemplos de uso do módulo
    ├── simple/                  # Exemplo mínimo (quick start)
    │   └── main.tf
    │
    └── complete/                # Exemplo completo com múltiplos cenários
        ├── main.tf
        └── README.md
```

## 📝 Descrição dos Arquivos

### Arquivos Principais do Módulo

- **main.tf**: Contém toda a lógica do módulo, incluindo:
  - Buckets S3 (principal e de logs)
  - Configurações de versionamento
  - Configurações de criptografia (SSE-S3 e SSE-KMS)
  - Block Public Access
  - Logging
  - Lifecycle policies (opcional)
  - Tags obrigatórias (Owner, CostCenter, Environment)

- **variables.tf**: Define todas as variáveis de entrada com:
  - Descrições obrigatórias
  - Types obrigatórios
  - Validações onde aplicável
  - Valores padrão quando apropriado

- **outputs.tf**: Exporta informações úteis dos recursos criados:
  - IDs, ARNs e nomes dos buckets
  - Domain names
  - Informações do bucket de logs

- **versions.tf**: Especifica requisitos de versão:
  - Terraform >= 1.5.0
  - AWS Provider >= 5.0.0

### Exemplos

- **examples/simple/**: Demonstra o uso mínimo do módulo com apenas os parâmetros obrigatórios

- **examples/complete/**: Demonstra 4 cenários reais de uso:
  1. Bucket de assets de aplicação (SSE-S3 básico)
  2. Bucket de dados de clientes (SSE-KMS + compliance)
  3. Bucket de artifacts de dev (com lifecycle de limpeza)
  4. Bucket de backups (KMS + lifecycle com transições)

## 🚀 Como Usar

### Quick Start (Exemplo Simples)

```bash
cd examples/simple
terraform init
terraform plan
terraform apply
```

### Teste Completo

```bash
cd examples/complete
terraform init
terraform plan
terraform apply
```

## 📦 Distribuição

Este módulo pode ser distribuído de várias formas:

1. **Git Repository** (Recomendado):
```hcl
module "my_bucket" {
  source = "git::https://github.com/sua-org/terraform-aws-s3-bucket.git?ref=v1.0.0"
  # ...
}
```

2. **Path Local** (para desenvolvimento):
```hcl
module "my_bucket" {
  source = "../../modules/terraform-aws-s3-bucket"
  # ...
}
```

3. **Terraform Registry Privado** (se disponível):
```hcl
module "my_bucket" {
  source  = "app.terraform.io/sua-org/s3-bucket/aws"
  version = "1.0.0"
  # ...
}
```

## ✅ Compliance

Este módulo garante 100% de conformidade com os padrões definidos:

✅ Prefixo `hvt-` em todos os recursos  
✅ Tags obrigatórias: Owner, CostCenter, Environment  
✅ Criptografia habilitada (SSE-S3 mínimo)  
✅ Versionamento ativo  
✅ Block Public Access total  
✅ Logging configurado  
✅ Variables com description e type obrigatórios
