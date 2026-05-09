# Questão 08 - Postmortem técnico de incidente em produção

## Framework Escolhido: T-A-G (Task – Action - Goal)

---

## Prompt

**Task:** Um incidente está em andamento em horário de pico. Analise as informações dos artefatos abaixo e produza um relatório técnico para auxiliar na tomada de decisão entre rollback do deploy v2.48.0 (que subiu ontem) e scaling emergencial (aumento de limits do RDS e do pool de conexões). O relatório deve ser claro e objetivo, trazendo insumos para tomada de decisão. Os artefatos disponíveis para análise são os seguintes:

1- Evento do deploy anterior (ontem, 18:42 UTC):

Deploy chronos-api: v2.47.0 -> v2.48.0
Argo CD sync: 2026-04-23 18:42:11 UTC
Changelog:
- Adicionado endpoint POST /v2/transactions/batch
- Refatorado cliente do Ledger (pool de conexoes movido para nova biblioteca interna)
- Bump de psycopg 3.1.18 -> 3.2.0
- Reduzido timeout do Ledger de 5s para 2s

2- Métricas do Beacon nos últimos 30 minutos:

timestamp                p99_latency_ms   req_rate_s   err_rate_pct
2026-04-24 13:30 UTC     420              1200         0.2
2026-04-24 13:45 UTC     510              1450         0.3
2026-04-24 14:00 UTC     780              1780         0.8
2026-04-24 14:10 UTC     2400             2100         4.5
2026-04-24 14:15 UTC     5200             2400         8.2
2026-04-24 14:20 UTC     8100             2650         11.7

3 - Trecho do log do pod chronos-api-79c4d8b9-xk2jp:

2026-04-24 14:19:48 [ERROR] [ledger-client] connection pool exhausted (max=20, active=20, waiting=147)
2026-04-24 14:19:49 [WARN]  [ledger-client] query timeout after 2000ms: SELECT ... FROM transactions WHERE ...
2026-04-24 14:19:49 [ERROR] [handler] POST /v2/transactions/batch failed: context deadline exceeded
2026-04-24 14:19:50 [ERROR] [ledger-client] connection reset by peer
2026-04-24 14:19:51 [WARN]  [circuit-breaker] ledger-client OPEN (threshold 50%, current 87%)
2026-04-24 14:19:52 [ERROR] [reactor] failed to publish message: chronos-api upstream error

4 - Estado do Reactor (fila chronos-transactions):

50.127 mensagens acumuladas, crescendo a ~800/min.
Consumer lag atual: 18 minutos e aumentando.

5 - Estado do cluster:

Chronos: 12/12 pods running (HPA no máximo).
CPU médio dos pods: 62%.
Memória média dos pods: 71%.
Conexões ativas ao Ledger: 240/250 (limite do RDS).

**Action:** Analise os artefatos fornecidos e indique claramente qual ação tomar: rollback do v2.48.0 ou scaling emergencial, com justificativa técnica baseada nos dados apresentados.

**Goal:** Auxiliar a decisão do CTO de forma rápida. A análise deve ser objetiva, baseada apenas nos artefatos fornecidos, sem especulações, e com uma recomendação clara e justificativa técnica.

---

## Modelo

**Gemini 3 - Raciocínio** — Considerando o numero de informações e necessidade de tomada de decisão, escolhi um modelo que tivesse boa capacidade de racicínio para resolver problemas em contexto de urgência

---

## Output

https://gemini.google.com/share/532de019271f
---

## Justificativas

## Escolha do Framework T-A-G
 - A escolha foi baseada nas informações disponíveis na questão 8: O que fazer, Como fazer e Qual o objetivo final.

  - **Task:** Define o problema e entrega os artefatos, informo a necessidade de decisão entre rollback e scaling. O modelo recebe o contexto completo do que precisa analisar.
  - **Action:** Instrui o modelo a analisar os artefatos e indicar claramente qual ação tomar, com justificativa técnica baseada nos dados.
  - **Goal:** O objetivo final: Auxiliar a decisão do CTO de forma objetiva e clara.

## Comparação com frameworks alternativos

- **RISE:** Seria o melhor, teria o input separando os artefatos da instrução, o objetivo final (expectativa) solicitando o relatório com a tomada de decisão, porém, a questão não trouxe insumos referente a quais passos (Steps) o relatório deveria seguir para chegar no resultado final, sendo assim, não escolhi o RISE.

- **CARE:** Seria um forte candidato para produzir um documento padronizado com o resultado final informando qual decisão deveria ser tomada, porém na questão não havia exemplos de documentos anteriores para serem seguidos.

- **BAB:** Seria um framework intereessante, pensando em um registro tecnico mostrando o antes e depois do ambiente após o rollback, o que não é solicitado na questão.
---

## Nota sobre a nomenclatura::
- O enunciado informa a nessecidade de um **postmortem**, porém no meu entendimento ficou confuso elaborar um postmortem para um incidente que está em andamento, já que o postmortem é para ser um documento após a resolução de um incidente. Sendo assim, para não causar alucinações na IA (assim como causou em mim), ou incluir o termo RCA, resolvi tratar o prompt como "relatório técnico"

---
