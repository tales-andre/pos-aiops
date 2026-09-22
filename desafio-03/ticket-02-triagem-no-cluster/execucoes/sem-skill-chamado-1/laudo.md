# Laudo de triagem — chamado nyx: "a API fica reiniciando sozinha"

- **Cliente / namespace:** nyx — `nyx-prod`
- **Workload:** `deployment/nyx-api` (2 réplicas), imagem `fabricioveronez/kube-news:v1.0.0`
- **Cluster:** `metacortex-lab` (kind, nó único `metacortex-lab-control-plane`, k8s v1.27.3)
- **Data da triagem:** 22/09/2026, ~09:15–09:17 BRT
- **Plantonista:** SRE Metacortex
- **Ação no cluster:** nenhuma. Triagem 100% de leitura (a única exceção foi um `kubectl exec ... cat` de leitura em **staging**, não em produção).

---

## 1. Veredito

**A API não está "reiniciando sozinha": ela está sendo morta pelo kernel por estouro de memória (OOMKill) a cada inicialização, porque o limite de memória declarado no Deployment (`24Mi`) é menor do que a memória que a aplicação precisa para subir (~34 MiB medidos).**

O Kubernetes, com `restartPolicy: Always`, reinicia o container a cada morte — e como a causa é determinística (o app sempre precisa de mais de 24Mi), o ciclo nunca converge e o pod cai em `CrashLoopBackOff`.

- **Categoria:** erro de configuração de recursos no manifesto (não é bug de aplicação, não é falha de infraestrutura, não é falha de dependência).
- **Confiança:** alta. A causa está provada por três evidências independentes e convergentes (seção 3).
- **Impacto atual:** **indisponibilidade total da API em produção.** O `deployment/nyx-api` está `0/2` disponível e o `service/nyx-api` está **sem endpoints** — nenhum tráfego é entregue.

---

## 2. Sintoma observado

```
NAME                            READY   STATUS             RESTARTS        AGE
nyx-api-6bb9d659c5-fzv86        0/1     CrashLoopBackOff   5 (97s ago)     7m27s
nyx-api-6bb9d659c5-jcz42        0/1     CrashLoopBackOff   6 (4m30s ago)   10m
nyx-postgres-5c64c56fc4-5ckmm   1/1     Running            0               13m
```

As duas réplicas da API estão no mesmo estado. O banco está saudável.

---

## 3. Evidências

### 3.1. O kernel diz explicitamente que é OOM (evidência direta)

Em **ambos** os pods, o estado da última execução do container é idêntico (`03-describe-pod-fzv86.txt`, `04-describe-pod-jcz42.txt`):

```
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
      Started:      Tue, 22 Sep 2026 09:13:56 -0300
      Finished:     Tue, 22 Sep 2026 09:13:58 -0300
    Restart Count:  5
    Limits:
      cpu:     200m
      memory:  24Mi
```

`Reason: OOMKilled` + `Exit Code: 137` (128 + SIGKILL) é o registro que o kubelet grava quando o **cgroup do container** estoura o limite e o OOM killer do kernel mata o processo. Não é interpretação: é o campo que o próprio kubelet preencheu.

Repare também na janela `Started` → `Finished`: **2 segundos**. O processo nem chega ao regime de operação — morre durante a subida.

### 3.2. A aplicação precisa de ~34 MiB; o limite é 24Mi (evidência quantitativa)

O `metrics-server` não está instalado neste cluster (`kubectl top` retorna `Metrics API not available`), então a medição foi feita lendo o cgroup diretamente. Como o pod de produção morre em 2 s e não dá para medi-lo, usei como **controle a mesma aplicação, a mesma imagem, rodando em `nyx-stg`** (`12-memoria-real-stg.txt`):

```
pod nyx-stg/nyx-api-69695bc4d6-4927k -> memory.current = 35909632 bytes = 34.2 MiB
pod nyx-stg/nyx-api-69695bc4d6-j882k -> memory.current = 35323904 bytes = 33.7 MiB

Limite configurado em nyx-prod: 24Mi = 25165824 bytes
```

A aplicação consome **~1,4x o limite que prod lhe concede**. Com esse limite, é aritmeticamente impossível o container sobreviver — o resultado não é intermitente, é garantido.

### 3.3. Staging é o experimento de controle que isola a variável (evidência comparativa)

`10-comparacao-nyx-stg.txt`:

| | `nyx-prod` | `nyx-stg` |
|---|---|---|
| Imagem | `fabricioveronez/kube-news:v1.0.0` | `fabricioveronez/kube-news:v1.0.0` (idêntica) |
| `resources` | `limits: {cpu: 200m, memory: 24Mi}` / `requests: {cpu: 50m, memory: 16Mi}` | `{}` (sem limite) |
| Estado | `0/1 CrashLoopBackOff`, 5–6 restarts | `1/1 Running`, **0 restarts** há 12 min |

Mesma imagem, mesmo nó, mesmo par app+postgres, mesma versão de kubelet. A **única** diferença relevante entre o ambiente que quebra e o que funciona é o bloco `resources`. Isso descarta bug de aplicação, imagem corrompida e problema de plataforma.

### 3.4. Descarte das hipóteses concorrentes

| Hipótese | Descartada porque |
|---|---|
| **Falha do banco de dados** | `nyx-postgres` está `1/1 Running`, 0 restarts, e os logs mostram `database system is ready to accept connections` seguido apenas de checkpoints de rotina (`14-logs-postgres-prod.txt`). O endpoint `nyx-postgres → 10.244.0.5:5432` existe e está populado (`13-endpoints-nyx-prod.txt`). Além disso, falha de conexão a banco produziria exit code de aplicação (tipicamente 1) e mensagem no log, não `OOMKilled`/137. |
| **Liveness probe matando o pod** | **Não existe liveness probe** no Deployment (`06-deployment-nyx-api.yaml`). Só há `readinessProbe`, e readiness **nunca reinicia** um container — apenas o remove dos endpoints do Service. Os restarts, portanto, não podem vir de probe. |
| **Pressão de memória no nó / evicção** | O nó está saudável: `MemoryPressure False`, `KubeletHasSufficientMemory`. De 7,6 GiB alocáveis, há apenas **322 MiB de requests (4%) e 438 MiB de limits (5%)** comprometidos (`08-describe-node.txt`). Sobra memória de fábrica no nó — o estouro é do cgroup do container, não do host. Evicção por nó também apareceria como `Evicted`, não `OOMKilled`. |
| **LimitRange do namespace injetando o limite** | `No resources found in nyx-prod namespace` para `limitrange` e `resourcequota` (`09-limitrange-quota.txt`). O `24Mi` não foi injetado pela plataforma — veio do próprio manifesto do cliente, e está visível no `kubectl.kubernetes.io/last-applied-configuration` do Deployment. |
| **Problema de imagem** | A imagem baixa e o container **inicia** (`Created` / `Started` nos eventos, 5x). A mesma imagem roda estável em `nyx-stg`. |
| **Erro na própria aplicação (crash de código)** | Os logs vêm **completamente vazios**, na instância atual e no `--previous`, nos dois pods (`05-logs-nyx-api.txt`). Um crash de aplicação deixa stack trace; um `SIGKILL` do OOM killer não deixa nada — o processo é encerrado sem chance de escrever. A ausência de log é, ela própria, coerente com OOM. |

---

## 4. Linha do tempo reconstruída (eventos, `07-events-nyx-prod.txt`)

| Quando | Fato |
|---|---|
| ~14 min antes da triagem | Namespace provisionado. `deployment/nyx-api` sobe o ReplicaSet `nyx-api-5ddc9d474c` com a tag de imagem `kube-news:v1`. |
| ~12 min antes | Essa primeira tentativa falha em **`ErrImagePull` / `ImagePullBackOff`**: `no match for platform in manifest` para `docker.io/fabricioveronez/kube-news:v1`. Os pods nunca chegam a rodar. |
| ~10 min antes | Alguém corrige a tag para `v1.0.0` → **revisão 2** do Deployment, novo ReplicaSet `nyx-api-6bb9d659c5`. A imagem agora baixa (`Successfully pulled ... in 8.87s`). |
| ~9 min antes | Container `api` é criado e iniciado — e morre em ~2 s com `OOMKilled`. |
| daí em diante | Ciclo `Created` → `Started` → `OOMKilled` → `BackOff` se repete. Contadores no momento da triagem: 5 e 6 restarts; 24 e 46 eventos `BackOff`. |

**Nota relevante para o pós-mortem:** o histórico de rollout (`11-rollout-history.txt`) mostra **apenas a revisão 2** — a revisão 1 não é mais recuperável (`unable to find the specified revision`), e o `CHANGE-CAUSE` está `<none>`. Ou seja, o deployment que entrou em produção é uma correção feita no calor do momento (só a tag de imagem foi ajustada), e **o limite de `24Mi` já estava errado desde a revisão 1** — ele só não tinha se manifestado antes porque o pod sequer conseguia baixar a imagem. Trocar a tag não introduziu o defeito: **revelou** um defeito que já estava no manifesto.

---

## 5. Causa raiz

> O manifesto de `deployment/nyx-api` em `nyx-prod` declara `resources.limits.memory: 24Mi` para um container que, na prática, precisa de **~34 MiB** (medido na mesma imagem em `nyx-stg`). Toda inicialização ultrapassa o limite do cgroup, o kernel emite SIGKILL, o kubelet registra `OOMKilled`/exit 137 e reinicia o container por `restartPolicy: Always`. Como a condição é determinística, o ciclo se repete indefinidamente e o pod permanece em `CrashLoopBackOff` — o que o cliente percebe como "a API fica reiniciando sozinha".

Causa contribuinte: `requests.memory: 16Mi` também está abaixo do consumo real, o que, além do OOM, torna o agendamento não representativo do consumo verdadeiro e dá ao pod (QoS `Burstable`) uma garantia irreal.

---

## 6. Recomendação (NÃO aplicada — requer aprovação do cliente)

Nenhuma alteração foi feita no cluster, conforme instrução do chamado. Para quando houver janela/autorização:

1. **Corrigir o limite de memória no manifesto** (no repositório do cliente, não via `kubectl edit`), dimensionando com folga sobre os ~34 MiB medidos — algo como `requests.memory: 64Mi` e `limits.memory: 128Mi`. O valor exato deve sair de observação sob carga real, não do consumo em repouso de staging: 34 MiB é o piso ocioso, não o pico.
2. **Alinhar `nyx-stg` ao que for definido para prod.** Hoje staging roda **sem nenhum limite**, o que é exatamente por isso que o defeito não foi pego antes de produção. Staging sem limites não testa a configuração de produção.
3. **Instalar `metrics-server` no cluster.** Sem ele não há `kubectl top`, e todo dimensionamento de recursos vira adivinhação — nesta triagem foi preciso ler cgroup via `exec` para obter um número.
4. **Adicionar alerta de `OOMKilled` / `CrashLoopBackOff`** por namespace. Este chamado chegou pelo cliente, não pelo monitoramento — essa é a falha de detecção a tratar no pós-mortem.
5. **Passar o manifesto pelo Padrão de Manifests da Metacortex** antes do próximo deploy. Além dos recursos, a revisão deve endereçar: `DB_PASSWORD` em texto puro como variável de ambiente (`Pg#123`) — deveria ser `Secret`; ausência de `livenessProbe`; ausência de labels padrão (`app.kubernetes.io/*`); e `CHANGE-CAUSE` não preenchido nos rollouts.

Dois cuidados na execução: não subir o limite sem corrigir o `requests` junto; e não usar `kubectl set resources` direto no cluster — o Deployment tem `last-applied-configuration` gerenciado via `kubectl apply`, e uma edição imperativa seria revertida no próximo apply do pipeline.

---

## 7. Comandos executados e saídas brutas

Todos os comandos foram executados via WSL com `KUBECONFIG=~/.kube/metacortex-lab.yaml`. Saídas completas salvas nesta mesma pasta:

| Arquivo | Comando |
|---|---|
| `01-get-pods.txt` | `kubectl get pods -n nyx-prod -o wide` |
| `02-get-all.txt` | `kubectl get all -n nyx-prod` |
| `03-describe-pod-fzv86.txt` | `kubectl describe pod nyx-api-6bb9d659c5-fzv86 -n nyx-prod` |
| `04-describe-pod-jcz42.txt` | `kubectl describe pod nyx-api-6bb9d659c5-jcz42 -n nyx-prod` |
| `05-logs-nyx-api.txt` | `kubectl logs <pod> -n nyx-prod` e `--previous`, nos dois pods |
| `06-deployment-nyx-api.yaml` | `kubectl get deployment nyx-api -n nyx-prod -o yaml` |
| `07-events-nyx-prod.txt` | `kubectl get events -n nyx-prod --sort-by=.lastTimestamp` |
| `08-describe-node.txt` | `kubectl describe node metacortex-lab-control-plane` |
| `09-limitrange-quota.txt` | `kubectl get limitrange,resourcequota -n nyx-prod` |
| `10-comparacao-nyx-stg.txt` | `kubectl get pods -n nyx-stg` + `resources` de stg e prod |
| `11-rollout-history.txt` | `kubectl rollout history deployment/nyx-api -n nyx-prod` |
| `12-memoria-real-stg.txt` | `kubectl top pods -n nyx-prod` + leitura de `memory.current` via `exec` em `nyx-stg` |
| `13-endpoints-nyx-prod.txt` | `kubectl get endpoints -n nyx-prod` |
| `14-logs-postgres-prod.txt` | `kubectl logs nyx-postgres-5c64c56fc4-5ckmm -n nyx-prod --tail=30` |

**Sobre a única escrita-adjacente:** o item 12 usou `kubectl exec` em dois pods de **`nyx-stg`** (não produção) apenas para `cat` de arquivo do cgroup. É leitura, não altera estado e não tocou em `nyx-prod`.
