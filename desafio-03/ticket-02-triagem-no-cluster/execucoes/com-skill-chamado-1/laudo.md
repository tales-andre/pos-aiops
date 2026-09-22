# Triagem — nyx-prod

**Sintoma declarado:** cliente nyx relata que a API do produto, em produção, "fica reiniciando sozinha".

**Causa:** o container `api` é morto pelo kernel por estouro de memória — `lastState.terminated` traz `reason: OOMKilled`, `exitCode: 137` nos dois pods — contra um `limits.memory: 24Mi` declarado no Deployment `nyx-api`; ele sobe, consome mais que o teto em 1–2 segundos e é morto, e o controlador reinicia em laço (`CrashLoopBackOff`).

Coletado em 2026-09-22T12:15Z, cluster `metacortex-lab`, namespace `nyx-prod`.

## Como cheguei

O verbo do chamado foi "reinicia" — porta de entrada pelo estado do container (`lastState.terminated`), não pelos eventos. O retrato do namespace (`snapshot.py`) já entregou a causa na camada 3; as camadas seguintes foram percorridas apenas para descartar alternativas e separar causa de ruído.

| Camada | O que olhei | O que encontrei |
|---|---|---|
| 1. Declaração | `get deployment nyx-api -o yaml` | 2 réplicas desejadas, imagem `fabricioveronez/kube-news:v1.0.0`, revisão 2. `resources.limits.memory: 24Mi`, `requests.memory: 16Mi`. `readinessProbe` em `/ready:8080` com `initialDelaySeconds: 10`. Condição `Available=False` / `MinimumReplicasUnavailable`, `unavailableReplicas: 2`. |
| 2. Agendamento | `get pods -o wide`, condições do pod, `get nodes` | Descartado. Os dois pods estão `PodScheduled=True` no nó `metacortex-lab-control-plane`, com IP atribuído. Nenhum `Pending`. O nó tem 7.997.664Ki alocáveis e `MemoryPressure=False` — não há pressão de memória no host; o estouro é do cgroup do container. |
| 3. Container | `snapshot.py`, `describe pod`, `containerStatuses` em JSON | **Aqui está a causa.** `nyx-api-6bb9d659c5-fzv86`: `lastState.terminated.reason: OOMKilled`, `exitCode: 137`, `startedAt 12:13:56Z` → `finishedAt 12:13:58Z`, 5 reinícios. `nyx-api-6bb9d659c5-jcz42`: mesmo `OOMKilled` / `137`, `startedAt 12:11:06Z` → `finishedAt 12:11:05Z`, 6 reinícios. Estado atual dos dois: `waiting.reason: CrashLoopBackOff`, com back-off já saturado em 5m0s. A imagem **foi baixada com sucesso** (`Successfully pulled image ... in 8.87s`) — não é problema de pull na revisão vigente. |
| 4. Aplicação (logs) | não percorrida, deliberadamente | `OOMKilled` com `exitCode 137` significa que o processo foi morto de fora, pelo kernel, e não que a aplicação decidiu sair. Log só entraria na conta em `exitCode: 1` / `reason: Error`. A causa já liga sintoma a fato observado sem "provavelmente"; a triagem para aqui. |
| 5. Rede | `snapshot.py` seção 5, `get endpoints` | Descartada como causa. O Service `nyx-api` (ClusterIP) tem `selector: {app: nyx-api}` e **2 pods casam** com ele — o metadado está coerente. Os `endpoints nyx-api` com 0 endereços são **consequência**, não causa: pod que não fica `Ready` não entra no Endpoints, e a `readinessProbe` (delay de 10s) nunca chega a ser avaliada, porque o container morre com 1–2 segundos de vida. |

### Ruído descartado no caminho

Os eventos de Warning do namespace trazem `Failed to pull image "fabricioveronez/kube-news:v1" ... no match for platform in manifest` nos pods `nyx-api-5ddc9d474c-gz7v2` e `-hmmv9`, com `ErrImagePull` / `ImagePullBackOff`. **Isso não é a causa do chamado atual.**

Esses pods pertencem ao ReplicaSet `nyx-api-5ddc9d474c`, de uma revisão anterior, que já não existe — `get rs -n nyx-prod` lista apenas `nyx-api-6bb9d659c5` e `nyx-postgres-5c64c56fc4`. A revisão vigente do Deployment é a 2, com imagem `:v1.0.0`, cujo pull teve sucesso. São eventos residuais de um rollout já superado — e um bom exemplo de por que os eventos não são a porta de entrada para sintoma de reinício.

## O que estava saudável ao lado

- **`nyx-postgres`**: `1/1` pronto, `Running`, **0 reinícios**, no mesmo namespace e no mesmo nó. A diferença observável entre os dois workloads está justamente em `resources`: o Deployment `nyx-postgres` declara `resources: {}` — sem requests nem limits —, enquanto o `nyx-api` tem teto de 24Mi. É esse contraste que aponta para o limite, e não para o nó, a imagem ou o cluster.
- **Nó `metacortex-lab-control-plane`**: `Ready`, `MemoryPressure=False`, ~7,6Gi alocáveis. Descarta esgotamento de memória do host e despejo por pressão de nó.
- **Registry e imagem da revisão vigente**: `v1.0.0` puxada com sucesso e presente na máquina (`already present on machine` nos restarts seguintes). Descarta causa fora do cluster.
- **Metadado de rede**: o selector do Service casa com os rótulos do template do pod (`app: nyx-api`), caractere por caractere. Descarta a assinatura de "aplicação saudável e ninguém chega nela".
- **Agendamento**: nenhum pod `Pending`; sem quota, afinidade ou falta de nó em jogo.
- **Conectividade com o banco**: não avaliada, e não necessária — o container não sobrevive tempo suficiente para tentar conectar, e a morte por `OOMKilled` já é causa observada e suficiente.

## Correção sugerida (não aplicada)

**Nada foi escrito no cluster.** Todos os comandos desta triagem foram `get` e `describe`; o `snapshot.py` da skill só aceita o verbo `get`.

O caminho é elevar o teto de memória do container `api` no Deployment `nyx-api` para um valor compatível com o consumo real da aplicação. 24Mi é um teto que a imagem `kube-news` não sustenta nem na inicialização — ela morre em 1–2 segundos, antes mesmo de responder à primeira probe.

Ressalva de rigor: **não há medição de consumo real neste cluster** (não foi observado metrics-server disponível), então qualquer número abaixo é ponto de partida a validar, não fato medido. Sugestão de partida: `limits.memory: 256Mi` com `requests.memory: 128Mi`; subir, e então medir o consumo em regime (`kubectl top pod -n nyx-prod`, com metrics-server, ou o painel de observabilidade do parque) para ajustar. Vale também aproximar o `requests` do consumo em repouso — mantê-lo muito abaixo do limite deixa o pod em QoS `Burstable` e sujeito a despejo sob pressão de nó.

Comando sugerido, **não aplicado**:

```
kubectl -n nyx-prod patch deployment nyx-api --type=json \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"},
       {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"128Mi"}]'
```

Se o Deployment for gerenciado por GitOps ou manifesto versionado, esse `patch` seria sobrescrito na próxima sincronização — nesse caso a mudança vai no repositório de manifests, não no cluster.

**A decisão de aplicar é de quem está de plantão.** Duas perguntas que deveriam ser respondidas antes de fechar o chamado, e que estão fora do escopo da triagem:

1. **De onde veio o `24Mi`?** O limite está na revisão vigente, e o vizinho no mesmo namespace não tem limite nenhum. Vale conferir no repositório de manifests se houve uma passada de aperto de limites que pegou o `nyx-api` e não o `nyx-postgres`. Sem responder isso, a correção volta a cair no próximo deploy.
2. **O `nyx-postgres` roda sem nenhum request/limit em produção.** Não é a causa deste chamado, mas é um pod sem contenção num nó compartilhado — assunto para o Padrão de Manifests, não para este plantão.

## Saídas brutas

| Arquivo | Conteúdo |
|---|---|
| `01-snapshot.txt` | `snapshot.py nyx-prod` — retrato completo do namespace (script da skill, somente-leitura) |
| `02-workloads-e-revisoes.txt` | `get deploy,rs,pods -o wide` e listagem de ReplicaSets com imagem — usado para descartar o `ImagePullBackOff` residual |
| `03-describe-pod-e-laststate.txt` | `describe pod nyx-api-6bb9d659c5-jcz42` e `containerStatuses` em JSON dos dois pods — evidência do `OOMKilled` / `exitCode 137` |
| `04-declaracao-deployment-e-no.txt` | `get deployment nyx-api -o yaml`, `resources` do `nyx-postgres` e condições/alocável do nó |
