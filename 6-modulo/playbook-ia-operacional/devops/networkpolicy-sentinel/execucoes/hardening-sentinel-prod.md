## Execução — manifesto do Sentinel (namespace `sentinel-prod`)

**Modelo:** Claude Opus 5 · temperatura 0.1 (manifesto de segurança: reprodutibilidade prioritária
sobre variação). Revisão conduzida adotando o papel de revisor de segurança adversarial — sem
reaproveitar o raciocínio da geração, para não herdar seus pontos cegos.

### v1 — primeira geração

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

### Verificação 1 — perguntas de um revisor de segurança

1. **Os `podSelector` de `from`/`to` acima estão restritos ao namespace da política ou a qualquer
   pod do cluster com aquele label?** Relay está em `relay-prod`, API gateway em `edge`, Forge em
   `forge-prod`, Cerebro em `cerebro-prod`, DNS em `kube-system` — todos diferentes de
   `sentinel-prod`. Um `podSelector` sozinho em `from`/`to` só enxerga pods **do mesmo namespace**
   onde a `NetworkPolicy` está definida. Sem `namespaceSelector`, nenhuma dessas seis regras
   corresponde a pod nenhum, e o comportamento real seria negar tudo — o oposto do declarado.
   **CRÍTICO.**
2. **A regra de DNS libera UDP e TCP?** CoreDNS/kube-dns responde consultas por UDP normalmente,
   mas cai para TCP quando a resposta excede o tamanho do datagrama (respostas grandes, DNSSEC).
   A v1 só libera UDP/53. Sob certas consultas, a resolução de nomes falharia de forma
   intermitente e difícil de diagnosticar. **ALTO.**
3. **O `policyTypes` da política de allow inclui `Egress` mesmo sem nenhuma necessidade de ingress
   adicional além do já coberto?** Não é erro, mas vale confirmar que não sobrou nenhum
   `policyTypes` declarado sem `ingress`/`egress` correspondente — aqui os dois têm regra, então
   está correto. Sem achado.
4. **As portas de ingress (Relay → Sentinel, API gateway → Sentinel) foram restringidas?** O mapa
   de serviços não declara porta para essas duas entradas, e a v1 corretamente não inventou —
   mas isso significa ingress liberado em **qualquer porta** dos pods do Sentinel a partir dessas
   duas origens. É menos grave que allow-all (a origem continua restrita), mas é uma superfície
   maior do que o necessário. Vale registrar como item para o revisor decidir, não como bug do
   prompt. **MÉDIO, mas fora do escopo do que o mapa de serviços autoriza resolver sozinho.**
5. **A política de default-deny cobre `Egress` mesmo sem nenhuma política de allow para DNS
   *antes* de a política de allow existir?** Ordem de aplicação de NetworkPolicy no Kubernetes não
   é sequencial — as duas políticas coexistem e o efeito é a união dos allows sobre a negação
   base. Não há problema de ordem aqui. Sem achado.
6. **O nome dos objetos seguirá convenção usada em outras NetworkPolicy do cluster?** Não há dado
   suficiente no mapa de serviços ou no padrão para confirmar convenção de nomenclatura além do que
   foi pedido. Fora do escopo verificável com o material disponível.

**Veredito da rodada 1:** 1 achado CRÍTICO (namespaceSelector ausente — a política, como escrita,
não libera o tráfego que deveria e na prática se comporta como default-deny total, quebrando
Sentinel/Relay/Forge/Cerebro em produção) e 1 achado ALTO (DNS só UDP). Não passa. Segue para v2.

### v2 — refino

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

### Verificação 2 — segunda rodada, adversarial

1. **O namespaceSelector + podSelector combinado resolve o achado crítico?** Sim — agora cada peer
   exige as duas condições simultaneamente, e como está dentro do mesmo item de `from`/`to`
   (mesmo nível de indentação, um único elemento de lista), o Kubernetes interpreta como AND, não
   como duas entradas separadas. Confirma-se a correção.
2. **DNS cobre os dois protocolos?** Sim, UDP e TCP na porta 53, ambos com o mesmo peer. Achado ALTO
   fechado.
3. **Alguma regra ainda usa `podSelector: {}` ou `- {}` fora da política de default-deny?** Não —
   inspecionado item a item, todo `podSelector` na política de allow tem `matchLabels`, e toda
   entrada de `ingress`/`egress` tem `from`/`to` com peer explícito.
4. **A dependência do label automático de namespace foi declarada, ou ficou implícita?** Foi
   declarada explicitamente nas perguntas em aberto — isso é o correto a fazer, porque é uma
   suposição sobre o ambiente que o prompt não tem como confirmar sozinho, mas classificaria como
   crítica caso a suposição fosse falsa e ficasse silenciosa. Como está registrada e não escondida
   dentro da lógica da regra, considero adequada para produção assim que a suposição for validada
   — não é um bug do manifesto, é uma pré-condição de ambiente corretamente exposta.
5. **Existe algum caminho de tráfego que o padrão exige e que ficou de fora?** Conferindo contra as
   cinco regras do padrão uma a uma: ingress de Relay ✓, ingress de API gateway ✓, egress para
   Forge:5432 ✓, egress para Cerebro:9200 ✓, egress para DNS ✓, nenhum allow-all em nenhum lado ✓,
   default-deny explícita e separada ✓, todo peer comentado ✓. Nenhuma lacuna restante frente ao
   padrão fornecido.
6. **A regra de ingress permanece mais aberta que o necessário quanto à porta?** Sim, mas isso não é
   um defeito do manifesto — é a consequência correta de o mapa de serviços não declarar a porta do
   Sentinel, e o prompt está proibido de inventar. Continua registrado como pergunta em aberto, não
   como achado a corrigir sozinho.

**Veredito da rodada 2:** zero achados CRÍTICO ou ALTO. As únicas pendências restantes são as duas
perguntas em aberto, ambas dependentes de informação que não está no mapa de serviços fornecido —
critério de parada atingido. v2 é a versão final para revisão humana.
