---
nome: Hardening de NetworkPolicy — Sentinel
descricao: "Substitui um manifesto de Kubernetes barrado por permissivo demais por um conjunto de NetworkPolicy least-privilege (default-deny + allows específicos), sem inventar label, namespace ou porta fora do mapa de serviços."
versao: 1.0.0
tags: [devops, kubernetes, networkpolicy, security, zero-trust, sre]
inputs:
  - nome: MANIFESTO_PERMISSIVO
    descricao: Manifesto de NetworkPolicy barrado na revisão de segurança por ser permissivo demais.
  - nome: REGRAS_PADRAO
    descricao: Conjunto de regras de padrão (least privilege) que a nova versão precisa satisfazer.
  - nome: MAPA_SERVICOS
    descricao: Mapa de identificação dos serviços do cluster — namespace, label e porta de cada contraparte.
---

# Hardening de NetworkPolicy — Sentinel

## Objetivo

Transformar um manifesto de `NetworkPolicy` barrado por permissivo demais em um par de
políticas least-privilege — uma default-deny explícita e uma allow específica por fluxo
legítimo — sem que o modelo invente label, namespace ou porta fora do que o mapa de
serviços declara. O prompt embute um checklist de raciocínio interno (Chain-of-Thought)
que mapeia cada regra do padrão à contraparte exata antes de gerar o YAML, e é seguido
por um loop de verificação adversarial com critério de parada explícito.

## Quando usar

- Sempre que uma `NetworkPolicy` for barrada em revisão de segurança por padrões que
  disfarçam allow-all (`podSelector: {}`, `- {}` em ingress/egress, ausência de
  `namespaceSelector` em regra cross-namespace).
- Hardening de zero-trust entre microsserviços quando já existe um mapa de serviços
  confiável (namespace, label, porta) para basear os seletores.
- Não usar quando o mapa de serviços não tiver as portas necessárias e a política
  precisar ir para produção sem revisão humana das pendências — o prompt propositalmente
  não inventa porta ausente e devolve isso como pergunta em aberto.

## Parâmetros

| Parâmetro | Descrição |
|-----------|-----------|
| `{{MANIFESTO_PERMISSIVO}}` | Manifesto barrado na revisão por ser permissivo demais. |
| `{{REGRAS_PADRAO}}` | Regras de padrão (least privilege) que a nova versão precisa satisfazer. |
| `{{MAPA_SERVICOS}}` | Mapa de identificação dos serviços — namespace, label e porta de cada contraparte. |

## Exemplo de uso

Preencha os três parâmetros com o manifesto barrado, as regras de padrão do time de
segurança e o mapa de serviços do cluster. A saída são exatamente dois documentos YAML
(default-deny + allow), sem texto fora do bloco de código, terminando em um comentário
`# PERGUNTAS EM ABERTO PARA O REVISOR:` com toda porta/protocolo que não pôde ser
restringido por falta de dado no mapa de serviços. Execução completa (v1 → verificação →
v2 → verificação) sobre o manifesto do Sentinel em
[`execucoes/hardening-sentinel-prod.md`](./execucoes/hardening-sentinel-prod.md).

## Execução

Rodado sobre o manifesto do Sentinel (`sentinel-prod`), com **Claude Opus 5**
(`claude-opus-5`, via claude.ai, temperatura 0.1 — reprodutibilidade priorizada por ser
manifesto de segurança). Duas iterações:

- **v1** produziu `default-deny-all` + `allow-sentinel` com seletores sintaticamente
  corretos, mas a verificação adversarial encontrou 1 achado **CRÍTICO**: os `podSelector`
  de `from`/`to` não tinham `namespaceSelector`, e como todas as seis contrapartes (Relay,
  API gateway, Forge, Cerebro, DNS) vivem fora de `sentinel-prod`, a política — como
  escrita — não casava com pod nenhum e se comportava como default-deny total, quebrando
  produção. Achado **ALTO** adicional: DNS só liberava UDP/53, sem TCP de fallback.
- **v2** combinou `namespaceSelector` + `podSelector` no mesmo item de peer (AND, não OR)
  em toda regra cross-namespace, e adicionou TCP/53 à regra de DNS. A segunda rodada de
  verificação fechou os dois achados e não encontrou nenhum CRÍTICO/ALTO novo — critério de
  parada atingido. As duas pendências restantes (porta de ingress do Sentinel ausente no
  mapa de serviços; dependência do label automático `kubernetes.io/metadata.name`) ficaram
  registradas como perguntas em aberto, não corrigidas por suposição.

## Criação via meta-prompting

Prompt gerado com **Claude Opus 5** (via claude.ai) a partir do gerador de prompts por
framework (`gerador-prompts-frameworks.md`); a execução e as duas rodadas de verificação
também rodaram no Opus 5. O meta-prompt em si não é entregável.

## Curadoria

### Justificativa do framework

**R-T-F**, por critério 1 da decision tree do `prompt-lab-guia.md` — output rígido e
estruturado (aqui, literalmente código: manifesto Kubernetes) tem prioridade máxima na
ordem de escolha, e o checkpoint é exatamente esse caso: dois objetos YAML com estrutura
de campos fixa pelo próprio Kubernetes. O Role fixa a postura adversarial de quem já barra
manifesto permissivo; o Task isola a regra mais importante do exercício — nunca inventar
label, namespace ou porta fora do mapa de serviços; o Format é o que faz o prompt ser
reusável como item de playbook, porque define a forma exata (dois documentos, ordem,
convenção de nome, bloco de perguntas em aberto) que qualquer manifesto futuro vai seguir,
não só este.

Descartados:
- **C-A-R-E** — cairia bem se o objetivo fosse calibrar *estilo* de resposta com exemplos
  de I/O. Aqui a estrutura é ditada pela especificação do Kubernetes, não por um padrão
  estilístico a aprender por exemplo — few-shot seria redundante com a spec do próprio
  recurso.
- **R-I-S-E** — cobriria bem o *diagnóstico* do manifesto barrado, mas o pedido central não
  é diagnosticar, é produzir o artefato corrigido. Usar R-I-S-E deslocaria o peso do prompt
  para explicar o que estava errado em vez de entregar o YAML certo.
- **T-A-G / B-A-B** — não se aplicam: não há workflow sequencial a automatizar nem mudança
  de estado a narrar. É geração de artefato contra especificação.

### Justificativa da técnica complementar

- **Chain-of-Thought** — os cinco passos de raciocínio interno (mapear regra → contraparte,
  decidir namespaceSelector vs. podSelector, verificar porta, banir `{}`, confirmar
  default-deny) existem porque o erro mais caro em NetworkPolicy — `podSelector` sozinho não
  filtrando por namespace — é sutil o bastante para escapar de um prompt sem esse passo. E
  de fato escapou na v1 mesmo com o CoT presente, o que valida por que a segunda camada de
  defesa (o loop de verificação) não é opcional aqui.
- **Critério de Parada** — escolhido em vez de tratar a verificação como rodada única,
  porque o próprio checkpoint pede um processo (v1 → verificação → v2 → …) e não um prompt
  que se autodeclare pronto. O critério adotado — zero achados CRÍTICO ou ALTO, com achados
  MÉDIO restantes documentados como perguntas em aberto em vez de bloquear a entrega — é o
  que permite a v2 convergir em vez de gerar uma v3 desnecessária só para "ter mais uma
  rodada".
- **Por que não Few-shot:** um exemplo de NetworkPolicy corrigida ancoraria a estrutura de
  seletores do exemplo, que pode não bater com a topologia real do mapa de serviços
  recebido (cross-namespace aqui, mas nem sempre). Zero-shot com a spec do Kubernetes
  explícita nas REQUIREMENTS é mais seguro e mais transferível para o próximo manifesto que
  passar por este prompt.

### O achado que justifica o processo de verificação existir

O ponto central desta entrega não é o YAML final — é que a **v1, gerada pelo mesmo prompt
bem escrito, continha uma falha crítica que não é visível a olho nu**: sintaticamente
válida, com comentário parecendo correto, mas semanticamente equivalente a um default-deny
total, porque `podSelector` sem `namespaceSelector` não atravessa namespace. Uma
NetworkPolicy que não filtra nada e uma que bloqueia tudo têm exatamente essa aparência de
"parece certo" em revisão rápida — e é precisamente o tipo de erro que motiva barrar um
manifesto por outro motivo (permissivo demais). O checkpoint pede verificação e refino
porque o primeiro erro grave de um manifesto de rede raramente é óbvio como `- {}`; o mais
perigoso é o que parece restritivo e não é.

### Por que a v2 foi aceita sem v3

O critério de parada foi definido antes de rodar a primeira geração, não ajustado depois de
ver o resultado — isso evita o viés de "baixar a régua" para justificar parar cedo. As duas
pendências que sobraram na v2 (porta de ingress não especificada; dependência do label
automático de namespace) não são achados de segurança que o prompt devesse resolver
sozinho: são decisões que dependem de dado que não estava no mapa de serviços fornecido, e
inventar esse dado violaria a regra mais importante do prompt. Documentá-las como
perguntas em aberto — em vez de escondê-las dentro de uma regra — é o resultado correto,
não um resultado incompleto.

### Como validar antes de promover a item de playbook

- Rodar o prompt com um segundo manifesto barrado onde todas as contrapartes estão no
  **mesmo** namespace do Sentinel, e confirmar que o modelo não adiciona `namespaceSelector`
  desnecessário quando `podSelector` sozinho já é correto — o prompt não deve generalizar
  demais a partir deste caso.
- **Teste de porta ausente:** remover a porta 5432 do mapa de serviços e confirmar que a
  regra de Forge sai sem restrição de porta e a pendência aparece no bloco de perguntas em
  aberto — não que o modelo invente uma porta plausível.
- **Teste de armadilha:** fornecer um mapa de serviços com dois serviços de nomes parecidos
  em namespaces diferentes e confirmar que o modelo não funde os dois seletores por engano.
- **Teste de regressão do achado crítico:** validar com `kubectl` (`--dry-run=server` ou uma
  ferramenta de simulação de NetworkPolicy) que a v2, aplicada de fato, permite o tráfego
  Relay→Sentinel e nega qualquer outra origem — o teste que a v1 teria reprovado.

## Limitações conhecidas

- Assume o label automático de namespace `kubernetes.io/metadata.name` (padrão desde
  Kubernetes 1.21). Se algum namespace tiver esse label alterado manualmente, a regra
  correspondente para de casar — dependência registrada como pergunta em aberto, não
  validada automaticamente pelo prompt.
- NetworkPolicy opera em L3/L4: não inspeciona payload nem impede exfiltração via DNS
  tunneling ou abuso de uma porta já liberada por um peer legítimo.
- Seletores baseados em label pressupõem que o RBAC do cluster impede um workload não
  autorizado de assumir o label de um serviço legítimo (relabel attack) — a NetworkPolicy
  sozinha não é o controle contra isso.
- Não restringe porta quando o mapa de serviços não a declara; o resultado é ingress/egress
  mais aberto que o ideal, registrado como pergunta em aberto para decisão humana, não
  corrigido por suposição do modelo.
