# Laudo de triagem — nyx-stg responde 503 para chamadas externas

- **Chamado:** produto do cliente `nyx` em staging retorna **503** para quem chama de fora; o time afirma que a aplicação está de pé e saudável.
- **Namespace:** `nyx-stg`
- **Cluster:** `metacortex-lab` (kind, control-plane único)
- **Data da triagem:** 22/09/2026
- **Escopo:** somente leitura. **Nenhuma alteração foi aplicada no cluster.**

---

## 1. Veredito

**Causa raiz: o Service `nyx-api` não seleciona nenhum Pod, por divergência de rótulo (label/selector mismatch).**

| Objeto | Valor |
|---|---|
| `Service/nyx-api` → `spec.selector` | `app: nyx-api` (**com hífen**) |
| `Deployment/nyx-api` → `spec.template.metadata.labels` | `app: nyxapi` (**sem hífen**) |

Como nenhum Pod carrega o rótulo `app=nyx-api`, o controlador de endpoints não consegue popular o
Service. O `EndpointSlice` de `nyx-api` existe, porém com `endpoints: null` e `ports: null`.
Resultado: o Service é um destino válido no DNS e tem ClusterIP, mas **não tem backend algum** — e
qualquer proxy na frente dele (borda, gateway, apiserver proxy) só pode devolver **503 Service
Unavailable**.

O time está certo ao dizer que a aplicação está saudável — ela está. O problema não é a aplicação:
é o roteamento do Service até ela. Os dois fatos são compatíveis, e é exatamente essa combinação
que produz o sintoma "está de pé e ninguém chega nela".

---

## 2. Evidências

### 2.1 O Service está vazio

```
$ kubectl get endpoints -n nyx-stg
NAME                     ENDPOINTS          AGE
nyx-api                  <none>             14m      <-- vazio
nyx-postgres             10.244.0.12:5432   14m
```

```
$ kubectl describe service nyx-api -n nyx-stg
Selector:                 app=nyx-api
Type:                     ClusterIP
IP:                       10.96.16.24
Port:                     <unset>  80/TCP
TargetPort:               8080/TCP
Endpoints:                          <-- nenhum
```

O `EndpointSlice` correspondente (`nyx-api-57cfn`) confirma no objeto:

```yaml
addressType: IPv4
endpoints: null
ports: null
```

### 2.2 O rótulo dos Pods não bate com o selector

```
$ kubectl get pods -n nyx-stg --show-labels
nyx-api-69695bc4d6-4927k   1/1  Running  app=nyxapi,pod-template-hash=69695bc4d6
nyx-api-69695bc4d6-j882k   1/1  Running  app=nyxapi,pod-template-hash=69695bc4d6

$ kubectl get svc    nyx-api -n nyx-stg -o jsonpath="{.spec.selector}"
{"app":"nyx-api"}

$ kubectl get deploy nyx-api -n nyx-stg -o jsonpath="{.spec.template.metadata.labels}"
{"app":"nyxapi"}
```

Consulta direta pelos dois rótulos, que fecha o caso:

```
$ kubectl get pods -n nyx-stg -l app=nyx-api      # o que o Service procura
No resources found in nyx-stg namespace.

$ kubectl get pods -n nyx-stg -l app=nyxapi       # o que os Pods realmente têm
nyx-api-69695bc4d6-4927k   1/1   Running
nyx-api-69695bc4d6-j882k   1/1   Running
```

### 2.3 A aplicação está mesmo saudável (o time tem razão)

Chamando **através do Service** — reproduz o sintoma do chamado:

```
$ kubectl get --raw /api/v1/namespaces/nyx-stg/services/nyx-api:80/proxy/
Error from server (ServiceUnavailable): no endpoints available for service "nyx-api"
```

Chamando **direto no Pod**, mesma porta 8080 — responde normalmente:

```
$ kubectl get --raw /api/v1/namespaces/nyx-stg/pods/nyx-api-69695bc4d6-4927k:8080/proxy/
<!DOCTYPE html> ... <title>Kubenews</title> ...        (HTTP 200, página da aplicação)

$ .../proxy/ready    -> Ok
$ .../proxy/health   -> {"state":"up","machine":"nyx-api-69695bc4d6-4927k"}
```

O Deployment está `2/2 available`, `readyReplicas: 2`, condição `Available=True`; os Pods estão
`Ready: True` com `Restart Count: 0`. Nos logs aparecem apenas os probes do kubelet (`GET /health`,
`GET /ready`) — **nenhuma requisição de usuário chega aos Pods**, que é a assinatura de tráfego
morrendo antes do backend. (O único `GET /` nos logs é o teste desta triagem.)

---

## 3. Hipóteses descartadas

| Hipótese | Verificação | Conclusão |
|---|---|---|
| Aplicação caída / em crash | Pods `1/1 Running`, `Restart Count: 0`, `Ready: True` | Descartada |
| Readiness probe reprovando e tirando o Pod do Service | `/ready` responde `Ok`; Pods estão `Ready` | Descartada |
| `targetPort` errado no Service | Service `targetPort: 8080`; container `containerPort: 8080`; app responde em 8080 | Descartada |
| NetworkPolicy bloqueando a entrada | `kubectl get networkpolicy -A` → `No resources found` | Descartada |
| Banco indisponível derrubando a aplicação | `nyx-postgres` `1/1 Running` com endpoint `10.244.0.12:5432`; app consulta a tabela `Posts` com sucesso no log | Descartada |
| Rollout travado / imagem quebrada | Houve falha na revisão 1 (`kube-news:v1`, `no match for platform in manifest`), mas a revisão 2 (`v1.0.0`) concluiu e o ReplicaSet antigo está zerado | Descartada como causa atual |
| Ingress mal configurado | `kubectl get ingress -A` → `No resources found`; não há ingress controller no cluster | Não há objeto Ingress a culpar (ver ressalva) |

**Ressalva sobre a borda:** não existe Ingress nem ingress controller neste cluster, então não foi
possível inspecionar o componente que atende o cliente "de fora" — ele é externo ao cluster, ou
trata-se de `port-forward`/proxy. Isso **não muda o veredito**: o que quer que esteja na frente
aponta para o Service `nyx-api`, e esse Service não tem backend. O apiserver proxy reproduziu
literalmente o `ServiceUnavailable`. A falha está a montante da borda, e corrigi-la resolve o
sintoma independentemente de qual proxy esteja ali.

---

## 4. Correção recomendada (NÃO aplicada)

Um único rótulo precisa ser reconciliado. Há duas saídas, e a **primeira é a recomendada**:

**Opção A (recomendada) — corrigir o selector do Service para o rótulo que os Pods já têm.**
Não toca nos Pods, não gera rollout, não causa indisponibilidade adicional.

```yaml
# Service/nyx-api
spec:
  selector:
    app: nyxapi        # era: nyx-api
```

**Opção B — padronizar o rótulo da aplicação para `nyx-api`.** Mais correto a longo prazo (alinha o
rótulo ao nome do workload), porém mais caro: `spec.selector.matchLabels` de um Deployment é
**imutável**, então exige recriar o Deployment, não apenas editá-lo. Fazer só em janela de mudança.

Validação esperada após a correção:

```
kubectl get endpoints nyx-api -n nyx-stg
# deve listar 10.244.0.16:8080 e 10.244.0.17:8080

kubectl get --raw /api/v1/namespaces/nyx-stg/services/nyx-api:80/proxy/
# deve retornar a página da aplicação, não ServiceUnavailable
```

### Prevenção

O `Deployment/nyx-api` e o `Service/nyx-api` foram aplicados a partir de manifests que divergem
entre si (visível no `kubectl.kubernetes.io/last-applied-configuration` de ambos). Vale passar os
manifests do cliente `nyx` pelo Padrão de Manifests da casa antes do próximo apply — este é
exatamente o tipo de defeito que uma conferência de selector/label pega antes de chegar em staging.

---

## 5. Observações colaterais (fora do escopo deste chamado)

Encontradas durante a varredura do cluster; **não foram investigadas a fundo e não foram tocadas**:

- **`nyx-prod`**: os 2 Pods de `nyx-api` estão em `CrashLoopBackOff` (5 e 7 restarts). Mesmo cliente,
  em produção, com sintoma diferente do deste chamado. **Recomendo abrir chamado próprio, com
  prioridade — é produção.**
- **`orion-stg`**: os 3 Pods de `orion-web` estão em `ImagePullBackOff` há cerca de 14 minutos.

---

## 6. Arquivos de evidência

Todos na mesma pasta deste laudo:

| Arquivo | Conteúdo |
|---|---|
| `01-inventario-namespace.txt` | `get all -o wide`, endpoints, endpointslices, networkpolicy, configmap e eventos do namespace |
| `02-labels-selector.txt` | labels dos Pods, `describe`/`yaml` do Service, selector vs. labels, consultas por rótulo |
| `03-exposicao-externa.txt` | `get ingress -A`, namespaces, `get svc -A`, `get pods -A -o wide` |
| `04-deployment-nyx-api.txt` | `yaml` e `describe` completos do Deployment |
| `05-prova-conectividade.txt` | chamada via Service (503) vs. direto no Pod (200), `/ready`, `/health`, EndpointSlices |
| `06-descartes-e-logs.txt` | NetworkPolicies, logs dos Pods, `describe` de Pod |
