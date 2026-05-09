# Questão 02 - Script de backup do Ledger

## Framework: R-T-F (Role – Task – Format)

---

## Prompt

**Role:** Você é um SRE especialista em scripts de automações de backup para Data Warehouse em PostgreSQL que roda em instancias EC2 na AWS.

**Task:** Construa um script bash que deve realizar backup diário para um data warehouse chamado Ledger, que está em um PostgreSQL, o script deve executar as seguintes ações:
- Utilizar cron para execução diária;
- Dump com pg_dump;
- Compactar com gzip;
- Subir o arquivo para o bucket S3 utilizando o comando aws s3 cp;
- Nome do Bucket S3: hvt-ledger-backups;
- Manter 30 dias de retenção no S3, removendo arquivos com mais de 30 dias
- Registrar cada execução em /var/log/ledger-backup.log com timestamp;
- Sair com exit code adequado em caso de falha.

O script deve rodar no seguinte ambiente:
- Host: ledger-db.internal.hvt.io
- Porta: 5432
- Banco: ledger_prod
- Usuário de backup: backup_user
- Senha: variável de ambiente PGPASSWORD, populada pelo AWS Secrets Manager via IAM role da instância
- Região AWS: us-east-1
- SO da instância: Ubuntu 22.04 LTS
- Diretório de trabalho com 80 GB livres: /var/backups/ledger
- Tamanho médio atual do dump compactado: ~12 GB

**Format:** Gere o Script Bash completo com comentários explicando cada decisão.

---

## Modelo

**Gemini Pro** — O modelo Pro do Gemini foi escolhido pois tende a ser um bom modelo para programação e criação de Scripts. Também escolhi o modelo para economizar tokens do Claude e para testar as diferentes respostas entre modelos e avaliar o desempenho..

---

## Output

https://gemini.google.com/share/d466ea38fbff

---

## Justificativa

- **Role:** a primeira linha do prompt define a persona como SRE especialista em scripts de automação, voltado para o ambiente específico da questão que é um Data Warehouse em Postgres em uma instancia EC2 na AWS.
- **Task:** Solicito a criação do script bash com todos os detalhes já informados na questão, mas realizando alguns ajustes que acredito que poderia fazer a IA alucinar, como o nome do bucket, a remoção dos arquivos e deixando claro que é um PosgreSQL rodando dentro de uma EC2, para que o modelo não tente criar scripts voltados para o RDS ou algo do tipo.
- **Format:** Solicito apenas o script completo com os comentários, porém o modelo também trouxe a forma de configurar meu script para execução diária no crontab, que acho válido.
