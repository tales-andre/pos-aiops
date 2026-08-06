## Execução — manifesto do Sentinel (namespace `sentinel-prod`)

**Modelo:** Claude Opus 5 · temperatura 0.1 (manifesto de segurança: reprodutibilidade prioritária
sobre variação).

### v1 — geração (CoVe passo 1)

```yaml
# default-deny explícita: sozinha, já bloqueia 100% do tráfego do namespace.
# As políticas abaixo são as únicas exceções liberadas.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sentinel-prod-default-deny-all
  namespace: sentinel-prod
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sentinel-prod-allow-sentinel
  namespace: sentinel-prod
spec:
  podSelector:
    matchLabels:
      app: sentinel
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Relay publica eventos de telemetry que o Sentinel consome para alerting
    - from:
        - podSelector:
            matchLabels:
              app: relay
    # API gateway encaminha requisições externas para o Sentinel
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway
  egress:
    # Sentinel grava/lê tabelas agregadas no warehouse do Forge
    - to:
        - podSelector:
            matchLabels:
              app: forge
      ports:
        - protocol: TCP
          port: 5432
    # Sentinel consulta o índice do Cerebro para investigação de incidentes
    - to:
        - podSelector:
            matchLabels:
              app: cerebro
      ports:
        - protocol: TCP
          port: 9200
    # Resolução de nomes internos do cluster
    - to:
        - podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53

# PERGUNTAS EM ABERTO PARA O REVISOR:
# nenhuma
```

### Verificação 1 (CoVe passos 2 e 3 — perguntas planejadas e respondidas isoladamente)

| # | Veredito | Severidade | Evidência no YAML |
|---|---|---|---|
| 1 | ACHADO | **CRÍTICO** | Relay/relay-prod, API gateway/edge, Forge/forge-prod, Cerebro/cerebro-prod, DNS/kube-system — todos fora de `sentinel-prod`. Os seis peers usam só `podSelector`, sem `namespaceSelector`. `podSelector` isolado só enxerga pods do namespace da política → nenhuma regra casa → efeito real = negar tudo |
| 2 | OK | NENHUM | Não há `namespaceSelector` presente ainda; a falha é a ausência dele (pergunta 1), não OR indevido |
| 3 | OK | NENHUM | `podSelector: {}` só na `default-deny-all`; nenhum `- {}` em ingress/egress da allow |
| 4 | ACHADO | **ALTO** | Regra de DNS libera só `UDP/53`. Falta `TCP/53` para respostas grandes/DNSSEC/fallback → resolução intermitente e difícil de diagnosticar |
| 5 | OK (parcial) | MÉDIO | Todos os fluxos do padrão têm regra. Mas ingress de Relay e de API gateway não tem porta no mapa de serviços → liberado em qualquer porta do Sentinel. Não é bug (o mapa não declara a porta); registrar como pergunta em aberto |
| 6 | OK | NENHUM | `default-deny-all` com `podSelector: {}` e `policyTypes` sem regras → nega 100% |
| 7 | OK | NENHUM | 5432, 9200, 53 — todas presentes no mapa de serviços; nenhuma inventada |
| 8 | ACHADO | MÉDIO | A correção da pergunta 1 vai exigir `namespaceSelector`, que dependerá do label automático de namespace — precisa ser declarado como pré-condição, não deixado implícito |

**VEREDITO DA RODADA 1: REPROVADO** — 1 CRÍTICO (seletores cross-namespace não casam; manifesto se
comporta como default-deny total e quebra Sentinel/Relay/Forge/Cerebro em produção) e 1 ALTO (DNS só
UDP). Segue para v2.

### v2 — refino (CoVe passo 4 — versão verificada)

```yaml
# default-deny explícita: sozinha, já bloqueia 100% do tráfego do namespace.
# As políticas abaixo são as únicas exceções liberadas.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sentinel-prod-default-deny-all
  namespace: sentinel-prod
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sentinel-prod-allow-sentinel
  namespace: sentinel-prod
spec:
  podSelector:
    matchLabels:
      app: sentinel
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Relay (namespace relay-prod) publica eventos de telemetry que o Sentinel consome
    # para alerting. namespaceSelector + podSelector no mesmo item: exige as duas
    # condições ao mesmo tempo, não uma origem OU outra.
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: relay-prod
          podSelector:
            matchLabels:
              app: relay
    # API gateway (namespace edge) encaminha requisições externas para o Sentinel
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: edge
          podSelector:
            matchLabels:
              app: api-gateway
  egress:
    # Sentinel grava/lê tabelas agregadas no warehouse do Forge (namespace forge-prod)
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: forge-prod
          podSelector:
            matchLabels:
              app: forge
      ports:
        - protocol: TCP
          port: 5432
    # Sentinel consulta o índice do Cerebro para investigação de incidentes
    # (namespace cerebro-prod)
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: cerebro-prod
          podSelector:
            matchLabels:
              app: cerebro
      ports:
        - protocol: TCP
          port: 9200
    # Resolução de nomes internos do cluster via CoreDNS/kube-dns (namespace kube-system).
    # UDP para consultas normais, TCP para respostas grandes/DNSSEC ou fallback de UDP.
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53

# PERGUNTAS EM ABERTO PARA O REVISOR:
# - Ingress de Relay e de API gateway para o Sentinel não tem porta restrita no mapa de
#   serviços fornecido. A regra libera essas duas origens em qualquer porta dos pods do
#   Sentinel. Confirmar se a porta da API do Sentinel deve ser adicionada ao mapa de
#   serviços para fechar essa regra também por porta.
# - namespaceSelector assume o label automático `kubernetes.io/metadata.name` (padrão
#   desde Kubernetes 1.21) nos namespaces relay-prod, edge, forge-prod, cerebro-prod e
#   kube-system. Se algum desses namespaces tiver esse label alterado manualmente, a
#   regra correspondente para de casar. Vale confirmar antes de aplicar em produção.
```

### Verificação 2 (segunda rodada de CoVe, adversarial)

| # | Veredito | Severidade | Evidência no YAML |
|---|---|---|---|
| 1 | OK | NENHUM | Cada peer cross-namespace agora tem `namespaceSelector` + `podSelector` no mesmo item; achado crítico da rodada 1 fechado |
| 2 | OK | NENHUM | `namespaceSelector` e `podSelector` no mesmo elemento da lista → AND, não OR |
| 3 | OK | NENHUM | Nenhum `podSelector: {}` fora da default-deny; nenhum `- {}` |
| 4 | OK | NENHUM | DNS agora com `UDP/53` e `TCP/53` no mesmo peer; achado ALTO fechado |
| 5 | OK | NENHUM | Ingress Relay ✓, ingress API gateway ✓, egress Forge:5432 ✓, egress Cerebro:9200 ✓, egress DNS ✓, sem allow-all, default-deny explícita, todo peer comentado |
| 6 | OK | NENHUM | `default-deny-all` inalterada; nega 100% |
| 7 | OK | NENHUM | Portas 5432/9200/53 conferem com o mapa |
| 8 | OK | MÉDIO (documentado) | Dependência do label automático de namespace declarada no bloco de perguntas em aberto — pré-condição exposta, não implícita |

**VEREDITO DA RODADA 2: APROVADO** — zero achados CRÍTICO ou ALTO. As duas pendências restantes
dependem de dado fora do mapa de serviços e estão documentadas. Critério de Parada atingido. v2 é a
versão final para revisão humana.
