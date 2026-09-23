# As duas skills durante este ticket

Relato honesto do que aconteceu com `padrao-manifests-metacortex` e `triagem-de-cluster` enquanto
eu construía o dashboard.

## Resumo curto

**Nenhuma das duas disparou sozinha.** Uma eu chamei na mão e ela encaixou pela metade. A outra eu
nunca chamei — e depois descobri que o material de referência dela era o documento mais relevante
da máquina para este ticket.

| Skill | Disparou sozinha? | Chamei na mão? | Veredito |
|---|---|---|---|
| `padrao-manifests-metacortex` | não | sim, uma vez | encaixou no tipo de artefato, não no tipo de objeto |
| `triagem-de-cluster` | não | não | ausência correta pela regra dela, cara pelo conteúdo |

---

## `padrao-manifests-metacortex`

### Não disparou sozinha, e o gatilho existia

Escrevi um manifesto Kubernetes neste ticket: `ambiente/rbac-leitura-restrita.yaml`
(ServiceAccount + ClusterRole + ClusterRoleBinding + Role + RoleBinding), para fabricar o contexto
de leitura restrita do critério 7. A descrição da skill diz que ela vale "sempre que houver um
arquivo YAML em mãos ou **a intenção de produzir um**". Eu tinha exatamente essa intenção, e nada
aconteceu. Chamei manualmente.

### Chamada na mão: encaixe parcial, e dá para dizer onde a costura abriu

O que serviu:

- `scripts/conferir_manifests.py` rodou sobre o arquivo e devolveu **0 barram, 0 pedem
  justificativa, 13 conformes**. Como portão mecânico foi útil de verdade: confirmou nomenclatura
  em kebab-case (1.1) e os quatro rótulos (1.3) em todos os cinco objetos, que eu havia aplicado
  de memória e poderia ter errado em um deles sem perceber.
- A regra 1.5 (anotação de dono) me fez acrescentar `metacortex.io/owner` e uma anotação de
  propósito explicando que aquilo é credencial de laboratório. Num cluster compartilhado, uma SA
  com nome genérico e sem dono é exatamente o objeto que ninguém sabe se pode apagar.

O que não tinha objeto:

- Todo o Bloco 2 (requests/limits, readiness/liveness, PDB, SIGTERM) e todo o Bloco 3
  (`readOnlyRootFilesystem`, contexto de segurança, registry) são regras **de container**. Um
  `Role` não tem container. Isso é mais da metade do corpo da skill.
- O passo 2 do modo conferência — "descubra qual aplicação é, abra o repositório da aplicação,
  responda: em que porta escuta, tem endpoint de saúde, que caminhos escreve em disco" — não tem
  resposta possível. Não há aplicação; há uma credencial.
- O aviso sobre `trivy config` e o falso-positivo `KSV-0125` não se aplicou, porque não há imagem.

**Por que isso acontece, e não é bem um defeito.** A própria descrição da skill enumera os tipos
que ela cobre: "Deployment, Service, Job, CronJob, ConfigMap, Secret". RBAC não está na lista.
Então ela **não disparar** em RBAC está coerente com o que ela promete — e a chamada manual foi
minha decisão de forçar um encaixe parcial, não um erro dela. Fica o registro de que o par
descrição/conteúdo diverge num ponto: a descrição também diz "arquivo YAML em mãos", que é bem mais
largo do que os seis tipos que ela realmente sabe conferir.

### O que mais pesa: o escopo dela quase não tocou este ticket

Os manifestos de workload do laboratório (`ambiente/encontros-tech-app.yaml`,
`encontros-tech-schema.yaml`, `helio-prod-suporte.yaml`) já estavam escritos e aplicados quando
comecei, e a instrução era não mexer. Ou seja: o único manifesto que este ticket produziu foi
justamente o tipo que a skill não cobre. Ela ficou de fora não por falha de roteamento, mas porque
o ticket é de aplicação, não de empacotamento.

---

## `triagem-de-cluster`

### Não disparou, e eu também não a chamei

Passei o ticket inteiro olhando para os sintomas que são os exemplos literais da descrição dela:
`nyx-prod` em `CrashLoopBackOff`, `orion-stg` em `ImagePullBackOff`, `nyx-stg` com Service sem
endpoint. A descrição cita, entre aspas, "o pod do nyx-prod não sobe". Mesmo assim ela não
disparou, e eu concordo que **não devia** ter disparado:

- A skill exige "sintoma observado ao vivo" e "incidente associado". Aqui não havia incidente. Os
  quatro namespaces são **fixtures** — foram postos em falha de propósito, e o briefing já me
  entregou as causas prontas (OOMKilled, selector divergente, imagem inexistente).
- A skill "para quando encontra a causa". Eu não queria encontrar causa nenhuma; queria verificar
  se a minha tela *renderiza* aquelas causas. É o objeto inverso.

Então a regra de roteamento dela funcionou. O problema é o que isso custou.

### O que descobri depois, e é o achado mais desconfortável deste relatório

Fui ler a skill só agora, para escrever este arquivo com evidência em vez de palpite. Ela contém,
em `references/padroes-de-falha.md` e `scripts/snapshot.py`:

- **A armadilha 1, nominalmente.** Linha 27 do arquivo de referência: "um pod em `CrashLoopBackOff`
  continua com `phase: Running`", e aponta `status.containerStatuses[].lastState.terminated` como
  onde a causa está.
- **A armadilha 2, como comentário de código.** Em `snapshot.py`:
  `pronto = st.get("readyReplicas", 0)  # ausente quando nenhuma esta pronta`.
- **A armadilha 3, com a decisão D5 embutida.** Linhas 71-72: "código que espera lista vazia quebra,
  e olho humano que procura `[]` não acha. O `Endpoints` também está a caminho da aposentadoria; a
  informação equivalente vive em `EndpointSlice`."
- **O mesmo invariante, com o mesmo nome.** `snapshot.py` declara `VERBOS_PERMITIDOS = {"get"}`.
  Eu escrevi, sem ter visto isso, `VERBOS_PERMITIDOS = frozenset({"get", "list", "watch"})` em
  `src/acesso.py`. Mesmo conceito, mesmo identificador, duas implementações independentes.

Ou seja: as três armadilhas de `00-brainstorm.md` e a decisão D5 de `02-decisoes.md` dizem quase o
mesmo que o material dessa skill. Não fui prejudicado — recebi o conteúdo pela spec, que é a fonte
correta neste ticket. Mas passei o trabalho todo sem saber que existia uma segunda cópia
daquele conhecimento na máquina, e **o parque agora tem duas.** A skill de manifests avisa, no
próprio texto, por que isso é ruim: "duas verdades sobre a mesma regra é como um padrão começa a
divergir de si mesmo". É exatamente o que está montado aqui.

Detalhe concreto da divergência que já nasceu: os dois `VERBOS_PERMITIDOS` têm conjuntos
diferentes. `{get}` na skill, `{get, list, watch}` no dashboard. Ambos defensáveis — a skill roda
`kubectl get`, eu uso `list` do cliente oficial —, mas quem ler os dois vai ter que descobrir
sozinho que a diferença é de ferramenta e não de política.

### Um uso que teria sido legítimo e eu não fiz

A skill diz que `snapshot.py` "traz, em ordem: prontos/desejados, estado dos containers com
`waiting` e `lastState`, recursos declarados, eventos de Warning, coerência entre selector e
rótulos". Isso é, em texto, quase a especificação dos meus cinco painéis. Rodá-lo contra
`nyx-prod` e `nyx-stg` teria sido um **oráculo** barato: uma segunda implementação, escrita por
outra pessoa, contra a qual conferir se meu `coleta.py` derivava os mesmos valores. Não usei, e
teria sido a forma mais rápida de pegar o defeito de autenticação descrito em `curadoria.md` —
porque o `snapshot.py` chama `kubectl`, que funcionava, enquanto o meu cliente Python autenticava
como anônimo.

---

## Nenhuma apareceu onde não devia

Respondendo direto à pergunta: **não houve disparo espúrio**, porque não houve disparo nenhum. O
mais perto disso foi a `padrao-manifests-metacortex` atuando sobre RBAC — e fui eu quem a arrastou
para lá, na mão.

---

## O que eu reexpliquei repetidamente mesmo tendo as duas

Esta é a parte que mais diz alguma coisa sobre a lacuna real.

**1. A disciplina do KUBECONFIG — de longe o campeão.** `export KUBECONFIG=~/.kube/metacortex-lab.yaml`
entrou em praticamente todo comando que rodei, em todo script, e a regra "nunca encostar no
`~/.kube/config`, que aponta para um EKS de produção real" teve que ser carregada por mim do
briefing até o fim. Nenhuma das duas skills sabe disso. A `triagem-de-cluster` é a que mais
deveria: ela lê cluster, aceita parâmetro de contexto, e seu risco de errar de cluster é o mesmo.
Hoje essa proteção existe só na cabeça de quem escreveu o briefing. **Se eu pudesse promover uma
única coisa deste ticket a regra de projeto, seria essa** — e não é conhecimento de Kubernetes, é
política do parque.

**2. As três armadilhas de forma de dado.** Foram reescritas por mim em: as specs (já estavam lá),
`design.md`, o docstring de `coleta.py`, três comentários inline em `coleta.py` explicando cada
uma no ponto de uso, os arquivos de evidência dos critérios 3, 4 e 5, e de novo em `curadoria.md`.
Parte dessa repetição é deliberada e boa — leitores diferentes, e um comentário no ponto de uso
vale mais que uma referência. Mas o **conteúdo** eu derivei da spec em cada lugar, sem nunca
apontar para uma fonte única, e agora descobri que a fonte única existia.

**3. Como chamar as ferramentas das skills nesta máquina.** As duas dizem
`python3 <skill>/scripts/...`. Nenhuma sabe que este ambiente é partido: o trabalho roda no WSL e
as skills moram no lado Windows, então o caminho real é
`python3 /mnt/c/Users/tales/.claude/skills/<skill>/scripts/...`. Tive que montar isso na mão, e
teria que montar de novo a cada chamada.

**4. Que o dashboard é somente leitura.** Repeti em: docstring de `acesso.py`, comentário sobre a
constante, docstring de `dashboard.py`, o selo no cabeçalho da tela, o rodapé da tela, a linha de
subida no stderr, `testes/test_invariante.py`, a spec de capacidade e a evidência do critério 9.
Aqui a repetição é o produto — a spec exigia que o invariante fosse *visível* —, então não conto
como desperdício. Registro porque é o único caso em que reexplicar era o objetivo.

---

## O que eu mudaria

1. **Uma regra de projeto para o kubeconfig**, acima das duas skills, dizendo qual cluster é
   permitido e qual é proibido. É a lacuna mais perigosa e a mais barata de fechar.
2. **`triagem-de-cluster` deveria cobrir "vou escrever código que lê o cluster"**, não só "há
   incidente ao vivo". O conhecimento dela — onde mora o estado de falha na API — serve a quem
   diagnostica *e* a quem instrumenta. Hoje a porta só abre para o primeiro.
3. **Alinhar a descrição da `padrao-manifests-metacortex` ao que ela cobre**: ou ela para de
   prometer "qualquer arquivo YAML", ou passa a ter algo a dizer sobre RBAC — que num parque
   multi-cliente é o tipo de objeto onde um erro custa mais caro que um `limits` mal dimensionado.
