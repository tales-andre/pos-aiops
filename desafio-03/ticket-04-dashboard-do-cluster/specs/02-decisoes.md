# Decisões técnicas — justificativa estendida

Quatro decisões que este projeto deixa em aberto e que não têm resposta única. Cada uma compara o
caminho escolhido com **pelo menos dois descartados**, dizendo o que se ganha e o que se perde em
cada um. Quem pegar este código daqui a um ano vai perguntar por quê, e o commit não responde.

---

## D1 — Linguagem e stack

**Contexto que decide:** quem vai manter isso é um time de infraestrutura, não um time de produto.
A métrica não é velocidade de escrita, é custo de alguém do plantão abrir o arquivo e mudar uma
coluna às três da manhã.

### Escolhido — Python 3, servidor da biblioteca padrão, página única com JavaScript sem framework

**Ganha:** Python já está em toda máquina do parque e é a linguagem do Ticket 03, então o
repositório inteiro fala uma língua só. O servidor sai da `http.server`, sem framework web. A
única dependência real é o cliente oficial do Kubernetes. Um plantonista que sabe ler um script
consegue mudar o dashboard.

**Perde:** `http.server` é single-thread e não serve produção — o que é aceitável porque isto roda
em `localhost` para uma pessoa. JavaScript sem framework significa manipular DOM na mão; a partir
de umas poucas telas isso azeda.

### Descartado — Go com binário único

**Ganharia:** distribuição trivial. Um binário, sem runtime, sem dependência — para um time de
infraestrutura isso é genuinamente atraente, e o ecossistema Kubernetes é Go, então o cliente
oficial é de primeira classe.

**Perderia:** o time não escreve Go no dia a dia. Uma mudança pequena passa a exigir toolchain,
compilação e alguém que saiba. Distribuição é um problema de uma vez; manutenção é de todo dia — e
o problema declarado é o custo diário.

### Descartado — React ou Vue com backend de API

**Ganharia:** a interface mais confortável dos três, com componentes prontos para tabela, filtro e
busca, e espaço para crescer sem virar espaguete.

**Perderia:** `node_modules`, passo de build, e uma segunda pilha para manter. Para cinco painéis
de leitura, o custo de manutenção não se paga — e o time que mantém não é de frontend.

---

## D2 — Como falar com a API do Kubernetes

Três caminhos reais, e cada um resolve autenticação, contexto e tipagem de um jeito diferente.

### Escolhido — cliente oficial da linguagem (`kubernetes` para Python)

**Ganha:** resolve o kubeconfig inteiro, incluindo a parte chata — certificado de cliente,
`current-context`, e principalmente os **plugins de credencial por `exec`**. Isso não é detalhe: o
kubeconfig desta estação tem um contexto de EKS que autentica via `aws eks get-token`. Objetos
tipados tornam explícita a distinção entre campo ausente e campo vazio, que é justamente a
armadilha do `Endpoints`.

**Perde:** uma dependência pesada, que costuma atrasar em relação à versão do cluster. E o modelo
de objetos gerado é verboso.

### Descartado — chamar `kubectl` como subprocesso e ler a saída

**Ganharia:** zero dependência de biblioteca, e compatibilidade perfeita com kubeconfig por
construção — o `kubectl` é a referência. Fácil de depurar: o comando que roda é o comando que você
digitaria.

**Perderia:** um processo por consulta, e cinco painéis atualizando viram muitos processos. O
`kubectl` precisa existir na máquina. Pior: a saída JSON é dicionário sem tipo, então a distinção
entre ausência e vazio passa a depender de disciplina em cada acesso — exatamente onde as
armadilhas moram.

### Descartado — HTTP direto contra o apiserver

**Ganharia:** controle total, dependência nenhuma além de um cliente HTTP, e o menor peso dos três.

**Perderia:** reimplementar autenticação. Certificado de cliente é viável; plugin de credencial por
`exec` significa reimplementar a especificação de `ExecCredential`, invocar o binário externo,
tratar cache e renovação de token. Seria reescrever a parte do cliente oficial que mais valor
entrega, e errar nela é falha de segurança, não bug de tela.

---

## D3 — Como manter a tela atualizada

### Escolhido — consulta em intervalo fixo, com relógio visível e atualização manual

**Ganha:** simples e previsível. A carga sobre o apiserver é conhecida e limitada: cinco consultas
a cada N segundos, por pessoa olhando. Sem estado de conexão para gerenciar, e reconexão é a
próxima consulta. O relógio de "atualizado há X" na tela torna o atraso **declarado** em vez de
oculto — o que importa mais que o atraso ser pequeno.

**Perde:** atraso de até um intervalo. Num incidente em movimento, a tela pode estar mostrando algo
que acabou de mudar — e é por isso que o relógio é obrigatório, não opcional.

### Descartado — observar mudanças com `watch` e receber eventos conforme acontecem

**Ganharia:** o menor atraso possível e a menor carga em regime — uma conexão longa por recurso em
vez de consulta repetida.

**Perderia:** complexidade que não se paga aqui. `watch` exige tratar `resourceVersion` expirada,
reconexão com `bookmark`, e resincronização depois de queda. Com permissão negada para um recurso,
a falha vira uma conexão que morre em laço em vez de um painel que diz "sem permissão". Para uma
ferramenta aberta por dez minutos no começo de um chamado, o ganho de latência não compensa o
código de reconexão.

### Descartado — consultar apenas sob demanda, quando a pessoa pede

**Ganharia:** a menor carga possível sobre o apiserver, e nenhum tráfego com a aba esquecida aberta.

**Perderia:** a tela fica velha sem avisar, e o dado velho é pior que dado ausente numa triagem —
alguém conclui a partir de um retrato de cinco minutos atrás achando que é agora.

---

## D4 — Quanto do escopo entra na primeira fatia

### Escolhido — os cinco painéis do enunciado, filtro por namespace, busca por nome, contexto corrente só

**Ganha:** cobre o que o enunciado pede e resolve o problema declarado, que é encurtar os primeiros
dez minutos do chamado. Escopo pequeno o bastante para que os três cenários de ambiente hostil
sejam tratados de verdade, e não como `TODO`.

**Perde:** quem quiser log de container continua indo ao terminal.

### Descartado — incluir logs de container na primeira fatia

**Ganharia:** log é o passo seguinte natural depois de ver um pod em falha, e evitaria a troca de
janela.

**Perderia:** log é volume, streaming e paginação — sozinho vale mais que os cinco painéis juntos
em esforço. E tem risco de vazamento: log de produção carrega dado de cliente, e exibir isso numa
tela sem controle de acesso é decisão de segurança, não de produto.

### Descartado — começar por uma fatia mínima com só pods e eventos

**Ganharia:** entrega mais rápida, feedback mais cedo.

**Perderia:** não resolveria o problema. Metade das triagens do Ticket 02 dependeu de Service e
Endpoints — o chamado 3 é inteiramente sobre isso. Um dashboard sem Services deixa o caso mais
silencioso do parque exatamente onde ele estava: invisível.

---

## D5 — `Endpoints` ou `EndpointSlice`

Decisão pequena com consequência de durabilidade, que o enunciado levanta explicitamente.

**Escolhido — `EndpointSlice`, com `Endpoints` como alternativa de compatibilidade.**

**Ganha:** é para onde a API está indo; `Endpoints` está a caminho da aposentadoria. E
`EndpointSlice` já é o objeto real em clusters modernos — `Endpoints` passa a ser tradução.

**Perde:** um Service pode ter várias slices, então "tem endpoint?" vira uma agregação em vez de
uma leitura. E em cluster muito antigo `EndpointSlice` pode não existir, daí a alternativa.

**Descartado — só `Endpoints`:** mais simples de ler, um objeto por Service, e é o que aparece em
todo tutorial. Perde por ser dívida assumida conscientemente no dia em que se escreve o código.

**Descartado — não mostrar endpoint e deixar para o terminal:** economiza a decisão inteira, e
perde o caso de falha mais silencioso que existe. Foi por não enxergar isso que o chamado 3 do
Ticket 02 ficou em pé.
