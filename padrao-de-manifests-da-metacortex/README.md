# Desafio — Padrão de Manifests da Metacortex

Entrega do desafio técnico da pós em AIOps e IA na Engenharia de Cloud.

O enunciado é a página de wiki do padrão de manifests da Metacortex e pede a URL de um repositório
público. Conforme confirmado pela tutoria, a tarefa é a de um dia de trabalho real: **você recebe o
documento de padrões da empresa e precisa entregar manifests que passem na revisão.**

## O que está entregue

| O quê | Onde |
|---|---|
| Os manifests | [`manifests/nyx-api.yaml`](./manifests/nyx-api.yaml) |
| A revisão passando | [`revisao/`](./revisao/) |

O workload é o **`nyx-api`**, componente do cliente `nyx` em produção — o mesmo que a wiki usa em
todos os exemplos dela. O pacote tem ServiceAccount, Deployment, Service e PodDisruptionBudget.

## A revisão

```
$ python3 conferir_manifests.py manifests/
Resumo: 0 barram, 0 pedem justificativa, 21 conformes.
código de retorno: 0

$ trivy config manifests/
Tests: 100 (SUCCESSES: 99, FAILURES: 1)
```

O único achado do Trivy é o `KSV-0125`, "untrusted registry", disparado contra
`registry.metacortex.io` — que é justamente o **único** registry que a regra 3.7 aceita. O critério
do Trivy é o oposto do da casa, então o achado é falso positivo por construção. Saída bruta em
[`revisao/02-trivy-config.txt`](./revisao/02-trivy-config.txt).

## Onde entra a IA

O enunciado não menciona IA, e a tutoria confirmou que isso é intencional: *"identificar onde ela
agrega valor e como aplicá-la é justamente a competência que queremos desenvolver"*.

A decisão que tomei foi **não usar IA para escrever o YAML.** Escrever um manifesto com um agente é
barato e não resolve o problema que a própria wiki declara logo na abertura: o padrão existe, está
escrito, e é longo demais para alguém abrir no meio de uma tarefa e conferir regra por regra. O
gargalo não é produzir manifesto — é a revisão.

Então usei IA para **empacotar o padrão numa skill do Claude Code** que escreve e confere manifests
sozinha. Ela está em
[`../desafio-03/ticket-01-padrao-de-manifests/skill/padrao-manifests-metacortex/`](../desafio-03/ticket-01-padrao-de-manifests/skill/padrao-manifests-metacortex/),
e os manifests desta entrega foram conferidos por ela.

O desenho dela saiu de uma triagem regra a regra do padrão, com quatro destinos:

| Destino | Regras | Por quê |
|---|---|---|
| `trivy config` | 2.1, 3.1, 3.2 | já existe catálogo pronto; reimplementar cria duas verdades sobre a mesma regra |
| script | 1.1, 1.2, 1.3, 1.4, 2.3, 2.4, 2.5, 3.3, 3.4, 3.5, 3.7 | decide-se lendo só o YAML, então é trabalho de computador |
| instrução | probe, caminhos graváveis, dono, componente, dimensionamento | exige abrir o código da aplicação; nenhum script alcança |
| fora | Bloco 4 inteiro | é glossário de Kubernetes, não regra conferível |

A fronteira com o Trivy foi estabelecida **rodando** a ferramenta sobre um manifesto real, não
supondo: 18 achados dele colapsam em 4 regras do padrão. A justificativa completa da linha está em
[`../desafio-03/ticket-01-padrao-de-manifests/curadoria.md`](../desafio-03/ticket-01-padrao-de-manifests/curadoria.md).

O ganho concreto: a revisão do padrão passou de leitura de uma wiki de quatro blocos para
`exit 0` ou `exit 1`, o que serve em pipeline de PR.

## As decisões que o padrão não responde

Três pontos onde a wiki não dá resposta e foi preciso abrir o código do `kube-news`:

**Para onde as probes apontam.** A regra 2.2 exige as duas apontando para endpoints que a aplicação
de fato expõe, e alerta contra apontar ambas para algo que consulta o banco. Em `src/system-life.js`
existem `/ready` e `/health` na porta 8080, e **nenhum dos dois toca o banco** — então a separação
que o padrão pede é possível aqui, o que não se sabia olhando só o YAML.

**O dimensionamento.** A regra de bolso pede limits de memória entre 1,5x e 2x o consumo observado.
O consumo medido foi **~34 MiB**, lido do cgroup do container em execução. `limits: 64Mi` é 1,9x.
É número medido, não chute — e vale dizer que a maioria dos manifests não tem esse dado.

**Os caminhos graváveis.** `readOnlyRootFilesystem: true` exige `emptyDir` no que a aplicação
escreve. O `kube-news` não escreve em disco — sem uso de `fs`, sem `/tmp`, log direto para stdout —
então nenhum volume foi declarado. Declarar um "por precaução" seria ruído.

## Ressalva que a revisão não pega e vale registrar

O `kube-news` chama `models.initDatabase()` no start (`src/server.js`), que executa
`sync({ alter: true })`. Com `replicas: 2` e `maxUnavailable: 0`, um rollout chega a três pods
executando alteração de schema no mesmo banco ao mesmo tempo.

Isso **não viola nenhuma regra do padrão** e passa na revisão. Mas é risco real, e o conserto não é
de manifesto: extrair para um Job não resolve, porque a chamada está no fluxo principal da
aplicação. É pedido de mudança para o time dono — registrado aqui porque revisão que só carimba o
que está na lista não presta serviço nenhum.

## Reproduzir

```bash
SKILL=../desafio-03/ticket-01-padrao-de-manifests/skill/padrao-manifests-metacortex
python3 $SKILL/scripts/conferir_manifests.py manifests/
trivy config manifests/
```
