# Matriz de roteamento — `padrao-manifests-metacortex` x `triagem-de-cluster`

**Data:** 22/09/2026
**Método:** roteamento decidido lendo **apenas o frontmatter YAML** (`name` + `description`) das duas
skills. Os corpos (`SKILL.md` abaixo do frontmatter) **não** foram lidos, de propósito: o agente
escolhe qual skill carregar tendo só a descrição em contexto, então é a descrição que está sob teste.

Skills avaliadas:
- `C:\Users\tales\.claude\skills\padrao-manifests-metacortex\SKILL.md`
- `C:\Users\tales\.claude\skills\triagem-de-cluster\SKILL.md`

---

## Matriz

| # | Frase | Skill escolhida | Trecho da descrição que decidiu | Confiança |
|---|---|---|---|---|
| 1 | "o pod do nyx-prod não sobe" | `triagem-de-cluster` | `frase solta do tipo "o pod do nyx-prod não sobe"` — exemplo **literal** na descrição | Alta |
| 2 | "por que esse deployment está 0/3" | `triagem-de-cluster` | `ou "por que esse deployment está 0/3"` — exemplo **literal** na descrição | Alta |
| 3 | "o service do nyx-stg não tem endpoint" | `triagem-de-cluster` | `sintoma observado num cluster ao vivo` + `Service que não entrega tráfego`; o nome de ambiente (`nyx-stg`) indica recurso já existente, não arquivo | Média |
| 4 | "revisa esse deployment antes de eu subir" | `padrao-manifests-metacortex` | `Use sempre que alguém for criar, revisar ou corrigir manifesto Kubernetes` + a exclusão explícita na outra skill: `Não use para conferir ou escrever arquivo de manifesto antes de subir — isso é outra skill` | Alta |
| 5 | "esse manifesto está no padrão da casa?" | `padrao-manifests-metacortex` | `inclusive quando a pessoa apenas perguntar "esse manifesto está no padrão da casa?"` — exemplo **literal** | Alta |
| 6 | "cria um Deployment novo do zero pra mim" | `padrao-manifests-metacortex` | `Escreve e confere manifests Kubernetes` + `alguém for criar (...) (Deployment, Service, Job, CronJob, ConfigMap, Secret)` | Alta |
| 7 | "esse manifesto não sobe no cluster" | `ambiguo` | Colide: `manifesto` puxa para `criar, revisar ou corrigir manifesto`; `não sobe no cluster` puxa para `sintoma observado num cluster ao vivo`. A exclusão `antes de subir` não cobre "durante o subir" | Baixa |
| 8 | "o Service do nyx não está entregando tráfego" | `ambas` | As **duas** descrições reivindicam a mesma cláusula: PMM `ou relatar Service que não entrega tráfego`; TDC `Service que não entrega tráfego` | Baixa (para desempatar) / Alta (de que ambas casam) |
| 9 | "o que é um DaemonSet?" | `nenhuma` | Nenhuma descrição cobre pergunta conceitual: PMM exige `manifesto` em mãos, TDC exige `sintoma observado num cluster ao vivo`. `DaemonSet` nem consta da lista de objetos do PMM | Alta |
| 10 | "provisiona uma VM nova no Construct pro cliente orion" | `nenhuma` | Fora do domínio Kubernetes das duas: PMM fala de `manifests Kubernetes`, TDC de `workload que já está rodando num cluster Kubernetes` | Alta |

**Placar:** 3 `triagem-de-cluster` + 3 `padrao-manifests-metacortex` + 1 `ambas` + 1 `ambiguo` + 2 `nenhuma`.

---

## 1. Frases ambíguas

### #7 — "esse manifesto não sobe no cluster" (a ambiguidade mais séria)

A frase mistura os dois vocabulários de gatilho numa sentença só: o substantivo (`manifesto`) é o
gatilho canônico do `padrao-manifests-metacortex`, e o predicado (`não sobe no cluster`) é o gatilho
canônico da `triagem-de-cluster` — inclusive o verbo "não sobe" é o mesmo do exemplo literal da frase #1.

**O que falta para desempatar:** saber **em que ponto do ciclo a coisa quebrou**. Há dois mundos
distintos escondidos na mesma frase:

- **O `kubectl apply` foi rejeitado** (erro de schema, campo inválido, admission/policy barrando,
  CRD ausente). Nada chegou a existir no cluster — não há o que triar. É `padrao-manifests-metacortex`.
- **O `apply` foi aceito, mas o workload não fica pronto** (pod em `CrashLoopBackOff`,
  `ImagePullBackOff`, deployment travado em 0/N). O objeto existe e emite sinal. É `triagem-de-cluster`.

A descrição da `triagem-de-cluster` só exclui o caso `antes de subir`. A frase #7 descreve o caso
**"durante o subir"**, que nenhuma das duas descrições nomeia — é um buraco de cobertura, não um empate
entre duas coberturas.

### #8 — "o Service do nyx não está entregando tráfego" (ambiguidade na descrição, não na frase)

Aqui a frase está bem formulada: nomeia um recurso concreto e existente (`o Service do nyx`) e um
comportamento observado (`não está entregando tráfego`). Pela regra geral, é sintoma ao vivo →
triagem. **O problema é que as duas descrições contêm a cláusula quase verbatim:**

- PMM: `(...) pedir para empacotar uma aplicação para subir num cluster, ou relatar Service que não entrega tráfego.`
- TDC: `(...) deployment que não fica pronto, Service que não entrega tráfego, cliente relatando que está fora do ar.`

**O que falta:** nada na frase. Falta nas descrições — uma das duas tem que abrir mão da cláusula, ou
qualificá-la (ver seção 3). Enquanto as duas a reivindicarem, essa frase é um coin flip permanente,
e é o defeito de autoria mais caro dos dez casos: a colisão está justamente no sintoma mais comum de
selector/rótulo errado, que é o ponto onde os dois domínios de fato se tocam.

### #3 — "o service do nyx-stg não tem endpoint" (ambiguidade leve, resolvida por contexto)

Mesma colisão de #8, mas a frase traz um desempate fraco e um forte:

- Fraco: `não tem endpoint` é linguagem de leitura de cluster (`kubectl get endpoints`), não de revisão
  de arquivo.
- Forte: `nyx-stg` nomeia um **ambiente**, o que pressupõe recurso já aplicado.

Ainda assim a confiança é **média**, não alta, porque a causa-raiz quase certa (selector que não casa
com os rótulos do pod) cai no território que o PMM declara seu: `nomenclatura, rótulos`. A rigor, o
fluxo correto é triagem primeiro (achar a causa) e PMM depois (corrigir o YAML) — sequência que
nenhuma das duas descrições explicita.

---

## 2. Fora de escopo

São **#9** ("o que é um DaemonSet?") e **#10** ("provisiona uma VM nova no Construct pro cliente orion").

### As descrições seguram bem? Parcialmente. Por acidente, não por desenho.

**#9 — pergunta conceitual.** Não dispara por três razões, todas indiretas:
- PMM está ancorado num artefato (`manifesto`) que a frase não menciona nem pressupõe.
- TDC exige `sintoma observado num cluster ao vivo` — não há sintoma.
- `DaemonSet` não está na lista de objetos do PMM (`Deployment, Service, Job, CronJob, ConfigMap, Secret`).

O risco residual está na frase final do PMM: `Vale mesmo quando o pedido não cita o padrão: todo
manifesto que entra num cluster do parque passa por essa revisão`. É uma cláusula de expansão
deliberada, escrita para vencer empates a favor do PMM. Numa variante um pouco mais carregada da
frase — "como eu escrevo um DaemonSet?" — essa cláusula provavelmente puxaria o PMM, e aí seria
acerto. Para a pergunta puramente conceitual, o que salva é a ausência da palavra "manifesto", o que é
frágil demais para se apoiar. **Nenhuma das duas descrições tem cláusula negativa para pergunta
conceitual/didática.**

**#10 — provisionamento fora de Kubernetes.** Não dispara porque as duas descrições dizem "Kubernetes"
explicitamente e "VM" não é objeto Kubernetes. Mas há duas armadilhas de vocabulário compartilhado:
- `pro cliente orion` ecoa `de qualquer cliente do parque` (PMM) e `cliente relatando que está fora do
  ar` (TDC).
- `provisiona (...) nova` ecoa `criar` e `pedir para empacotar uma aplicação para subir num cluster` (PMM).

Se "Construct" for um cluster (e não um provedor de VM), a frase fica bem mais perigosa. Do jeito que
está, **o PMM é a fonte de falso positivo mais provável das duas**: ele tem a cláusula expansiva e
**zero** cláusulas negativas. A `triagem-de-cluster` tem uma (`Não use para conferir ou escrever
arquivo de manifesto antes de subir`) e, por isso, é a mais bem comportada do par.

---

## 3. Sugestões de ajuste nas descrições

### 3.1 `padrao-manifests-metacortex`

**Ajuste A — desfazer a colisão do Service (resolve #8, firma #3). Prioridade máxima.**

- Texto atual: `(...) pedir para empacotar uma aplicação para subir num cluster, ou relatar Service que não entrega tráfego.`
- Substituto proposto: `(...) pedir para empacotar uma aplicação para subir num cluster, ou corrigir no YAML um Service cujo selector não casa com os rótulos do pod, depois que a triagem já apontou essa causa.`

Racional: o PMM não perde o caso (continua dono da correção), mas para de reivindicar o **sintoma**.
A palavra que decide passa a ser "corrigir no YAML", não "Service".

**Ajuste B — dar ao PMM a cláusula negativa que ele não tem (resolve #9 e #10).**

- Acrescentar ao final: `Não use quando o pedido for um sintoma observado num cluster ao vivo (pod reiniciando, deployment 0/N, Service já no ar sem endpoints) — isso é triagem-de-cluster. Também não use para infraestrutura fora de Kubernetes (VM, rede, DNS, pipeline) nem para perguntas conceituais sobre objetos Kubernetes.`

**Ajuste C — escopar a cláusula expansiva (reduz falso positivo sem perder a intenção original).**

- Texto atual: `Vale mesmo quando o pedido não cita o padrão: todo manifesto que entra num cluster do parque passa por essa revisão, e é mais barato acertar antes do que ser barrado depois.`
- Substituto proposto: `Vale mesmo quando o pedido não cita o padrão, desde que exista um arquivo YAML em mãos ou a intenção de produzir um: todo manifesto que entra num cluster do parque passa por essa revisão, e é mais barato acertar antes do que ser barrado depois.`

Racional: preserva o comportamento desejado (vencer empate quando **há manifesto**) e retira a leitura
"qualquer coisa que toque um cluster do parque é comigo".

### 3.2 `triagem-de-cluster`

**Ajuste D — transformar a exclusão em desempate operacional (ataca #7).**

- Texto atual: `Não use para conferir ou escrever arquivo de manifesto antes de subir — isso é outra skill.`
- Substituto proposto: `Não use quando houver um arquivo de manifesto em mãos para conferir, corrigir ou escrever antes do apply, nem quando o próprio apply for rejeitado pelo servidor (erro de schema, campo inválido, admission barrando) — nesses dois casos a skill é padrao-manifests-metacortex. O gatilho daqui é o objeto já existir no cluster e emitir sinal.`

Racional: fecha o buraco "durante o subir". Hoje a fronteira é temporal (`antes de subir`); passa a ser
factual (**o objeto existe no cluster?**), que é verificável.

**Ajuste E — qualificar o Service para casar com o Ajuste A.**

- Texto atual: `(...) deployment que não fica pronto, Service que não entrega tráfego, cliente relatando que está fora do ar.`
- Substituto proposto: `(...) deployment que não fica pronto, Service já aplicado que não entrega tráfego (sem endpoints, 502, timeout), cliente relatando que está fora do ar.`

**Ajuste F — excluir pergunta conceitual (simétrico ao Ajuste B).**

- Acrescentar: `Não use para pergunta conceitual sobre o que um objeto Kubernetes é ou faz, quando não houver incidente associado.`

### 3.3 Onde o problema é a frase, e nenhum ajuste de descrição resolve

Ser honesto sobre isso importa mais do que empilhar cláusula:

- **#7 "esse manifesto não sobe no cluster" — a frase é que está mal formulada.** "Não sobe" descreve
  dois eventos tecnicamente opostos (apply rejeitado x workload não pronto) e o falante não diz qual.
  O Ajuste D dá um **default defensável** (se o objeto existe → triagem; se o apply foi rejeitado →
  PMM), mas não elimina a ambiguidade: para saber qual é, é preciso perguntar ou olhar. O comportamento
  correto do agente aqui **não é escolher com confiança**, é fazer uma pergunta de uma linha
  ("o `kubectl apply` chegou a ser aceito?") ou inspecionar antes de carregar skill. Nenhuma redação de
  descrição compra essa informação, porque a informação não está na frase.
- **#6 "cria um Deployment novo do zero pra mim" — roteamento claro, pedido incompleto.** A descrição
  acerta sozinha (alta confiança), mas falta imagem, porta, namespace, cliente e recursos. É lacuna de
  **execução**, não de roteamento; não deve virar cláusula de descrição.
- **#9 e #10 são bons controles negativos** e devem permanecer como estão no conjunto de teste. Se
  depois dos Ajustes B e F alguma das duas ainda disparar neles, o defeito é da cláusula expansiva do
  PMM, não da frase.
- **#8 é o inverso de #7: frase boa, descrições ruins.** Vale registrar a distinção porque o reflexo
  natural ao ver um empate é reescrever a frase de teste — e aqui isso mascararia o bug real, que é a
  duplicação verbatim da cláusula do Service.

### 3.4 Resumo dos ajustes

| Ajuste | Skill | Resolve | Prioridade |
|---|---|---|---|
| A — tirar o sintoma "Service não entrega tráfego" do PMM | PMM | #8, firma #3 | Alta |
| B — cláusula negativa (sintoma ao vivo, não-K8s, conceitual) | PMM | #9, #10 | Alta |
| C — escopar "vale mesmo quando o pedido não cita o padrão" | PMM | falso positivo geral | Média |
| D — fronteira factual "o objeto existe no cluster?" | TDC | #7 (parcial) | Alta |
| E — qualificar Service como "já aplicado" | TDC | #8 | Alta |
| F — excluir pergunta conceitual | TDC | #9 | Média |

Depois de A–F, a expectativa é: #1, #2, #3 → triagem; #4, #5, #6 → PMM; #8 → triagem com confiança
alta; #9, #10 → nenhuma; **#7 continua ambíguo por defeito da frase**, com default para triagem quando
o objeto já existe no cluster.
