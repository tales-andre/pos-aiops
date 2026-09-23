# pos-aiops

Entregas dos desafios técnicos da pós-graduação em **AIOps e Inteligência Artificial com
Engenharia de Cloud**.

Cada desafio do módulo *Desafios Técnicos - IAOps* tem uma pasta própria, e cada pasta é uma
entrega autocontida.

## Desafios

| # | Desafio | Pasta | O que é |
|---|---|---|---|
| 01 | Frameworks de Prompt Engineering | [`2-modulo/1-desafio-pratico/`](./2-modulo/1-desafio-pratico/) | oito questões resolvidas aplicando um framework de prompt por questão (R-T-F, C-A-R-E, R-I-S-E e outros) |
| 02 | Playbook de IA Operacional | [`6-modulo/playbook-ia-operacional/`](./6-modulo/playbook-ia-operacional/) | catálogo de prompts operacionais por domínio, com avaliação determinística em promptfoo e evidência de execução real |
| 03 | Padrão de Manifests da Metacortex | [`padrao-de-manifests-da-metacortex/`](./padrao-de-manifests-da-metacortex/) | manifests Kubernetes que passam na revisão do padrão da casa, e a skill que automatiza essa revisão |
| 04 | Skills de DevOps e Projetos com SDD | [`desafio-03/`](./desafio-03/) | quatro tickets: duas skills e dois projetos completos pelo arco de spec-driven development |

## Sobre os nomes das pastas

As duas primeiras entregas seguem a numeração do módulo da pós (`2-modulo`, `6-modulo`), que era a
convenção quando foram feitas. A quarta usa `desafio-03` porque é o nome que o próprio enunciado
dela desenha na seção "Como a entrega deve ser feita", e mexer nisso depois de entregue não vale o
risco.

A numeração da coluna `#` acima segue a **ordem em que os desafios aparecem na plataforma**. Ela
não bate com o `desafio-03` da última pasta, e essa divergência é do enunciado, não da organização
daqui.

## Ferramental compartilhado

- [`.mcp.json`](./.mcp.json) — registra o `mcp-server-kubernetes` em modo não-destrutivo, apontado
  para um kubeconfig de laboratório. Usado pela skill de triagem do desafio 04.
- [`.github/workflows/`](./.github/workflows/) — suíte de avaliação de prompts do desafio 02, em
  promptfoo, disparada por PR que toque aquela pasta.

## Skills produzidas

Dois dos desafios produziram skills do Claude Code, que funcionam fora do contexto da pós:

- [`padrao-manifests-metacortex`](./desafio-03/ticket-01-padrao-de-manifests/skill/padrao-manifests-metacortex/)
  — escreve e confere manifests Kubernetes contra um padrão de casa
- [`triagem-de-cluster`](./desafio-03/ticket-02-triagem-no-cluster/skill/triagem-de-cluster/)
  — método de triagem para workload rodando, somente leitura
