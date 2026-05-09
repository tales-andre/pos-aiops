#!/bin/bash

# ==============================================================================
# SCRIPT DE BACKUP: Data Warehouse Ledger (PostgreSQL)
# SO: Ubuntu 22.04 LTS | Região AWS: us-east-1
# ==============================================================================

# Aborta o script em caso de erros de comando (-e), variáveis não declaradas (-u)
# e garante que erros em pipes (como pg_dump | gzip) não sejam ignorados (-o pipefail)
set -euo pipefail

# ==============================================================================
# VARIÁVEIS DE AMBIENTE E CONFIGURAÇÃO
# ==============================================================================

# Banco de Dados
DB_HOST="ledger-db.internal.hvt.io"
DB_PORT="5432"
DB_NAME="ledger_prod"
DB_USER="backup_user"

# AWS e Storage
AWS_REGION="us-east-1"
S3_BUCKET="s3://hvt-ledger-backups"
SECRET_NAME="ledger/db/backup_password" # Substitua pelo nome real do secret no AWS Secrets Manager

# Diretórios e Arquivos
WORK_DIR="/var/backups/ledger"
LOG_FILE="/var/log/ledger-backup.log"
DATE_STAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="${WORK_DIR}/ledger_prod_${DATE_STAMP}.sql.gz"

# Retenção
RETENTION_DAYS=30

# ==============================================================================
# FUNÇÕES DE SUPORTE
# ==============================================================================

# Função para registrar logs com timestamp
log_info() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $1" | tee -a "$LOG_FILE" >&2
}

# Tratamento de erro via Trap (Garante exit code adequado)
handle_error() {
    local exit_code=$?
    log_error "Ocorreu um erro na execução do script na linha $1. Código de saída: $exit_code."
    
    # Limpeza de arquivos temporários locais em caso de falha para não lotar os 80GB
    if [[ -f "$BACKUP_FILE" ]]; then
        log_info "Limpando arquivo de backup incompleto: $BACKUP_FILE"
        rm -f "$BACKUP_FILE"
    fi
    
    exit "$exit_code"
}

trap 'handle_error $LINENO' ERR

# ==============================================================================
# EXECUÇÃO DO BACKUP
# ==============================================================================

# Cria o diretório de trabalho caso não exista
mkdir -p "$WORK_DIR"

log_info "Iniciando rotina de backup do DW Ledger ($DB_NAME)."

# 1. Recuperar senha do AWS Secrets Manager via IAM Role da EC2
log_info "Recuperando credenciais de banco de dados do AWS Secrets Manager..."
export PGPASSWORD=$(aws secretsmanager get-secret-value \
    --region "$AWS_REGION" \
    --secret-id "$SECRET_NAME" \
    --query SecretString \
    --output text)

# 2. Gerar dump e compactar com gzip em tempo real
log_info "Iniciando pg_dump e compactação gzip para: $BACKUP_FILE"
# O uso de pipe para o gzip evita a necessidade de gravar o dump em texto claro no disco,
# economizando I/O e espaço na partição de 80 GB.
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" | gzip > "$BACKUP_FILE"
log_info "Dump e compactação concluídos com sucesso."

# 3. Upload para o S3
log_info "Iniciando upload para o bucket S3 ($S3_BUCKET)..."
aws s3 cp "$BACKUP_FILE" "${S3_BUCKET}/" --region "$AWS_REGION" --quiet
log_info "Upload para S3 concluído com sucesso."

# 4. Limpeza local (SRE Best Practice para evitar File System Full)
log_info "Removendo arquivo de backup local para liberar espaço no disco..."
rm -f "$BACKUP_FILE"

# 5. Aplicação da política de retenção no S3
log_info "Verificando e removendo backups no S3 com mais de $RETENTION_DAYS dias..."
# Calcula o timestamp limite para retenção usando GNU date
CUTOFF_TIMESTAMP=$(date -d "$RETENTION_DAYS days ago" +%s)

# Lista os arquivos, filtra os SQLs e deleta os que ultrapassaram a retenção
aws s3 ls "${S3_BUCKET}/" --region "$AWS_REGION" | grep "\.sql\.gz" | while read -r line; do
    # O output do 'aws s3 ls' segue o formato: YYYY-MM-DD HH:MM:SS SIZE FILENAME
    FILE_DATE=$(echo "$line" | awk '{print $1" "$2}')
    FILE_NAME=$(echo "$line" | awk '{print $4}')
    
    FILE_TIMESTAMP=$(date -d "$FILE_DATE" +%s)
    
    if [[ $FILE_TIMESTAMP -lt $CUTOFF_TIMESTAMP ]]; then
        log_info "Removendo arquivo expirado no S3: $FILE_NAME"
        aws s3 rm "${S3_BUCKET}/${FILE_NAME}" --region "$AWS_REGION" --quiet
    fi
done

log_info "Rotina de backup finalizada com sucesso."
exit 0