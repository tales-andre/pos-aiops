# Design

## Context

Ver `proposal.md — Why` para a motivação. As decisões estruturais D1 a D5 foram tomadas e
registradas **antes** desta mudança, em `specs/02-decisoes.md` na raiz do ticket, cada uma com pelo
menos duas alternativas descartadas. Este documento não as renegocia: transcreve o que foi decidido
e desce ao nível de arquitetura que falta.

Restrições que moldam o desenho:

- Quem mantém é time de infraestrutura, não de produto. A métrica é o custo de alguém do plantão
  abrir o arquivo às três da manhã e mudar uma coluna.
- A aplicação fala com produção. O invariante de somente-leitura precisa ser **auditável**, não
  prometido.
- A API do Kubernetes responde por omissão em vez de por valor vazio em três pontos que são
  justamente os que mais importam para triagem.

## Goals / Non-Goals

**Goals:**

- Um único ponto de passagem para o apiserver, com os verbos permitidos como dado explícito, de
  modo que a auditoria do invariante seja a leitura de uma função.
- Um retrato do cluster em formato único (um "snapshot") que carregue, por recurso, ou os dados ou
  a falha classificada — nunca uma exceção que suba à interface.
- Normalização das três armadilhas de forma de dado no servidor, não no JavaScript: o navegador
  recebe o dado já derivado, então um erro de derivação não se espalha por várias telas.

**Non-Goals:**

- Abstrair o cliente do Kubernetes atrás de uma camada de portabilidade. Um adaptador só.
- Cache, persistência ou histórico. O snapshot vive na requisição.
- Concorrência real no servidor. `localhost`, uma pessoa (ver D1).

## Decisions

### D1 — Python 3, `http.server`, página única sem framework

**Escolhido** (transcrito de `specs/02-decisoes.md`). Python já está em toda máquina do parque e é a
linguagem do Ticket 03. A única dependência real é o cliente oficial do Kubernetes.

*Descartados*: **Go com binário único** — distribuição trivial e ecossistema nativo, mas o time não
escreve Go; distribuição é problema de uma vez, manutenção é de todo dia. **React/Vue com backend de
API** — melhor interface, mas `node_modules`, passo de build e uma segunda pilha para cinco painéis
de leitura.

*Consequência de desenho*: `http.server` é single-thread. Aceito, porque é `localhost` para uma
pessoa. O tempo de uma requisição `/api/snapshot` é dominado pelas leituras ao apiserver, e elas
são sequenciais.

### D2 — Cliente oficial `kubernetes` para Python

**Escolhido.** Resolve o kubeconfig inteiro, inclusive plugins de credencial por `exec` — o
kubeconfig real da estação tem contexto de EKS que autentica via `aws eks get-token`. Objetos
tipados tornam explícita a distinção entre campo ausente (`None`) e campo vazio (`[]`), que é
exatamente a armadilha do `Endpoints`.

*Descartados*: **`kubectl` como subprocesso** — zero dependência e depuração trivial, mas um
processo por consulta, e a saída JSON é dicionário sem tipo, então ausência-vs-vazio vira disciplina
em cada acesso. **HTTP direto contra o apiserver** — mais leve, mas reimplementar `ExecCredential`
é reescrever a parte do cliente oficial que mais valor entrega, e errar nela é falha de segurança.

### D3 — Consulta em intervalo fixo, relógio visível, atualização manual

**Escolhido.** Carga conhecida e limitada; reconexão é a próxima consulta. O relógio de "atualizado
há X" torna o atraso **declarado** em vez de oculto — o que importa mais que o atraso ser pequeno.

*Descartados*: **`watch`** — menor atraso, mas exige tratar `resourceVersion` expirada, reconexão
com bookmark e resincronização; com `403` a falha vira conexão morrendo em laço em vez de painel
dizendo "sem permissão". **Sob demanda apenas** — menor carga, mas a tela envelhece sem avisar, e
dado velho é pior que dado ausente numa triagem.

### D4 — Cinco painéis, filtro por namespace, busca por nome, contexto corrente só

**Escolhido.** Escopo pequeno o bastante para que os três cenários de ambiente hostil sejam tratados
de verdade e não como `TODO`.

*Descartados*: **logs de container na primeira fatia** — volume, streaming, paginação, e risco de
vazamento de dado de cliente numa tela sem controle de acesso. **fatia mínima só com pods e
eventos** — deixaria o caso de falha mais silencioso do parque exatamente onde estava.

### D5 — `EndpointSlice`, com `Endpoints` como alternativa de compatibilidade

**Escolhido.** É para onde a API está indo. Consequência de desenho: "tem endpoint?" é uma
**agregação** — um Service pode ter várias slices, ligadas pelo rótulo
`kubernetes.io/service-name`. Em cluster antigo sem `EndpointSlice`, cai para `Endpoints`.

*Descartados*: **só `Endpoints`** — mais simples, mas dívida assumida no dia em que se escreve.
**não mostrar endpoint** — economiza a decisão e perde o caso de falha mais silencioso que existe.

### Estrutura do código

```
src/
  dashboard.py       ponto de entrada: --porta, servidor http.server, rotas
  acesso.py          O PONTO DE PASSAGEM. verbos permitidos + classificação de falha
  coleta.py          monta o snapshot: chama acesso.py e normaliza as 3 armadilhas
  ui/index.html      página única
  ui/app.js          DOM na mão: filtro, busca, relógio, render dos painéis
  ui/estilo.css
```

O invariante mora em `acesso.py`: uma constante `VERBOS_PERMITIDOS = {"get", "list", "watch"}` e uma
única função `ler(verbo, recurso, ...)` que valida o verbo antes de qualquer chamada de rede. Todo
acesso de `coleta.py` passa por ela. `dashboard.py` não importa `kubernetes` — apenas `coleta`.
Auditar o invariante é `grep` por `kubernetes` no `src/` e ler uma função.

### Forma do snapshot

Cada recurso do snapshot é um envelope com a mesma forma:

```
{"ok": true,  "itens": [...]}
{"ok": false, "categoria": "permissao_negada", "recurso": "services", "mensagem": "..."}
```

Isso resolve a degradação parcial sem código condicional espalhado: a interface renderiza cada
painel a partir do seu envelope, e um envelope de falha vira uma faixa no painel em vez de derrubar
a página. As categorias são `cluster_inalcancavel`, `credencial_invalida`, `permissao_negada`,
`nao_encontrado` e `falha_desconhecida`.

### Normalização das três armadilhas (feita no servidor)

1. **Pods**: o estado exibido vem de `containerStatuses`. Ordem de precedência:
   `state.waiting.reason` → `state.terminated.reason` → `Running`/`NotReady` conforme `ready`. O
   motivo adicional vem de `lastState.terminated.reason` (é daí que sai `OOMKilled`, que não aparece
   em `state.waiting.reason`, onde está apenas `CrashLoopBackOff`). `phase` nunca é a fonte do
   estado exibido.
2. **Deployments**: `prontos = status.readyReplicas or 0` — `None` e `0` colapsam no mesmo valor
   exibido `0/N`, e `N` vem de `spec.replicas`.
3. **Services**: a contagem de endereços é agregada sobre as `EndpointSlice` do Service. `None` e
   `[]` em `endpoints[].addresses` colapsam em zero endereços. Zero endereços é **"sem endpoint"**;
   falha na leitura das slices é um envelope de falha, e nunca "sem endpoint".

### Rotas HTTP

- `GET /` → a página
- `GET /api/contexto` → `{contexto, servidor}`, respondida mesmo com o cluster fora do ar
- `GET /api/snapshot?ns=<namespace>` → o retrato completo, com um envelope por recurso
- `GET /ui/*` → estáticos

Nenhuma rota aceita `POST`, `PUT`, `PATCH` ou `DELETE`; o handler implementa apenas `do_GET`, então
qualquer outro método recebe `501` do próprio `BaseHTTPRequestHandler`.

## Risks / Trade-offs

- **`http.server` é single-thread** → aceito por construção (`localhost`, uma pessoa). Mitigação
  parcial: a leitura do snapshot tem timeout curto, para que um cluster fora do ar não prenda o
  servidor por minutos. Sem timeout, o cenário 6 vira travamento em vez de mensagem.
- **Cluster grande faz `list` caro** → o snapshot lê apenas o namespace selecionado, exceto a lista
  de namespaces. Continua sendo `list` sem paginação; num cluster com milhares de pods num único
  namespace isso pesa. Aceito nesta fatia, registrado aqui.
- **`EndpointSlice` pode não existir em cluster antigo** → queda para `Endpoints`, com a mesma
  normalização de ausência-vs-vazio.
- **O invariante depende de disciplina de importação** → mitigado por fazer de `acesso.py` o único
  módulo que importa `kubernetes`, e por um teste que falha se outro módulo do `src/` importar o
  cliente diretamente.
- **JavaScript sem framework azeda com o crescimento** → aceito para cinco painéis; é o custo
  nomeado em D1.

## Migration Plan

Não se aplica: projeto novo, sem estado persistido e sem consumidor anterior. Desinstalar é apagar
o diretório; a aplicação não deixa nada no cluster (invariante).

## Open Questions

Nenhuma que possa ser adiada sem mexer nas specs. As dúvidas de durabilidade (`Endpoints` versus
`EndpointSlice`) e de escopo (logs) já estão resolvidas em D4 e D5.
