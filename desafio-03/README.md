# Desafio 03 — Skills de DevOps e Projetos com SDD

Entrega do desafio técnico da pós-graduação em AIOps e IA na Engenharia de Cloud. O cenário é a
Metacortex, provedora de infraestrutura gerenciada: quatro tickets abertos na fila, os dois
primeiros pedindo skills que empacotem o método de operação da casa, os dois últimos pedindo
projetos entregues por inteiro.

Duas regras valem do começo ao fim: toda skill nasce de um fluxo que foi rodado, não de um chute,
e nenhum dos dois projetos começa pelo código — o arco é brainstorm, documentos de spec, ciclo do
OpenSpec, implementação e validação.

---

## [Ticket 01 — Padrão de manifests](./ticket-01-padrao-de-manifests/)

Skill que empacota o Padrão de Manifests da Metacortex, com dois modos: escrever um manifesto novo
já dentro do padrão, e conferir um que já existe.

| Entrega | Onde |
|---|---|
| A skill completa | [`skill/padrao-manifests-metacortex/`](./ticket-01-padrao-de-manifests/skill/padrao-manifests-metacortex/) |
| A origem dela | [`origem-da-skill.md`](./ticket-01-padrao-de-manifests/origem-da-skill.md) |
| Execução — modo escrita | [`execucoes/skill-modo-escrita-encontros-tech/`](./ticket-01-padrao-de-manifests/execucoes/skill-modo-escrita-encontros-tech/) |
| Execução — modo conferência | [`execucoes/skill-modo-conferencia-nyx-api/`](./ticket-01-padrao-de-manifests/execucoes/skill-modo-conferencia-nyx-api/) |
| A curadoria | [`curadoria.md`](./ticket-01-padrao-de-manifests/curadoria.md) |

Das 21 regras do padrão, 3 ficaram com o Trivy, 9 viraram script, 4 se partiram entre script e
instrução, 5 são só instrução, e o Bloco 4 ficou de fora por ser glossário. A fronteira com o
Trivy foi estabelecida **rodando** a ferramenta, não supondo.

## [Ticket 02 — Triagem no cluster](./ticket-02-triagem-no-cluster/)

Skill que fixa o método de triagem, sobre o alcance do `mcp-server-kubernetes` em modo de leitura.

| Entrega | Onde |
|---|---|
| A skill completa | [`skill/triagem-de-cluster/`](./ticket-02-triagem-no-cluster/skill/triagem-de-cluster/) |
| A origem dela | [`origem-da-skill.md`](./ticket-02-triagem-no-cluster/origem-da-skill.md) |
| Os três ambientes de laboratório | [`ambientes/`](./ticket-02-triagem-no-cluster/ambientes/) |
| Triagem dos três chamados | [`execucoes/com-skill-chamado-1..3/`](./ticket-02-triagem-no-cluster/execucoes/) |
| Matriz de roteamento e os ajustes que ela provocou | [`matriz-de-roteamento.md`](./ticket-02-triagem-no-cluster/execucoes/matriz-de-roteamento.md) · [`ajustes-de-descricao.md`](./ticket-02-triagem-no-cluster/execucoes/ajustes-de-descricao.md) |
| Comparação com e sem skill | [`comparacao-com-e-sem-skill.md`](./ticket-02-triagem-no-cluster/execucoes/comparacao-com-e-sem-skill.md) |
| A curadoria | [`curadoria.md`](./ticket-02-triagem-no-cluster/curadoria.md) |

**Causas encontradas:** OOMKilled contra `limits.memory: 24Mi`; tag `v1.14.2` inexistente no
registry; selector `app: nyx-api` contra rótulo `app: nyxapi`.

**O achado que mais importa:** a flag `ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS` remove **5 das 24**
ferramentas do MCP e mantém `apply`, `patch`, `scale` e `exec`. Não-destrutivo não é
somente-leitura, e a garantia teve que ser construída em três camadas.

## [Ticket 03 — Inventário de VM](./ticket-03-inventario-de-vm/)

Ferramenta que entra por SSH numa VM, levanta o retrato real do host e compara com o baseline
declarado do parque.

| Entrega | Onde |
|---|---|
| Documentos de spec | [`specs/`](./ticket-03-inventario-de-vm/specs/) |
| Artefatos do OpenSpec, arquivados | [`openspec/changes/archive/2026-09-22-add-inventario-drift-vm/`](./ticket-03-inventario-de-vm/openspec/changes/archive/) |
| Capacidade publicada | [`openspec/specs/inventario-drift-vm/`](./ticket-03-inventario-de-vm/openspec/specs/) |
| Código | [`src/inventario/`](./ticket-03-inventario-de-vm/src/inventario/) |
| Evidência dos 6 critérios de aceite | [`execucoes/`](./ticket-03-inventario-de-vm/execucoes/) |
| A curadoria | [`curadoria.md`](./ticket-03-inventario-de-vm/curadoria.md) |

Contra o host real: 6 conforme, 4 desvios, 1 `nao_verificado` — e o não verificado é o
`ssh.login_de_root`, porque `sshd -T` exige privilégio que o usuário da coleta não tem. É o
terceiro veredito pagando por si.

## [Ticket 04 — Dashboard do cluster](./ticket-04-dashboard-do-cluster/)

Aplicação local que lê o contexto corrente do kubeconfig e mostra o estado dos objetos do cluster.
Somente leitura.

| Entrega | Onde |
|---|---|
| Documentos de spec | [`specs/`](./ticket-04-dashboard-do-cluster/specs/) |
| Artefatos do OpenSpec, arquivados | [`openspec/changes/archive/2026-09-22-add-dashboard-cluster/`](./ticket-04-dashboard-do-cluster/openspec/changes/archive/) |
| Capacidades publicadas | [`openspec/specs/`](./ticket-04-dashboard-do-cluster/openspec/specs/) |
| Código | [`src/`](./ticket-04-dashboard-do-cluster/src/) |
| Evidência dos 9 critérios, com telas | [`execucoes/`](./ticket-04-dashboard-do-cluster/execucoes/) |
| O que aconteceu com as duas skills | [`skills-no-projeto.md`](./ticket-04-dashboard-do-cluster/skills-no-projeto.md) |
| A curadoria | [`curadoria.md`](./ticket-04-dashboard-do-cluster/curadoria.md) |

O ambiente de laboratório sobe o `encontros-tech` a partir dos **manifests que a skill do Ticket 01
gerou**, o que fecha o laço entre as quatro entregas.

---

## [Marketing pessoal](./marketing-pessoal.md)

As três teses do enunciado, cada uma com a prova que os tickets produziram e o ponteiro para o
artefato. O texto do post não está lá de propósito — a opinião é de quem assina.

## Como reproduzir o laboratório

```bash
kind create cluster --name metacortex-lab
export KUBECONFIG=~/.kube/metacortex-lab.yaml

kubectl apply -f ticket-02-triagem-no-cluster/ambientes/
kubectl apply -f ticket-04-dashboard-do-cluster/ambiente/helio-prod-suporte.yaml
sleep 20
kubectl apply -f ticket-04-dashboard-do-cluster/ambiente/
```

O [`.mcp.json`](../.mcp.json) na raiz do repositório registra o `mcp-server-kubernetes` em modo
não-destrutivo, apontado para esse kubeconfig de laboratório — nunca para um contexto de produção.
