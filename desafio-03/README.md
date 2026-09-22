# Desafio 03 — Skills de DevOps e Projetos com SDD

Entrega do desafio técnico da pós-graduação em AIOps e IA na Engenharia de Cloud. O cenário é a
Metacortex, provedora de infraestrutura gerenciada: quatro tickets abertos na fila, os dois
primeiros pedindo skills que empacotem o método de operação da casa, os dois últimos pedindo
projetos entregues por inteiro.

Duas regras valem do começo ao fim: toda skill nasce de um fluxo que foi rodado, não de um chute,
e nenhum dos dois projetos começa pelo código — o arco é brainstorm, documentos de spec, ciclo do
OpenSpec, implementação e validação.

## Tickets

### [Ticket 01 — Padrão de manifests](./ticket-01-padrao-de-manifests/) ✅

Skill que empacota o Padrão de Manifests da Metacortex, com dois modos: escrever um manifesto novo
já dentro do padrão, e conferir um que já existe.

| Entrega | Onde |
|---|---|
| A skill completa | [`skill/padrao-manifests-metacortex/`](./ticket-01-padrao-de-manifests/skill/padrao-manifests-metacortex/) |
| A origem dela | [`origem-da-skill.md`](./ticket-01-padrao-de-manifests/origem-da-skill.md) |
| Execução — modo escrita | [`execucoes/skill-modo-escrita-encontros-tech/`](./ticket-01-padrao-de-manifests/execucoes/skill-modo-escrita-encontros-tech/) |
| Execução — modo conferência | [`execucoes/skill-modo-conferencia-nyx-api/`](./ticket-01-padrao-de-manifests/execucoes/skill-modo-conferencia-nyx-api/) |
| A curadoria | [`curadoria.md`](./ticket-01-padrao-de-manifests/curadoria.md) |

### Ticket 02 — Triagem no cluster

Skill de triagem sobre o alcance do `mcp-server-kubernetes`, rodada nos três chamados reproduzidos
em laboratório, mais a matriz de roteamento entre as duas skills e a medição com e sem skill.

### Ticket 03 — Inventário de VM

Ferramenta que entra por SSH numa VM, levanta o retrato real do host e compara com o baseline
declarado do parque, com saída em JSON e Markdown.

### Ticket 04 — Dashboard do cluster

Aplicação local que lê o contexto corrente do kubeconfig e mostra o estado dos objetos do cluster,
somente leitura.
