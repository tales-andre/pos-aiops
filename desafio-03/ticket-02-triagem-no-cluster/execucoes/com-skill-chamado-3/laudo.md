# Triagem — nyx-stg

**Sintoma declarado:** o produto do cliente nyx em staging responde 503 para quem chama de fora; o time afirma que a aplicação está de pé e saudável, e mesmo assim ninguém chega nela.

**Causa:** o Service `nyx-api` seleciona `app: nyx-api`, mas os pods do Deployment são rotulados `app: nyxapi` (sem o hífen) — nenhum pod casa com o selector, o objeto `Endpoints nyx-api` não tem o campo de endereços e o `EndpointSlice nyx-api-57cfn` traz `endpoints: null`, então o Service não tem para onde encaminhar e devolve 503 mesmo com os dois pods `Running 1/1`.

## Como cheguei

| Camada | O que olhei | O que encontrei |
|---|---|---|
| Declaração | `deployment/nyx-api`: réplicas, imagem, recursos, condições | 2/2 prontos, imagem `fabricioveronez/kube-news:v1.0.0`, `Available=True (MinimumReplicasAvailable)` e `Progressing=True (NewReplicaSetAvailable)`. A declaração está satisfeita — nada pendente aqui. |
| Agendamento | fase dos pods e nó | Os 3 pods do namespace estão `Running` no nó `metacortex-lab-control-plane`, com IP atribuído (10.244.0.16, .17, .12). Nenhum `Pending`: sem problema de nó, quota ou afinidade. |
| Container | `state`/`lastState`, reinícios, recursos | `container api pronto=True reinicios=0` nos dois pods. Sem `waiting`, sem `lastState.terminated`, sem OOMKill. A camada de container está inteira — é o caso em que o sintoma persiste com a fonte dizendo "está bem", então a resposta está em outro objeto, não mais fundo no mesmo. |
| Aplicação | não foi necessário | Com o container pronto e o sintoma sendo "ninguém chega", o log não é onde a causa está. Camada não aprofundada, por decisão de método. |
| Rede | `spec.selector` do Service × `spec.template.metadata.labels` do Deployment, `Endpoints`, `EndpointSlice` | **Aqui está a causa.** `service/nyx-api` → `selector: {app: nyx-api}`. `deployment/nyx-api` → `template.metadata.labels: {app: nyxapi}` e `selector.matchLabels: {app: nyxapi}`. Pods confirmados com `app=nyxapi`. Diferença de um hífen. |

### As três evidências que fecham a causa

1. `kubectl get endpoints -n nyx-stg` → `nyx-api   <none>`; no YAML, o campo `subsets` **não vem** (não vem vazio, não vem), exatamente a assinatura descrita na referência da skill.
2. `kubectl get endpointslice nyx-api-57cfn -o yaml` → `endpoints: null` e `ports: null`.
3. O próprio retrato do namespace: `NENHUM pod casa com o selector -> Service sem endpoint`, listando os três candidatos e seus rótulos.

### Onde o defeito nasceu

A anotação `kubectl.kubernetes.io/last-applied-configuration` do Service preserva o manifesto aplicado:

```json
{"spec":{"ports":[{"port":80,"targetPort":8080}],"selector":{"app":"nyx-api"}}}
```

O Service subiu assim desde a criação (12:01:45Z) e nunca teve endereço — o `last-change-trigger-time` do Endpoints é o mesmo instante da criação, sem mudança posterior. Não é regressão de um deploy recente: é divergência de metadado desde a origem. Deployment e Service são válidos isoladamente, por isso os dois foram aceitos sem erro e a revisão passou.

## O que estava saudável ao lado

- **Os pods do próprio `nyx-api`**: 2/2 prontos, 0 reinícios, sem `waiting` e sem `lastState.terminated`. O time está certo ao dizer que a aplicação está de pé — ela está. Isso descarta container, imagem e agendamento.
- **`nyx-postgres` no mesmo namespace**: `selector: {app: nyx-postgres}` casando com o pod rotulado `app=nyx-postgres`, `Endpoints` com 1 endereço (`10.244.0.12:5432`), `EndpointSlice` populado. É o contraste que aponta o dedo para o metadado: mesma API, mesmo nó, mesmo namespace, mesmo controlador — o que difere entre os dois Services é só a coerência do rótulo. Isso descarta rede do cluster, CNI e kube-proxy.
- **A porta do Service**: `targetPort: 8080` bate com o `containerPort: 8080` declarado no template. Não há um segundo defeito escondido na porta; corrigido o rótulo, o tráfego encaixa.
- **Eventos de `ImagePullBackOff` — descartados como causa.** Os eventos de Warning do namespace são todos de `nyx-api-75b85c8454-vhqps` e `-tf9zg`, pods de um ReplicaSet **anterior** (`nyx-api-75b85c8454`, imagem `:v1`, erro `no match for platform in manifest`). Esse ReplicaSet está hoje em `DESIRED 0 / CURRENT 0`, e o ReplicaSet ativo (`nyx-api-69695bc4d6`, imagem `:v1.0.0`) subiu normalmente. É rastro de um problema já superado por rollout, não o motivo do 503 de agora — e é a armadilha deste chamado: quem começa a triagem pelos eventos persegue uma falha de imagem que já não existe.

## Observação sobre "de fora"

Não há `Ingress` em nenhum namespace do cluster e nenhum Service do tipo `NodePort` ou `LoadBalancer`. O `nyx-api` é `ClusterIP`, alcançável só de dentro do cluster. Quem chama "de fora" chega por `port-forward` ou por um proxy externo apontando para esse ClusterIP; em qualquer desses caminhos, um Service sem endpoint produz exatamente o 503 relatado. Isso não altera a causa, mas vale registrar no chamado: a forma de exposição externa deste staging não está declarada no cluster.

## Correção sugerida (não aplicada)

O defeito é de um caractere, e há duas formas de fechar a divergência. **Alinhar o Service aos pods é a de menor risco**, porque não recria pod nenhum e o serviço passa a entregar tráfego na hora:

```bash
# opção A (recomendada): corrige o selector do Service para o rótulo que os pods já têm
kubectl patch svc nyx-api -n nyx-stg -p '{"spec":{"selector":{"app":"nyxapi"}}}'
```

A alternativa é corrigir o rótulo do Deployment para `app: nyx-api`. Ela deixa o namespace no padrão de nomenclatura da casa (`nyx-postgres`, `nyx-api` — com hífen), mas é **mais cara e mais arriscada**: `spec.selector` de um Deployment é imutável, então não dá para editar no lugar — exige recriar o Deployment, o que derruba os dois pods que hoje estão saudáveis. Se essa for a escolha, ela é janela de manutenção, não correção de plantão.

O mais importante: seja qual for a opção, **a fonte da verdade é o manifesto no repositório**. Corrigir só no cluster faz o 503 voltar no próximo `apply` do pipeline.

**A decisão e a aplicação são de quem está de plantão.** Esta triagem apenas leu o cluster; nenhuma escrita foi feita.

## Comandos executados (todos somente-leitura)

Saída bruta salva nesta mesma pasta:

| Arquivo | Conteúdo |
|---|---|
| `01-snapshot.txt` | `snapshot.py nyx-stg` — retrato completo do namespace pelo script da skill |
| `02-visao-geral.txt` | `get all -o wide`, `get ingress`, `get endpoints`, `get endpointslice`, `get pods --show-labels` |
| `03-service-vs-pod-labels.txt` | `get svc nyx-api -o yaml`, selector/labels/ports do Deployment, condições do Deployment, `EndpointSlice` e `Endpoints` em YAML |
| `04-entrada-externa.txt` | `get ingress -A`, busca por NodePort/LoadBalancer no cluster, `get ns`, `describe svc nyx-api` |
