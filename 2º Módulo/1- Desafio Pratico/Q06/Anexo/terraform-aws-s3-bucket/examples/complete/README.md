# Exemplo Completo de Uso do Módulo S3

Este exemplo demonstra diferentes cenários de uso do módulo terraform-aws-s3-bucket.

## 📦 Cenários Implementados

### 1. Bucket de Assets de Aplicação
- Criptografia SSE-S3 (padrão)
- Tags personalizadas para projeto e criticidade
- Uso básico sem lifecycle

### 2. Bucket de Dados de Clientes
- Criptografia SSE-KMS para maior segurança
- Retenção de logs estendida (180 dias) para compliance
- Tags de classificação de dados e compliance LGPD

### 3. Bucket de Artifacts de Desenvolvimento
- Ambiente de desenvolvimento
- Lifecycle configurado para limpeza automática
- Artifacts expiram em 30 dias
- Retenção de logs reduzida (30 dias)

### 4. Bucket de Backups de Database
- Criptografia SSE-KMS
- Lifecycle com transições para otimizar custos:
  - 30 dias → STANDARD_IA
  - 90 dias → GLACIER
- Retenção de logs de 1 ano
- Versões antigas expiram em 90 dias

## 🚀 Como Usar

1. Configure suas credenciais AWS:
```bash
export AWS_PROFILE=seu-profile
# ou
export AWS_ACCESS_KEY_ID=sua-key
export AWS_SECRET_ACCESS_KEY=sua-secret
```

2. Ajuste os valores no arquivo `main.tf`:
   - Substitua os ARNs das chaves KMS pelos seus
   - Ajuste os valores de `owner` e `cost_center` conforme sua organização
   - Modifique os nomes dos buckets se necessário

3. Inicialize o Terraform:
```bash
terraform init
```

4. Revise o plano:
```bash
terraform plan
```

5. Aplique as mudanças:
```bash
terraform apply
```

## 📋 Recursos Criados

Este exemplo criará **8 buckets S3** no total:
- 4 buckets principais (um para cada cenário)
- 4 buckets de logs correspondentes

Todos com as configurações de segurança obrigatórias aplicadas automaticamente.

## 💰 Estimativa de Custos

**Nota**: Os custos variam por região e uso. Estimativas aproximadas para us-east-1:

| Recurso | Custo Mensal Estimado |
|---------|----------------------|
| 4 buckets principais (100GB cada) | ~$9.20 |
| 4 buckets de logs (10GB cada) | ~$0.92 |
| Requests de API | ~$0.50 |
| **Total estimado** | **~$10.62/mês** |

**Custos adicionais a considerar**:
- KMS: ~$1/chave/mês + $0.03 por 10.000 requests
- Transferência de dados (egress)
- Glacier storage (muito mais barato para backups antigos)

## 🧹 Limpeza

Para destruir todos os recursos criados:

```bash
# ATENÇÃO: Buckets com objetos não podem ser destruídos
# Você precisará esvaziar os buckets manualmente primeiro

terraform destroy
```

## 📝 Outputs Disponíveis

Após aplicar, você terá acesso aos seguintes outputs:

```bash
terraform output app_assets_bucket_name
terraform output customer_data_bucket_name
terraform output dev_artifacts_bucket_name
terraform output database_backups_bucket_name
```

## 🔍 Validação

Para validar que os buckets foram criados corretamente:

```bash
# Listar buckets criados
aws s3 ls | grep hvt-

# Verificar versionamento
aws s3api get-bucket-versioning --bucket hvt-app-assets-production

# Verificar criptografia
aws s3api get-bucket-encryption --bucket hvt-app-assets-production

# Verificar block public access
aws s3api get-public-access-block --bucket hvt-app-assets-production

# Verificar logging
aws s3api get-bucket-logging --bucket hvt-app-assets-production
```

## ⚡ Próximos Passos

Depois de aplicar este exemplo, você pode:

1. **Testar upload de objetos**:
```bash
echo "teste" > teste.txt
aws s3 cp teste.txt s3://hvt-app-assets-production/
```

2. **Verificar logs de acesso** (aguarde alguns minutos):
```bash
aws s3 ls s3://hvt-app-assets-logs-production/s3-access-logs/
```

3. **Testar lifecycle** (no bucket de dev):
```bash
# Upload de arquivo de teste
aws s3 cp teste.txt s3://hvt-build-artifacts-dev/
# Aguarde 30 dias ou ajuste a lifecycle para testar
```

## 🤝 Contribuindo

Encontrou algum problema ou tem sugestões? Entre em contato com o time de Platform Engineering.
