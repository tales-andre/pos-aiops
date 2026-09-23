# Tasks

## 1. Ponto de passagem e invariante de somente-leitura

- [x] 1.1 Criar `src/acesso.py` com `VERBOS_PERMITIDOS` explícito (apenas `get`, `list`, `watch`) e
      a função única `ler(...)`; verificar rodando um trecho que pede verbo `delete` e confirmar que
      levanta erro antes de qualquer tráfego de rede
- [x] 1.2 Resolver o contexto corrente e o endereço do servidor a partir do kubeconfig no
      `acesso.py`; verificar com `KUBECONFIG=~/.kube/metacortex-lab.yaml` que o contexto reportado é
      `kind-metacortex-lab` e bate com `kubectl config current-context`
- [x] 1.3 Implementar a classificação de falha em categorias nomeadas (`cluster_inalcancavel`,
      `credencial_invalida`, `permissao_negada`, `nao_encontrado`, `falha_desconhecida`); verificar
      com um teste que mapeia `ApiException(403)` e `ApiException(401)` para categorias distintas
- [x] 1.4 Escrever o teste do invariante que falha se qualquer módulo de `src/` além de `acesso.py`
      importar o cliente `kubernetes`; verificar que o teste passa no estado corrente do projeto

## 2. Coleta e normalização das armadilhas de forma de dado

- [x] 2.1 Criar `src/coleta.py` com o envelope único por recurso (`{ok, itens}` ou
      `{ok:false, categoria, recurso, mensagem}`); verificar que um recurso negado devolve envelope
      de falha sem levantar exceção
- [x] 2.2 Coletar namespaces e deployments, derivando `prontos/desejados` com `readyReplicas`
      ausente lido como zero; verificar contra `nyx-prod` (deployment sem réplica pronta) que o
      resultado é `0/2` e não campo em branco
- [x] 2.3 Coletar pods derivando estado e motivo de `containerStatuses` (`state.waiting.reason`,
      `state.terminated.reason`, `lastState.terminated.reason`), nunca de `phase`; verificar contra
      `nyx-prod` que o pod aparece como `CrashLoopBackOff` com motivo `OOMKilled`, e contra
      `orion-stg` que aparece `ImagePullBackOff`
- [x] 2.4 Coletar services com agregação de `EndpointSlice` por `kubernetes.io/service-name`, com
      queda para `Endpoints`, colapsando ausência e lista vazia em zero endereços; verificar contra
      `nyx-stg` que o Service aparece "sem endpoint" e contra `helio-prod` que aparece com contagem
- [x] 2.5 Coletar eventos do namespace selecionado com `Warning` primeiro e idade calculada;
      verificar contra `orion-stg` que os eventos de falha de imagem aparecem no topo
- [x] 2.6 Aplicar timeout curto nas chamadas ao apiserver; verificar que um kubeconfig apontando
      para endereço morto devolve envelope `cluster_inalcancavel` em poucos segundos, sem travar

## 3. Servidor e interface

- [x] 3.1 Criar `src/dashboard.py` com `http.server`, argumento `--porta` (padrão 8700) e apenas
      `do_GET`; verificar que `curl -X POST` contra a raiz devolve `501` e que nenhum outro método
      está implementado
- [x] 3.2 Servir `GET /api/contexto` respondendo contexto e servidor mesmo com o cluster fora do ar;
      verificar com o kubeconfig quebrado que a rota ainda responde `200` com o endereço tentado
- [x] 3.3 Servir `GET /api/snapshot?ns=<namespace>` com um envelope por recurso; verificar com
      `curl` contra `helio-prod` que os cinco recursos vêm preenchidos
- [x] 3.4 Construir `src/ui/index.html`, `app.js` e `estilo.css` com cabeçalho fixo de contexto e
      servidor, os cinco painéis e renderização por envelope; verificar que o HTML servido carrega e
      mostra o contexto corrente no cabeçalho
- [x] 3.5 Implementar filtro por namespace e busca por nome sobre deployments, pods e services, com
      mensagem distinta para "nenhum resultado para a busca"; verificar que buscar `postgres` em
      `nyx-prod` reduz os painéis e que um termo inexistente produz a mensagem de busca vazia
- [x] 3.6 Implementar o relógio de "atualizado há X", a atualização automática em intervalo fixo e o
      botão de atualização manual; verificar que o relógio avança e que o botão relê o snapshot
- [x] 3.7 Renderizar envelope de falha como faixa no painel afetado, com texto distinto por
      categoria e botão de nova tentativa; verificar que nenhum caminho produz tela em branco ou
      rastro de pilha

## 4. Validação contra o cluster de laboratório

- [x] 4.1 Preparar os dois cenários fabricados: kubeconfig com `server` apontando para endereço
      morto, e ServiceAccount + Role + RoleBinding que lê pods mas não services, com kubeconfig de
      token; verificar com `kubectl auth can-i` que a SA pode `get pods` e não pode `get services`
- [x] 4.2 Capturar a evidência dos critérios 1 a 5 contra `helio-prod`, `nyx-prod`, `nyx-stg` e
      `orion-stg`, salvando em `execucoes/` a saída HTTP e o comando que a gerou
- [x] 4.3 Capturar a evidência dos critérios 6 e 7 com os cenários fabricados, salvando em
      `execucoes/` a saída HTTP e o comando
- [x] 4.4 Capturar a evidência dos critérios 8 e 9, incluindo a saída do teste do invariante;
      verificar que os nove critérios têm arquivo de evidência correspondente
