# Evidência dos critérios de aceite

Tudo aqui foi gerado por `bash execucoes/capturar-evidencias.sh`, contra o cluster de laboratório
`kind-metacortex-lab` (kubeconfig `~/.kube/metacortex-lab.yaml`). Cada arquivo `.txt` começa com o
comando exato que o produziu. As telas em `telas/` foram capturadas com o Edge em modo headless
contra a aplicação rodando.

Os três kubeconfigs de cenário hostil ficam em `../ambiente/` e são fabricados — nenhum deles
aponta para cluster real.

| # | Critério | Evidência | Tela |
|---|---|---|---|
| 1 | Sobe contra o contexto corrente e mostra qual é, sem argumento de cluster | `criterio-01-contexto-corrente.txt` | `telas/tela-01-saudavel-helio-prod.png` |
| 2 | Lista namespaces, e selecionar um filtra os demais painéis | `criterio-02-namespaces-filtram.txt` | `telas/tela-01…` vs `telas/tela-02…` |
| 3 | Deployment sem réplica pronta aparece como `0/N`, não em branco | `criterio-03-deployment-zero-de-n.txt` | `telas/tela-02-crashloop-nyx-prod.png` |
| 4 | Pod em `CrashLoopBackOff` aparece com o motivo, não como "Running" | `criterio-04-crashloop-com-motivo.txt` | `telas/tela-02-crashloop-nyx-prod.png`, `telas/tela-04-imagepull-orion-stg.png` |
| 5 | Service sem endpoint aparece marcado, distinto de erro de leitura | `criterio-05-service-sem-endpoint.txt` | `telas/tela-03-sem-endpoint-nyx-stg.png` |
| 6 | Com o cluster fora do ar, a tela carrega e explica | `criterio-06-cluster-fora-do-ar.txt` | `telas/tela-05-cluster-fora-do-ar.png` |
| 7 | Com permissão negada para um recurso, os outros painéis continuam | `criterio-07-permissao-negada.txt` | `telas/tela-06-permissao-negada.png` |
| 8 | Busca por nome e filtro por namespace funcionam | `criterio-08-busca-e-filtro.txt` | `telas/tela-07-busca-por-nome.png`, `telas/tela-08-busca-sem-resultado.png` |
| 9 | Nenhum caminho de código alcança verbo de escrita | `criterio-09-invariante-somente-leitura.txt` | — (verificação mecânica) |

Extra, exigido por `specs/01-comportamento.md` mas não numerado entre os nove:

| Comportamento | Evidência |
|---|---|
| Credencial inválida tem mensagem **distinta** de cluster fora do ar | `extra-credencial-invalida.txt` |
| Namespace sem objetos é distinto de erro e de busca sem resultado | `criterio-08-busca-e-filtro.txt` (as três mensagens lado a lado) |

## Os quatro namespaces do laboratório

| Namespace | Estado | Qual critério cobre |
|---|---|---|
| `helio-prod` | saudável, 2 réplicas, endpoints populados | 1, 2, 5 (contraste) |
| `nyx-stg` | Service sem endpoint (selector divergente) | 5 |
| `nyx-prod` | `CrashLoopBackOff` por `OOMKilled` | 3, 4 |
| `orion-stg` | `ImagePullBackOff` | 4 |

## Os três cenários fabricados

| Cenário | Como foi fabricado | Arquivo |
|---|---|---|
| Cluster fora do ar | cópia do kubeconfig com `server` trocado para `https://127.0.0.1:59999` | `../ambiente/kubeconfig-cluster-morto.yaml` |
| Permissão negada em um recurso | ServiceAccount + ClusterRole (namespaces) + Role (pods, deployments, events) — **sem** services nem endpointslices | `../ambiente/rbac-leitura-restrita.yaml`, `../ambiente/kubeconfig-leitura-restrita.yaml` |
| Credencial inválida | mesmo endereço válido, token substituído por lixo | `../ambiente/kubeconfig-credencial-invalida.yaml` |

## Snapshots brutos

`snapshot-*.json` são as respostas de `GET /api/snapshot?ns=<N>` em cada cenário, salvas na
íntegra. São a prova mais direta do envelope por recurso: em
`snapshot-permissao-negada.json`, `pods.ok` é `true` e `services.ok` é `false` **no mesmo
documento** — que é o critério 7 em uma linha.
