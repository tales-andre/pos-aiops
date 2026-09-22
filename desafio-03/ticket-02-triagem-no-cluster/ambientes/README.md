# Ambientes de laboratório

Os três chamados do enunciado, reproduzidos num cluster local. Cada arquivo sobe o ambiente
inteiro do cliente — banco, aplicação e Service — com o defeito que gerou o chamado preservado.

```bash
kind create cluster --name metacortex-lab
kubectl apply -f .
# esperar alguns minutos e deixar o cluster nesse estado
```

| Arquivo | Namespace | Defeito plantado |
|---|---|---|
| `chamado-1-nyx-prod.yaml` | `nyx-prod` | `limits.memory: 24Mi` insuficiente → OOMKilled em laço |
| `chamado-2-orion-stg.yaml` | `orion-stg` | tag `v1.14.2` inexistente no registry → ImagePullBackOff |
| `chamado-3-nyx-stg.yaml` | `nyx-stg` | selector `app: nyx-api` contra rótulo do pod `app: nyxapi` → Service sem endpoint |

## Desvio do enunciado: a tag da imagem

Os chamados 1 e 3 usam `fabricioveronez/kube-news:v1.0.0`, e não `:v1` como o enunciado escreve.

**Motivo, verificado por execução:** a tag `v1` publica manifesto apenas para `arm64`. Numa
máquina x86_64 o pull falha com `no match for platform in manifest: not found`, e os dois pods
ficam em `ImagePullBackOff` — o que **mascara** os defeitos que esses dois chamados existem para
exercitar. O chamado 1 nunca chegaria a ser morto por memória, e o chamado 3 nunca teria pods
saudáveis para revelar o problema de selector.

A tag `v1.0.0` do mesmo repositório publica `amd64` e `arm64`, e é a única diferença introduzida.

O chamado 2 **mantém** `fabricioveronez/fake-shop:v1.14.2`, porque ali a falha de pull é o próprio
defeito.

Efeito colateral a conhecer: a troca de tag gerou uma revisão anterior nos Deployments de
`nyx-prod` e `nyx-stg`, cujos eventos de `ImagePullBackOff` ficam no histórico do namespace. Isso
acabou tornando o laboratório **mais** realista — é ruído de evento apontando para causa já
superada, exatamente o tipo de armadilha que a triagem precisa saber descartar.
