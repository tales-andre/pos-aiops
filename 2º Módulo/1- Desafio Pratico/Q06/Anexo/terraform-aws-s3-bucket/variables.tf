variable "bucket_name" {
  description = "Nome base do bucket S3 (será prefixado com 'hvt-' e sufixado com o environment)"
  type        = string
}

variable "environment" {
  description = "Nome do ambiente (dev, staging, production)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment deve ser dev, staging ou production."
  }
}

variable "owner" {
  description = "Nome do time ou pessoa responsável pelo recurso (tag obrigatória)"
  type        = string
}

variable "cost_center" {
  description = "Centro de custo responsável pelo recurso (tag obrigatória)"
  type        = string
}

variable "kms_key_id" {
  description = "ID da chave KMS para criptografia SSE-KMS (opcional, se não informado usa SSE-S3)"
  type        = string
  default     = null
}

variable "additional_tags" {
  description = "Tags adicionais para aplicar aos recursos além das obrigatórias"
  type        = map(string)
  default     = {}
}

variable "logs_retention_days" {
  description = "Número de dias para reter logs de acesso ao S3 (0 = sem expiração)"
  type        = number
  default     = 90

  validation {
    condition     = var.logs_retention_days >= 0
    error_message = "logs_retention_days deve ser maior ou igual a 0."
  }
}

variable "enable_lifecycle_rules" {
  description = "Habilitar regras de lifecycle no bucket principal"
  type        = bool
  default     = false
}

variable "lifecycle_rules" {
  description = "Lista de regras de lifecycle para o bucket principal"
  type = list(object({
    id                                   = string
    enabled                              = bool
    expiration_days                      = optional(number)
    noncurrent_version_expiration_days   = optional(number)
    transitions = optional(list(object({
      days          = number
      storage_class = string
    })), [])
  }))
  default = []
}
