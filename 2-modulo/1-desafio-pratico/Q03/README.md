# Questão 03 - Relatório de redução de custos cloud

## Framework: T-A-G (Task – Action - Goal)

---

## Prompt

**Task:** Analise o breakdown de custos AWS do ultimo mes que está no formato CSV abaixo e gere um relatorio alinhado a meta de 15% de redução de custo Cloud, com as oportunidades de economia priorizadas por impacto.

CSV:

```csv
servico,categoria,custo_mensal_usd,uso_medio_pct,observacao
EC2 reservada,compute,4200,72,contrato de 1 ano
EC2 on-demand,compute,8200,45,workloads variaveis
EKS,compute,6700,58,3 clusters
RDS PostgreSQL,databases,8200,62,multi-AZ
ElastiCache Redis,databases,2100,40,cluster de producao
S3 Standard,storage,3100,,5 buckets principais
EBS gp3,storage,1600,68,volumes de producao
CloudWatch Logs,observability,2800,,retencao de 90 dias
CloudWatch Metrics,observability,900,,
Data Transfer Out,network,1900,,trafego entre regioes
NAT Gateway,network,1200,,3 gateways ativos
Lambda,compute,900,30,~12M invocacoes/mes
```

**Action:** O relatório deve trazer as oportunidades de economia priorizadas por impacto, quanto cada oportunidade de economia representa em percentual no valor da conta total, o esforço de implementação deve ser classificado entre: baixo, médio, alto.
Apresentar os riscos ou pré-requisitos envolvidos em cada oportunidade.

**Goal:** Alcançar 15% de redução no custo cloud até o fim do período, sem degradar SLA. 

---

## Modelo

**Sonnet 4.6** — Considerando o numero de tokens utilizado no prompt e o resultado esperado, não achei necessário utilizar um modelo acima no Sonnet 4.6 que comporta tranquilamente a requisição.

---

## Output

https://claude.ai/share/ede77d77-30c4-4894-b2ea-828e46312ad9

---

## Justificativa

- **Task:** Defino o que tenho em mãos (CSV) e o que precisa ser feito com esses dados, que seria a analise de custos para criação do relatório.
- **Action:** Detalho como quero que o relatório seja criado, com quais critérios e priorizações.
- **Goal:** Informo qual o objetivo final do relatório, para que ele está sendo construído, e o que quero atingir com o resultado final da resposta gerada pela IA.

---
