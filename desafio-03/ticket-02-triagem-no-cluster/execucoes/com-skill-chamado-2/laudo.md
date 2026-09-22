# Triagem — orion-stg

**Sintoma declarado:** a loja do cliente orion, em staging, parou depois de uma publicação; a tag
nova foi anunciada no release e o deploy foi aplicado, mas segundo o time o pod nunca trocou.

**Causa:** o Deployment `orion-web` declara a imagem `fabricioveronez/fake-shop:v1.14.2`, e essa tag
não existe no registry — o kubelet recebe `NotFound ... v1.14.2: not found` do Docker Hub e os 3
pods ficam em `ImagePullBackOff`, com o container nunca chegando a executar.

Evidência fora do cluster: a API do Docker Hub responde **HTTP 404** para
`repositories/fabricioveronez/fake-shop/tags/v1.14.2`, e o repositório tem 18 tags, nenhuma no
formato semver `x.y.z`: `latest`, `1`, `v1`, `v2`, `v6`, `v7`, `v8`, `v9`, `v11`, `v12`, `v13`,
`v14`, `v15`, `v16`, `v17`, `v19`, `v20`, `v26`.

## Como cheguei

| Camada | O que olhei | O que encontrei |
|---|---|---|
| Declaração | `kubectl get deploy orion-web -o wide` + imagem do template | 3 réplicas desejadas, imagem `fabricioveronez/fake-shop:v1.14.2`; condições `Available=False (MinimumReplicasUnavailable)` e `Progressing=False (ProgressDeadlineExceeded)` |
| Agendamento | `describe pod` → Conditions / Events | `PodScheduled=True`, evento `Successfully assigned ... metacortex-lab-control-plane`. Nó e agendamento descartados |
| Container | `status.containerStatuses[].state.waiting` (porta de entrada para "parou depois do deploy") | `reason: ImagePullBackOff`, `message: Back-off pulling image "fabricioveronez/fake-shop:v1.14.2"`, `restartCount: 0`, `Container ID` e `Image ID` vazios — o container nunca executou |
| Container (evento de origem) | eventos de Warning do pod | `Failed to pull image: rpc error: code = NotFound ... docker.io/fabricioveronez/fake-shop:v1.14.2: not found` — erro de resolução da referência, não de autenticação nem de timeout |
| Fora do cluster | API pública do Docker Hub (se a tag existe ou não é pergunta para o registry) | `HTTP 404: tag 'v1.14.2' not found`; as 18 tags publicadas seguem o padrão `vN`, nenhuma `1.14.2` |
| Aplicação (logs) | **não descida de propósito** | container em `ImagePullBackOff` nunca executou; não há log de aplicação a ler |
| Rede | Service / Endpoints | `orion-web` tem selector correto (`app=orion-web`, casa com os 3 pods), mas `Endpoints` com 0 endereços — consequência de nenhum pod ficar `Ready`, não causa |

### Um ajuste ao relato do chamado

O time descreveu "o pod nunca trocou", o que sugere a versão anterior ainda servindo. Não é o caso:
`kubectl rollout history` mostra **apenas a revisão 1** e existe **um único ReplicaSet** de web
(`orion-web-6788bb6d46`, o da tag quebrada). Não há pod de versão anterior no namespace, e o
`Endpoints` de `orion-web` está vazio — a loja não está servindo versão velha, está sem servir
nada. Isso muda a urgência: não há fallback em pé.

## O que estava saudável ao lado

- **`orion-postgres`**: `1/1` pronto, `Running`, 0 reinícios, imagem `postgres:16-alpine` baixada
  normalmente, `Endpoints` com 1 endereço (`10.244.0.8:5432`). Um pull bem-sucedido no mesmo nó e no
  mesmo namespace descarta de uma vez rede do nó, DNS do registry e saúde do nó.
- **Agendamento**: os 3 pods de web foram agendados no `metacortex-lab-control-plane` sem esperar por
  recurso; não é quota, afinidade nem falta de nó.
- **Recursos**: nenhum container declara `requests/limits` (QoS `BestEffort`) — não há `OOMKilled` nem
  qualquer terminação; `restartCount: 0` e `lastState` vazio confirmam que não é o padrão de
  CrashLoop.
- **Selector/rótulos**: `spec.selector` do Service (`app: orion-web`) bate exatamente com os rótulos
  do template do pod. O padrão "Service não entrega tráfego por rótulo divergente" está descartado —
  o `Endpoints` vazio aqui é sintoma, não causa.
- **Credencial de registry**: o erro é `NotFound`, não `unauthorized`, e o repositório é público. Não
  é `imagePullSecrets` faltando.

## Correção sugerida (não aplicada)

A decisão é de quem está de plantão. **Nada foi alterado no cluster.**

1. **Confirmar com quem cortou o release qual tag foi realmente publicada.** O repositório
   `fabricioveronez/fake-shop` nunca usou semver `x.y.z` — só `vN`, `latest` e `1`. A tag `v1.14.2`
   do release não corresponde a nada publicado: ou o release anunciou uma tag que não existe, ou a
   imagem não chegou a ser enviada ao registry. Não dá para deduzir daqui qual era a intenção
   (`v14`? `v1`? uma build nova ainda não publicada?) — isso é pergunta para o dono do release, não
   para a triagem.
2. **Se a imagem não foi publicada:** publicar a tag no registry e deixar o Deployment como está — o
   kubelet sai sozinho do back-off no próximo retry.
3. **Se a tag correta for outra:** apontar o Deployment para ela, por exemplo
   `kubectl set image deployment/orion-web web=fabricioveronez/fake-shop:<tag-correta> -n orion-stg`.
4. **Não há rollback possível neste namespace.** Como só existe a revisão 1, `kubectl rollout undo`
   não tem para onde voltar — mitigar por rollback não é opção aqui.

### Prevenção (fora do escopo desta triagem, para o post-mortem)

- Validar no pipeline que a tag existe no registry antes do `apply` (um `docker manifest inspect` ou
  `crane manifest` no passo de deploy já barraria).
- `ProgressDeadlineExceeded` no Deployment é um bom sinal de alerta: aqui ele apareceu e ninguém
  reagiu até o cliente reclamar.

---

*Triagem somente-leitura. Comandos executados em `00-comandos-executados.txt`; saídas brutas em
`01-snapshot.txt`, `02-declaracao-e-replicasets.txt`, `03-describe-pod-orion-web.txt` e
`04-registry-dockerhub-tags.txt`.*
