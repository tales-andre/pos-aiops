# Questão 06 - Módulo Terraform no padrão interno

## Framework: C-A-R-E (Context – Action – Result – Example)

---

## Prompt

**Context:** Um novo padrão interno de IaC (Infrastructure as Code) foi publicado pelo head de segurança e compliance da empresa. Os novos módulos Terraform devem seguir o seguinte padrão:
-As tags "Owner", "CostCenter" e "Environment" são obrigatórias em todo recurso
-O nome de todos os recursos devem possuir o prefixo: hvt-
-Todo bucket S3 devem possuir: encryption habilitada (SSE-S3 mínimo), versioning ativo, block public access total, logging configurado.
-Variáveis de entrada devem estar em variables.tf com description e type obrigatórios.

**Action:** Crie um módulo terraform reutilizável para Criação de Buckets S3 na AWS, seguindo os novos padrões definidos pelo head de segurança e compliance informados acima.

**Result:** O módulo deve ser reutilizável por qualquer time da empresa e incluir um exemplo de uso demonstrando como utilizá-lo.

**Example:** Utilize o módulo de VPC abaixo como referência de estilo:

variable "environment" {
  description = "Nome do ambiente (dev, staging, production)"
  type        = string
}

locals {
  common_tags = {
    Owner       = var.owner
    CostCenter  = var.cost_center
    Environment = var.environment
  }
}

resource "aws_vpc" "this" {
  cidr_block = var.cidr_block
  tags = merge(local.common_tags, {
    Name = "hvt-vpc-${var.environment}"
  })
}
---

## Modelo

**Sonnet 4.5** — Acredito que o Claude para escrita de códigos e manifestos tem um desempenho melhor que o Gemini, e o modelo intermediário cumpre o seu papel para uma estrutura simples de terraform, ainda mais fornecendo um exemplo, evitando gastos de token parar gerar um modelo do zero.

---

## Output

https://claude.ai/share/72a58330-50cc-4183-96db-f13c95e01246
(resultados anexos na pasta Q06/Anexo/terraform-aws-s3-bucket)

---

## Justificativa

- **Context:** Informo o contexto atual, os novos padrões e o responsável por publicá-los. Removo o nome do responsável (desencessário para o prompt) e trago o seu papel na empresa que é de head de segurança e compliance. Incluo também o nome completo da sigla IaC para evitar suposições do modelo.
- **Action:** Informo o que deve ser feito
- **Result:** Trago detalhes do que deve conter no output, além do terraform um exemplo de como utilizá-lo
- **Example:** Informo o módulo VPC existente como base para criação do novo módulo evitando desvios e trazendo módulos fora do padrão da empresa.

---
