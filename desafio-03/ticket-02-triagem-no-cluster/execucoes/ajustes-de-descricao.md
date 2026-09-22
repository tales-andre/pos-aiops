# Ajustes de descrição feitos por causa da matriz de roteamento

A matriz testou as dez frases contra **apenas o frontmatter** das duas skills — que é o que o
agente realmente lê ao decidir qual carregar. Três problemas apareceram, e dois viraram correção.

## Problema 1 — colisão literal (frase 8)

A cláusula **"Service que não entrega tráfego" estava nas duas descrições**, quase palavra por
palavra. Enquanto as duas reivindicassem o mesmo sintoma, a frase *"o Service do nyx não está
entregando tráfego"* seria cara ou coroa — e é justamente o sintoma mais comum de selector errado,
o ponto onde os dois domínios se tocam de verdade.

Aqui a frase do usuário estava boa; as descrições é que estavam erradas. Foi erro de autoria meu,
por ter escrito as duas skills e repetido o mesmo exemplo nas duas.

**Correção:** o padrão de manifests larga o sintoma e fica com a correção no arquivo; a triagem
fica com o sintoma ao vivo.

## Problema 2 — fronteira temporal frágil (frases 3 e 8)

A triagem excluía o caso "antes de subir". Fronteira temporal é frágil porque depende de saber
quando o apply aconteceu. Trocada por uma fronteira **factual**: o objeto já existe no cluster e
emite sinal, ou não existe ainda?

## Problema 3 — frase mal formulada, sem conserto possível (frase 7)

*"esse manifesto não sobe no cluster"* descreve dois eventos opostos: apply **rejeitado** pela API
— nada existe no cluster, é problema de arquivo — ou apply aceito com o workload não ficando
pronto, que é triagem.

Nenhum ajuste de descrição resolve, porque **a informação não está na frase**. O comportamento
certo do agente é perguntar "o apply chegou a ser aceito?" antes de escolher. Registrado como
limite conhecido, não como defeito a corrigir.

## Problema 4 — assimetria de blindagem

A triagem tinha cláusula negativa; o padrão de manifests não tinha nenhuma, e ainda carregava uma
cláusula expansiva ("todo manifesto que entra num cluster do parque passa por essa revisão"). As
frases 9 e 10 — *"o que é um DaemonSet?"* e *"provisiona uma VM nova no Construct"* — não
disparavam, mas por acidente: ausência da palavra "manifesto" numa, e "VM" não ser objeto
Kubernetes na outra. Não por desenho.

**Correção:** cláusula negativa acrescentada ao padrão de manifests, cobrindo sintoma ao vivo,
infraestrutura fora do Kubernetes e pergunta conceitual.

---

## Texto antes e depois

### `padrao-manifests-metacortex`

**Antes:**
> Escreve e confere manifests Kubernetes contra o Padrão de Manifests da Metacortex — nomenclatura,
> rótulos, resiliência e segurança. Use sempre que alguém for criar, revisar ou corrigir manifesto
> Kubernetes de qualquer cliente do parque (Deployment, Service, Job, CronJob, ConfigMap, Secret),
> inclusive quando a pessoa apenas perguntar "esse manifesto está no padrão da casa?", pedir para
> empacotar uma aplicação para subir num cluster, **ou relatar Service que não entrega tráfego**.
> Vale mesmo quando o pedido não cita o padrão: todo manifesto que entra num cluster do parque
> passa por essa revisão, e é mais barato acertar antes do que ser barrado depois.

**Depois:**
> Escreve e confere **arquivos de manifesto** Kubernetes contra o Padrão de Manifests da Metacortex
> — nomenclatura, rótulos, resiliência e segurança. Use sempre que **houver um arquivo YAML em mãos
> ou a intenção de produzir um**: criar, revisar ou corrigir manifesto de qualquer cliente do parque
> (Deployment, Service, Job, CronJob, ConfigMap, Secret), inclusive quando a pessoa apenas perguntar
> "esse manifesto está no padrão da casa?", pedir para empacotar uma aplicação para subir num
> cluster, **quando o apply for rejeitado pela API**, ou quando for **corrigir no YAML um selector
> que não casa com os rótulos do pod depois que a triagem já apontou essa causa**. Vale mesmo quando
> o pedido não cita o padrão. **Não use para diagnosticar sintoma de workload que já está rodando,
> para infraestrutura fora do Kubernetes, nem para pergunta conceitual sem arquivo envolvido.**

### `triagem-de-cluster`

**Antes:**
> Método de triagem para workload que já está rodando num cluster Kubernetes do parque e parou de
> funcionar — pod que reinicia, deployment que não fica pronto, **Service que não entrega tráfego**,
> cliente relatando que está fora do ar. (...) **Não use para conferir ou escrever arquivo de
> manifesto antes de subir** — isso é outra skill.

**Depois:**
> Método de triagem para workload que **já existe no cluster** Kubernetes do parque e **está
> emitindo sinal de falha** — pod que reinicia, deployment que não fica pronto, **Service já
> aplicado que não entrega tráfego (sem endpoints, 502, timeout)**, cliente relatando que está fora
> do ar. Use sempre que **o objeto já existir no cluster e houver sintoma observado ao vivo** (...)
> **Não use quando o objeto ainda não existe no cluster — arquivo de manifesto a escrever, revisar,
> ou cujo apply foi rejeitado pela API — nem para pergunta conceitual sem incidente associado.**

---

## Resultado esperado depois do ajuste

| Frase | Antes | Depois |
|---|---|---|
| 1, 2 | triagem (alta) | triagem (alta) |
| 3 | triagem (média) | triagem (alta) |
| 4, 5, 6 | manifests (alta) | manifests (alta) |
| 7 | ambíguo | **ambíguo — por defeito da frase, não da descrição** |
| 8 | **ambas, empate** | triagem (alta) |
| 9, 10 | nenhuma, por acidente | nenhuma, por desenho |

Nove das dez frases passam a rotear com confiança alta. A décima continua ambígua, e está certo
que continue: a resposta correta ali é o agente perguntar, não adivinhar.
