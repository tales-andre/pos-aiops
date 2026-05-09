# =============================================================================
# Multi-stage build para otimizar tamanho final da imagem
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Instalação de dependências
# -----------------------------------------------------------------------------
FROM python:3.11-slim as builder

# Define diretório de trabalho temporário
WORKDIR /build

# Instala dependências de sistema necessárias para compilação de pacotes Python
# - gcc, g++: compiladores para extensões C (psycopg2, etc)
# - libpq-dev: headers PostgreSQL para psycopg2-binary
# - build-essential: ferramentas essenciais de build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas requirements.txt primeiro (cache layer otimizado)
# Se requirements.txt não mudar, essa layer será reutilizada
COPY requirements.txt .

# Instala dependências Python em diretório específico
# --no-cache-dir: não mantém cache do pip (reduz tamanho da imagem)
# --prefix=/install: instala em diretório separado para copiar depois
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Runtime - Imagem final de produção
# -----------------------------------------------------------------------------
FROM python:3.11-slim

# Metadata da imagem (boas práticas de rotulagem)
LABEL maintainer="Platform Engineering Team" \
      app="flask-api" \
      version="1.0"

# Cria usuário não-root para executar a aplicação (segurança)
# -r: cria usuário de sistema
# -s /bin/false: não permite login shell
# -M: não cria home directory (desnecessário)
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/false -M appuser

# Instala apenas dependências runtime necessárias
# libpq5: biblioteca PostgreSQL para psycopg2-binary em runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Define diretório de trabalho da aplicação
WORKDIR /app

# Copia dependências Python instaladas do stage builder
COPY --from=builder /install /usr/local

# Copia código da aplicação
# Ordem otimizada: dependências primeiro, código depois (melhor cache)
COPY lift/ /app/lift/

# Define ownership dos arquivos para o usuário não-root
RUN chown -R appuser:appuser /app

# Muda para usuário não-root (princípio do menor privilégio)
USER appuser

# Variáveis de ambiente de runtime
# PYTHONUNBUFFERED: força stdout/stderr sem buffer (logs em tempo real)
# PYTHONDONTWRITEBYTECODE: não gera arquivos .pyc (reduz tamanho)
# PORT: porta padrão da aplicação
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Declara variáveis obrigatórias sem valores default
# Força a injeção explícita em runtime (segurança)
# DATABASE_URL: string de conexão com banco de dados
# API_KEY: chave de autenticação da API
ENV DATABASE_URL="" \
    API_KEY=""

# Expõe porta da aplicação (documentação, não abre a porta de fato)
EXPOSE 8080

# Healthcheck para monitoramento de saúde do container
# Valida se a aplicação está respondendo corretamente
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)" || exit 1

# Comando de inicialização da aplicação
# --bind 0.0.0.0:8080: escuta em todas interfaces na porta 8080
# --workers 4: 4 processos worker (ajustar conforme CPU disponível)
# --worker-class sync: workers síncronos (padrão para I/O blocking)
# --timeout 120: timeout de 120s para requisições longas
# --access-logfile -: logs de acesso no stdout
# --error-logfile -: logs de erro no stderr
# --log-level info: nível de log padrão
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "lift.app:app"]