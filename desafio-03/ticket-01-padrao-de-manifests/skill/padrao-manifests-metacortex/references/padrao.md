# Padrão de Manifests da Metacortex — regras

Texto de consulta. Abra quando precisar citar a regra, explicar o porquê dela a alguém, ou
decidir se um desvio barra ou só pede justificativa.

**Força das regras:** `obrigatório` barra a revisão sem discussão. `recomendado` passa, mas a
exceção precisa estar escrita no PR. `proibido` tem caso registrado de estrago e não admite
exceção para workload de cliente.

**Conteúdo:** Bloco 1 identidade · Bloco 2 resiliência · Bloco 3 segurança · Exceções.

O Bloco 4 do padrão original (glossário de Pod, ReplicaSet, Deployment, Service, Endpoints,
ConfigMap/Secret e probes) não foi trazido: é material de onboarding para quem não conhece
Kubernetes, não regra conferível.

---

## Bloco 1 — Identidade e nomenclatura

### 1.1 Nome em kebab-case (obrigatório)
Minúsculo, palavras separadas por hífen. Sem camelCase, underscore ou ponto. Nome fora do padrão
quebra ferramenta de listagem e seletor escrito à mão.

`NyxAPI` errado · `nyx-api` certo

### 1.2 Namespace `<cliente>-<ambiente>` (obrigatório)
Ambientes válidos: `dev`, `stg`, `prod`. Um cliente nunca divide namespace com outro, nem um
ambiente com outro. Namespace fora desse formato não é criado pelo Construct — o manifesto não
tem onde aterrissar. Exemplos: `nyx-prod`, `orion-stg`, `helio-dev`.

### 1.3 Os quatro rótulos (obrigatório)
Em todo objeto — Deployment, Service, ConfigMap, Secret, Job, CronJob. Sustentam o inventário, o
rateio de custo por cliente e a resposta a "quem é o dono disso?" às três da manhã.

```yaml
app.kubernetes.io/name: nyx-api        # o componente
app.kubernetes.io/instance: nyx-prod   # a instalação
app.kubernetes.io/part-of: nyx         # o produto do cliente
app.kubernetes.io/managed-by: platform # platform | argocd | helm
```

O rótulo curto `app:` pode continuar existindo por compatibilidade com seletores antigos, mas não
substitui os quatro.

### 1.4 Selector casa com os rótulos do pod (obrigatório)
O `selector` do Service e o `matchLabels` do Deployment precisam ser idênticos aos rótulos do
template do pod, caractere por caractere.

É o erro mais comum do parque e o mais silencioso: o objeto sobe, a revisão passa, e o Service
fica sem endpoint. O objeto `Endpoints` não vem com lista vazia — o campo de endereços
simplesmente não aparece.

### 1.5 Anotação de dono (recomendado)
`metacortex.io/owner` com o time responsável, e `metacortex.io/runbook` com a URL do procedimento
de plantão quando existir.

### 1.6 Nome do container igual ao componente (recomendado)
Container chamado `app`, `main` ou `container` obriga quem lê log a abrir o manifesto para
descobrir o que é. Use `api`, `worker`, `scheduler`.

---

## Bloco 2 — Resiliência

### 2.1 requests e limits (obrigatório)
Todo container declara os quatro campos. Container sem requests é escalonado às cegas; sem limits
de memória derruba o nó do vizinho.

```yaml
resources:
  requests: {cpu: 100m, memory: 128Mi}
  limits:   {cpu: 500m, memory: 512Mi}
```

Regra de bolso da casa: limits de memória entre 1,5x e 2x o consumo observado em regime. Apertar
demais gera reinício por OOM; folgar demais desperdiça reserva do cliente.

### 2.2 readiness e liveness (obrigatório)
As duas, em qualquer ambiente, apontando para endpoints que a aplicação de fato expõe. Sem probe,
o Kubernetes considera o container pronto assim que o processo sobe e manda tráfego para
aplicação que ainda está carregando.

A distinção importa: readiness responde "posso receber tráfego agora?", liveness responde "ainda
estou vivo?". Apontar as duas para o mesmo endpoint que checa banco derruba a aplicação inteira
quando o banco fica lento — a liveness falha, o container reinicia, e o reinício não conserta
banco.

### 2.3 `replicas >= 2` em prod (obrigatório)
Réplica única em produção significa indisponibilidade a cada deploy, a cada drain de nó e a cada
evicção. Em dev e stg, uma réplica é aceitável.

### 2.4 Estratégia de atualização (obrigatório em prod)
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1
```
`maxUnavailable: 0` garante que a capacidade não cai durante o rollout. O custo é precisar de
espaço para uma réplica a mais durante a troca.

### 2.5 PodDisruptionBudget em prod (recomendado)
Todo workload de prod com mais de uma réplica declara um PDB com `minAvailable: 1` no mínimo. Sem
PDB, uma manutenção de nó pode derrubar todas as réplicas ao mesmo tempo.

### 2.6 `terminationGracePeriodSeconds` (recomendado)
O padrão de 30s não serve para worker que processa mensagem longa. Se a aplicação precisa de mais
tempo para drenar, declare — e garanta que ela trata SIGTERM.

---

## Bloco 3 — Segurança

Segurança & Compliance mantém uma varredura com Trivy no pipeline, sobre o diretório de manifests.
Ela não substitui esta página: o que a varredura não conhece continua sendo conferido na revisão.

### 3.1 Tag `:latest` (proibido)
Imagem sempre em tag imutável ou digest. `:latest` torna impossível saber o que está rodando,
quebra rollback e faz dois pods do mesmo Deployment rodarem versões diferentes.

`registry.metacortex.io/nyx/api:2.9.1` · melhor ainda, `...api@sha256:9f2c...`

### 3.2 securityContext (obrigatório)
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
```
`readOnlyRootFilesystem` exige que o que precisa escrever use `emptyDir` montado no caminho certo.
Dá trabalho uma vez e fecha uma classe inteira de escalonamento de privilégio.

### 3.3 Segredo em texto puro (proibido)
Nenhum valor sensível no manifesto — nem em `env.value`, nem em ConfigMap, nem em comentário.
Sempre por referência a um Secret.

```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef: {name: nyx-db, key: url}
```

Secret do Kubernetes é base64, não criptografia. O padrão vale para não versionar o segredo no
Git; proteção em repouso é assunto do cluster.

### 3.4 `automountServiceAccountToken: false` (obrigatório)
Quando o workload não fala com o apiserver — que é a maioria. Montar o token por padrão entrega
uma credencial de graça para quem comprometer o container.

### 3.5 ServiceAccount dedicada (recomendado)
Não use a `default` do namespace. Uma SA por workload, com RBAC mínimo — e nenhum RBAC quando ela
não fala com a API.

### 3.6 `hostNetwork`, `hostPID`, `privileged` (proibido)
Sem exceção em workload de cliente. Se for infraestrutura da própria Metacortex e precisar, o
pedido vai para Segurança com justificativa escrita.

### 3.7 Imagem só de registry interno (obrigatório)
Todo `image:` aponta para `registry.metacortex.io`. Imagem de registry público entra pelo Loom,
que a espelha, escaneia e republica internamente.

---

## Exceções

- Exceção a regra **obrigatória**: aprovação escrita de Segurança & Compliance no PR, com prazo
  de validade.
- Exceção a regra **recomendada**: justificativa no PR.
- Exceção a regra **proibida**: não existe, para workload de cliente.
