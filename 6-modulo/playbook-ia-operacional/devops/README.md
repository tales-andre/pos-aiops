# DevOps

Prompts voltados a **infraestrutura, automação e operação** de sistemas: pipelines de CI/CD, containers, orquestração, provisionamento, observabilidade, confiabilidade e segurança operacional.

## Escopo

Entram aqui prompts relacionados a:

- Pipelines de CI/CD (GitHub Actions, GitLab CI, Jenkins etc.).
- Containers e orquestração (Docker, Kubernetes, Helm).
- Infraestrutura como código (Terraform, Pulumi, Ansible).
- Provedores de nuvem (AWS, GCP, Azure) e seus recursos.
- Observabilidade (logs, métricas, tracing, alertas, dashboards).
- Confiabilidade, SRE, postmortems e análise de incidentes.
- Segurança operacional (hardening, secrets, políticas de acesso).

## Fora de escopo

- Escrita de código de aplicação → usar `desenvolvimento/`.
- Conteúdo educacional sobre DevOps (aulas, artigos, vídeos) → usar `criacao-conteudo/`.

## Prompts

- [triagem-de-pods](./triagem-de-pods/) — diagnostica pods problemáticos de um cluster Kubernetes a partir de um snapshot, cruzando status, eventos e logs.
- [nota-de-triagem](./nota-de-triagem/) — transforma um alerta cru de monitoramento em uma nota de triagem padronizada de cinco campos.
- [causa-raiz](./causa-raiz/) — analisa a causa-raiz de uma degradação cruzando configuração, métricas e logs, separando causa de sintoma.
- [backpressure-relay](./backpressure-relay/) — apoia uma decisão de backpressure comparando opções contra as restrições, com matriz de decisão e recomendação em camadas.
- [migracao-forge](./migracao-forge/) — cadeia de três prompts que conduz a migração de um pipeline de lote para orientado a eventos (diagnóstico → estratégia em fases → plano executável).
- [networkpolicy-sentinel](./networkpolicy-sentinel/) — endurece um manifesto de NetworkPolicy permissivo em default-deny + allow least-privilege, com cadeia de geração + verificação (Chain-of-Verification) e critério de parada.
