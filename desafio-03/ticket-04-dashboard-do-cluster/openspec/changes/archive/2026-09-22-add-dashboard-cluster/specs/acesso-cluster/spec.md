# Spec Delta

## Purpose

Define como a aplicação alcança o apiserver do Kubernetes: sempre pelo contexto corrente do
kubeconfig da estação, sempre por um único ponto de passagem cujo conjunto de verbos permitidos é
explícito e somente de leitura, e com a falha de acesso classificada em categorias distintas.

## ADDED Requirements

### Requirement: Invocação sobre o contexto corrente

A aplicação SHALL resolver o destino exclusivamente a partir do `current-context` do kubeconfig da
estação no momento em que sobe. A aplicação MUST NOT aceitar argumento de cluster ou de contexto, e
MUST NOT oferecer seletor de contexto na interface. O único argumento de linha de comando aceito é
a porta de escuta (`--porta`, padrão 8700).

#### Scenario: Sobe sem argumento de cluster

- **WHEN** a aplicação é iniciada sem nenhum argumento
- **THEN** ela resolve o contexto corrente do kubeconfig e passa a servir na porta padrão
- **AND** nenhum argumento de cluster, contexto ou kubeconfig é exigido

#### Scenario: Contexto corrente sempre visível

- **WHEN** a interface é carregada
- **THEN** o cabeçalho fixo mostra o nome do contexto corrente e o endereço do servidor
- **AND** essa informação permanece visível independentemente do painel selecionado

#### Scenario: Troca de destino exige reinício

- **WHEN** quem opera quer olhar outro cluster
- **THEN** a interface não oferece meio de trocar o destino
- **AND** a troca se dá alterando o contexto por fora e reiniciando a aplicação

### Requirement: Invariante de somente-leitura verificável

Todo acesso ao apiserver SHALL passar por um único ponto do projeto que declara explicitamente o
conjunto de verbos permitidos, restrito a verbos de leitura (`get`, `list`, `watch`). Esse ponto
MUST recusar, em tempo de execução, qualquer tentativa de operação cujo verbo esteja fora do
conjunto declarado. Nenhum outro caminho de código MAY falar com o apiserver.

#### Scenario: Verbos permitidos declarados em um único lugar

- **WHEN** alguém audita o projeto quanto a risco de escrita
- **THEN** existe uma única função/ponto de passagem cuja leitura revela o conjunto completo de
  verbos permitidos
- **AND** esse conjunto contém apenas verbos de leitura

#### Scenario: Tentativa de verbo de escrita é recusada

- **WHEN** um caminho de código solicita ao ponto de passagem uma operação com verbo de escrita
  (`create`, `update`, `patch`, `delete`, `deletecollection`, `scale`, `exec`)
- **THEN** o ponto de passagem recusa a chamada com erro antes de qualquer tráfego de rede
- **AND** nenhuma requisição é enviada ao apiserver

#### Scenario: Nenhuma chamada de escrita alcança o apiserver

- **WHEN** a aplicação é exercitada em qualquer cenário previsto nesta especificação
- **THEN** todo método HTTP emitido contra o apiserver é `GET`
- **AND** nenhum recurso do cluster é criado, alterado ou removido

### Requirement: Classificação de falha de acesso

A camada de acesso SHALL classificar a falha de comunicação com o apiserver em categorias
distintas e nomeadas — no mínimo: cluster inalcançável, credencial inválida ou expirada, permissão
negada para um tipo de recurso, e falha não classificada. A categoria MUST acompanhar a informação
suficiente para a ação de quem lê (por exemplo, o endereço tentado, ou o recurso negado).

#### Scenario: Categorias distintas para causas distintas

- **WHEN** a leitura de um recurso falha
- **THEN** a falha é reportada com uma categoria nomeada, e não como erro genérico
- **AND** cluster inalcançável, credencial inválida e permissão negada produzem categorias
  diferentes entre si

#### Scenario: Falha é dado, não exceção que sobe à interface

- **WHEN** qualquer recurso falha ao ser lido
- **THEN** a falha é devolvida como parte do retrato do cluster, associada ao recurso que falhou
- **AND** a aplicação continua servindo a interface
