# Questão 04 - Relatório mensal de transações do Ledger

## Framework: T-A-G (Task – Action - Goal)

---

## Prompt

**Task:** Gerar uma query SQL para um PostgreSQL que extraia informações sobre o crescimento de transações nos ultimos 6 meses. Essas informações serão utilizadas em um relatório mensal de transações de um Data Warehouse em PostgreSQL, divididos por categorias. Os numeros precisam estar consolidados e a query pode utilizar as 2 tabelas abaixo como referência:

TABELA 1:
CREATE TABLE transactions (
  id              BIGSERIAL PRIMARY KEY,
  customer_id     BIGINT NOT NULL REFERENCES customers(id),
  category        VARCHAR(32) NOT NULL,
  amount_cents    BIGINT NOT NULL,
  status          VARCHAR(16) NOT NULL,
  payment_method  VARCHAR(16),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_transactions_created_at ON transactions(created_at);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_category ON transactions(category);

TABELA 2:
CREATE TABLE customers (
  id          BIGSERIAL PRIMARY KEY,
  segment     VARCHAR(16) NOT NULL,
  country     CHAR(2) NOT NULL,
  signup_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

As categorias em produção hoje são: subscription, one_time, refund e credit_adjustment

**Action:** A query deve: 
- Filtrar somente resultados com: status = 'completed'
- Converter o campo amount_cents que está no formato 'centavos de real' para o formato 'Real' com 2 casas Decimais
- Filtrar resultados dos ultimos 6 meses corridos a partir da data de 24/Abril/2026 (2026-04-24)
- Agrupar os resultados por mes no formato YYYY-MM e também por categoria (subscription, one_time, refund e credit_adjustment)
- Trazer 2 métricas por linha: quantidade de transações e volume total em reais
- Ordenar primeiro por: Mês Crescente
- Ordenar depois por: Categoria Crescente

**Goal:** A query será executada por um usuário que não sabe escrever SQL e precisa dos resultados para gerar uma apresentação de crescimento de transações por categoria dos ultimos 6 meses. A query deve ser executada sem necessidade de ajustes ou alterações manuais. 

---

## Modelo

**Gemini 3 Raciocínio** — O prompt está bem estruturado com todos os detalhes para gerar um script SQL relativamente simples, não existem pontas soltas que façam o modelo alucinar ou buscar soluções irreais. Acredito que um modelo intermediário possa fazer um bom trabalho.

---

## Output

https://gemini.google.com/share/0c562376d55d

---

## Justificativa

- **Task:** Defino o que tenho em mãos (Tabelas de Referencia) e o que precisa ser feito com esses dados, em qual o ambiente será executado e o contexto da situação.
- **Action:** Detalho os filtros e formato que o resultado deve ser apresentado na tela.
- **Goal:** Informo que o usuário não sabe escrever SQL e que o script deve ser executado sem necessidade de alterações manuais, pronto para exportar os resultados para o relatório mensal.

---
