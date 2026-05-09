# Questão 07 - Runbook para alerta recorrente

## Framework: R-I-S-E (Role – Input – Steps – Expectation)

---

## Prompt

**Role:** Você é um SRE especialista em criação de runbooks para resoluções de incidentes e troubleshooting. Os runbooks criados são objetivos e claros, justamente para que qualquer analista de SRE possa solucionar problemas e incidentes, mesmo sem conhecimento prévio do ambiente.

**Input:** O alerta dispara em média 4 vezes toda semana na ferramenta de monitoração. A resolução varia de 30 a 40 minutos pois não existe um runbook para fazer a analise e resolução do incidente.
Nome do alerta: [CRITICAL] High memory usage on Chronos API pods (>85% for 10min)
Ambiente do Chronos API:
Chronos roda no EKS, namespace production, 6 réplicas com HPA configurado (min 4, max 12, CPU target 70%).
Deploy via Argo CD a partir do repositório hvt/chronos-api.
Dependências diretas: Data Warehouse Ledger (PostgreSQL) e Reactor (filas SQS).
Observabilidade: métricas expostas em /metrics, logs centralizados no Beacon (Ferramenta de Monitoração), dashboards em Grafana.
Ferramentas disponíveis para o plantonista SRE: kubectl, aws cli, argocd cli.
Canal de plantão: #oncall-chronos no Slack.
Time sênior de escalação: @chronos-core (SLA de resposta: 15 minutos em horário comercial, 30 fora).

**Steps:** O runbook deve seguir os seguintes passos, utilizando as ferramentas disponíveis: kubectl, aws cli, argocd cli.
1 - Diagnóstico: Passos iniciais de diagnósticos, com comandos específicos para executar, visando troubleshooting, sem alterações no ambiente. A cada comando de diagnóstico, informar qual o resultado esperado (saudável) e quais seriam os possíveis desvios que apontem a causa do problema, a partir disso informar quais os próximos passos.
2 - Resolução: Informar ações corretivas para cada cenário com erro identificado na fase 1 - Diagnóstico.
3 - Escalação: Critérios objetivos para escalar para o time sênior @chronos-core
4 - Encerramento: Critério para encerrar o incidente e confirmar que o alerta foi resolvido.

**Expectation:** Criação de um Runbook claro e objetivo, estruturado de forma procedural para que qualquer plantonista consiga seguir de ponta a ponta sem depender de quem conhece o sistema, até mesmo um plantonista que esteja começando hoje na empresa. Os comandos devem ser copiáveis, cada passo deve ter um checkpoint de decisão claro para saber se foi resolvido ou não e qual o próximo passo, com critérios de escalação e encerramento do incidente. Disponibilizar no formato PDF para download.

---

## Modelo

**Sonnet 4.6** — Para esse caso tive que efetuar correções no prompt durante as execuções, pois o resultado final não estava objetivo para que qualquer um pudesse seguir.
Usei vários modelos, Sonnet 4.6, Opus 4.6, Gemini Pro, Gemini Raciocício, até chegar no prompt e modelo final.
Definitivamente o Sonnet 4.6 foi o campeão, trazendo uma estrutura objetiva com um mapeamento claro do que fazer desde o primeiro step.
Em determinado momento solicitei download em PDF para o Sonnet e retornou um arquivo completamente destruturado e cheio de caracteres especiais.

---

## Output

https://claude.ai/share/cdd8ef3c-01e9-4bfd-859d-320a5f180973

---

## Justificativa

**Role:** Informo a persona e contexto atual que deve ser seguido.

**Input:** Informo os detalhes do sistema, o tempo de resolução de incidentes e o motivo para demorar tanto, que é a falta de um runbook para o time de SRE, as informações são necessárias para dar um contexto para os Steps, na criaçao do runbook.

**Steps:** Informo o passo a passo a ser seguido pelo runbook, aqui foi necessário fazer alterações para que já no primeiro step ficasse claro para quais passos seguir em caso falhas identificadas. 

**Expectation:** Informo que quero um runbook que possa ser utilizado por qualquer um, até mesmo quem estiver começando hoje na empresa, fazendo com que a geração seja o mais objetiva e clara possível.

---
