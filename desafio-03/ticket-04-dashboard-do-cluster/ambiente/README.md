# Ambiente do laboratório

O enunciado pede que o cluster tenha workload de verdade para o dashboard ter o que mostrar:
*"suba pelo menos dois dos três projetos — kube-news, fake-shop e encontros-tech — em namespaces
separados, usando os manifests que a sua skill gerou no Ticket 01"*.

## O que está de pé

| Namespace | Projeto | Estado | De onde vieram os manifests |
|---|---|---|---|
| `helio-prod` | encontros-tech | saudável, 2 réplicas, endpoints populados | **gerados pela skill do Ticket 01** |
| `nyx-stg` | kube-news | pods saudáveis, Service **sem endpoint** | ambiente do Ticket 02 |
| `nyx-prod` | kube-news | **CrashLoopBackOff** por OOMKilled | ambiente do Ticket 02 |
| `orion-stg` | fake-shop | **ImagePullBackOff** | ambiente do Ticket 02 |

Dois dos três projetos rodando, como pedido — e de quebra o cluster reúne, ao mesmo tempo, um
workload saudável, um em laço de reinício, um que nunca baixou a imagem e um Service que não
entrega tráfego. É exatamente a variedade que os critérios de aceite 3, 4 e 5 do dashboard exigem.

## Os manifests do encontros-tech

`encontros-tech-app.yaml` e `encontros-tech-schema.yaml` são cópias do que a skill
`padrao-manifests-metacortex` produziu no Ticket 01, em
`../../ticket-01-padrao-de-manifests/execucoes/skill-modo-escrita-encontros-tech/`.

**Única alteração:** a imagem, de `registry.metacortex.io/encontros-tech/web:v1` para
`fabricioveronez/encontros-tech:v26`. O registry da Metacortex é ficção do desafio; a troca para
rodar de verdade é sobreposição de ambiente, e o próprio `decisoes-conhecidas.md` da skill previu
isso ao dizer que o manifesto entregue aponta para o registry interno e a troca acontece fora do
arquivo versionado.

**O que a skill deixou de fora, e por quê**, está em `helio-prod-suporte.yaml`:

- o **Namespace**, porque a regra 1.2 do padrão diz que quem cria é o Construct
- o **Secret** `encontros-tech-db`, porque a regra 3.3 é `proibido` e segredo não é versionado
  junto do manifesto
- o **Postgres**, porque banco é infraestrutura e colide com a regra 3.2 — a decisão de mantê-lo
  fora do pacote do workload está registrada em `decisoes-conhecidas.md`

Ou seja: o pacote gerado pela skill não sobe sozinho, e isso é comportamento correto segundo o
padrão, não defeito. As três dependências externas estão declaradas aqui.

## Como subir do zero

```bash
kind create cluster --name metacortex-lab
export KUBECONFIG=~/.kube/metacortex-lab.yaml

# os três chamados do Ticket 02
kubectl apply -f ../../ticket-02-triagem-no-cluster/ambientes/

# o encontros-tech
kubectl apply -f helio-prod-suporte.yaml
sleep 20
kubectl apply -f .
```

## Validação de que os manifests da skill funcionam

Aplicados sem edição além da imagem, o resultado foi: Job `encontros-tech-schema` em `Completed`,
dois pods `encontros-tech-web` em `Running 1/1`, e `Endpoints` com dois endereços em `:8000`.

Isso fecha um laço entre os tickets: os manifests que a skill do Ticket 01 gerou a partir da
leitura do código do projeto sobem num cluster de verdade, com a migração de schema separada em
Job, `readOnlyRootFilesystem` ativo e `emptyDir` nos caminhos que a aplicação escreve.
