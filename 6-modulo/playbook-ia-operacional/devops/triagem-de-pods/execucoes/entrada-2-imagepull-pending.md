# Entrada 2 — pods que não sobem (ImagePullBackOff + Pending)

**Modelo:** Gemini 3.5 Flash (`gemini-3.5-flash`) via Google AI Studio · thinking level: Medium · grounding: off

## Entrada (`{{snapshot}}`)

```text
$ kubectl get pods -n sentinel-prod
NAME                            READY   STATUS             RESTARTS   AGE
sentinel-api-7d9c8b6f4-2xk9p    1/1     Running            0          6d
sentinel-api-7d9c8b6f4-zzp10    0/1     ImagePullBackOff   0          8m
sentinel-ingest-8f7a9c5b-4dkqm  0/1     Pending            0          8m
sentinel-scheduler-6c4d7f-nn8vx 1/1     Running            0          6d
$ kubectl describe pod sentinel-api-7d9c8b6f4-zzp10 -n sentinel-prod
    State:    Waiting
      Reason: ImagePullBackOff
    Image:    registry.aegis.io/sentinel-api:2.9.2
Events:
  Type     Reason   Age   From     Message
  ----     ------   ----  ----     -------
  Warning  Failed   7m    kubelet  Failed to pull image "registry.aegis.io/sentinel-api:2.9.2": manifest unknown
  Warning  Failed   7m    kubelet  Error: ErrImagePull
  Normal   BackOff  6m    kubelet  Back-off pulling image "registry.aegis.io/sentinel-api:2.9.2"
$ kubectl describe pod sentinel-ingest-8f7a9c5b-4dkqm -n sentinel-prod
    State:    Waiting
      Reason: Pending
    Requests: cpu: 2
Events:
  Type     Reason            Age   From               Message
  ----     ------            ----  ----               -------
  Warning  FailedScheduling  7m    default-scheduler  0/6 nodes are available: 6 Insufficient cpu
```

## Saída do modelo

🔺 RESUMO

O cluster enfrenta dois problemas distintos que impedem novos deploys/escalonamentos: uma falha de scheduling por falta de CPU afeta a ingestão de dados, e uma imagem inexistente travou a atualização da API. A API não está totalmente fora do ar porque uma réplica antiga (sentinel-api-7d9c8b6f4-2xk9p) segue operando normalmente.

Pods analisados: 4 · Problemáticos: 2 · Saudáveis: 2

🚨 PODS PROBLEMÁTICOS
[ALTO] sentinel-ingest-8f7a9c5b-4dkqm — sentinel-prod

Estado: Pending · 0/1 · 0 restarts
Sinais cruzados:

get: Travado em Pending há 8m.

events: FailedScheduling: 0/6 nodes are available: 6 Insufficient cpu.

logs: N/A (O container sequer foi alocado em um node).

Causa provável: O cluster atingiu o limite de capacidade de processamento alocável. O pod exige 2 CPUs (Requests: cpu: 2), mas nenhum dos 6 nodes atuais possui essa quantidade de CPU livre. O estado Pending é apenas o sintoma; a causa raiz é exaustão de recursos no cluster.

Ação agora:

Inspecionar a alocação atual para ver quem consome a CPU: kubectl describe nodes | grep -A 2 -e "^\s*CPU Requests"

Aumentar a capacidade do cluster (escalar o node pool) ou reduzir o request de CPU do deployment sentinel-ingest, caso os 2 CPUs estejam superestimados.

Se não resolver: Procurar por pods de baixa prioridade (ex: jobs de batch) que possam ser temporariamente removidos para liberar espaço para a ingestão.

[MÉDIO] sentinel-api-7d9c8b6f4-zzp10 — sentinel-prod

Estado: ImagePullBackOff · 0/1 · 0 restarts
Sinais cruzados:

get: Preso em ImagePullBackOff há 8m.

events: Failed to pull image "registry.aegis.io/sentinel-api:2.9.2": manifest unknown.

logs: N/A (O container não iniciou pois a imagem não foi baixada).

Causa provável: O kubelet consegue acessar o registry, mas a tag 2.9.2 da imagem não existe lá (manifest unknown). Não é um problema de credencial/rede, mas sim de release. Alguém aplicou um manifesto com a tag errada ou o pipeline de CI/CD falhou silenciosamente antes de fazer o push da imagem. A severidade é média pois a réplica antiga de 6 dias (2xk9p) continua Running, segurando o tráfego.

Ação agora:

Abortar a atualização travada com um rollback imediato: kubectl rollout undo deployment/sentinel-api -n sentinel-prod

Verificar no registry registry.aegis.io quais tags estão realmente disponíveis para sentinel-api.

Se não resolver: Investigar os logs do último pipeline de build/deploy da API para identificar por que a tag 2.9.2 não foi gerada.

🔍 PONTOS CEGOS

Não sabemos se sentinel-ingest tem outras réplicas rodando ou se a ingestão está 100% parada. Para descobrir: kubectl get deployment sentinel-ingest -n sentinel-prod

Logs não estão disponíveis nem aplicáveis no momento para os pods problemáticos, pois as falhas ocorrem antes da execução dos containers (Scheduling e Pull de imagem).

⚡ SE VOCÊ SÓ TEM 60 SEGUNDOS

Faça o rollback da API para limpar o estado de erro (kubectl rollout undo deployment/sentinel-api -n sentinel-prod) e adicione um node ao cluster (via autoscaler ou console da nuvem) para destravar a inicialização do sentinel-ingest.
