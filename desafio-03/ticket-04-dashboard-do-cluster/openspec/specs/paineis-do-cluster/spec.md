# paineis-do-cluster Specification

## Purpose
Define o retrato do namespace que a tela entrega — os cinco painéis de leitura, como derivar os
campos que a API do Kubernetes responde por omissão em vez de por valor vazio, e o filtro por
namespace e a busca por nome que tornam o retrato utilizável num cluster com centenas de objetos.

## Requirements

### Requirement: Painel de namespaces como filtro principal

A aplicação SHALL listar os namespaces do cluster e SHALL destacar o selecionado. A seleção de um
namespace MUST filtrar todos os demais painéis de objetos para aquele namespace.

#### Scenario: Lista namespaces e destaca o selecionado

- **WHEN** a interface carrega contra um cluster acessível
- **THEN** o painel de namespaces lista os namespaces existentes
- **AND** o namespace corrente aparece destacado

#### Scenario: Selecionar namespace filtra os demais painéis

- **WHEN** quem opera seleciona um namespace
- **THEN** os painéis de Deployments, Pods, Services e Eventos passam a mostrar apenas objetos
  daquele namespace

### Requirement: Painel de deployments com prontos sobre desejados

O painel de Deployments SHALL mostrar, para cada deployment, o nome e a razão de réplicas prontas
sobre desejadas. Quando o campo de réplicas prontas estiver **ausente** da resposta da API, a
aplicação MUST tratar a ausência como zero e exibir `0/N`. A aplicação MUST NOT exibir campo em
branco nessa situação.

#### Scenario: Deployment sem réplica pronta aparece como 0/N

- **WHEN** um Deployment com `N` réplicas desejadas não tem nenhuma réplica pronta, e a API por
  isso omite o campo de réplicas prontas
- **THEN** o painel exibe `0/N`
- **AND** não exibe espaço em branco, traço ou `N/N`

#### Scenario: Deployment saudável aparece como N/N

- **WHEN** um Deployment tem todas as réplicas prontas
- **THEN** o painel exibe `N/N`

### Requirement: Painel de pods com estado do container e motivo da falha

O painel de Pods SHALL mostrar nome, estado, contagem de reinícios e, quando em falha, o **motivo**.
O estado exibido MUST derivar do estado dos containers do pod, e não da fase do pod. O motivo MUST
vir de `state.waiting.reason` ou de `lastState.terminated.reason`, e MUST NOT vir de `phase`. Um
pod reiniciando em laço MUST NOT aparecer como "Running" sem qualificação.

#### Scenario: Pod em CrashLoopBackOff mostra o motivo, não a fase

- **WHEN** um pod está em `CrashLoopBackOff` e a API ainda reporta `phase: Running`
- **THEN** o painel exibe o estado `CrashLoopBackOff`
- **AND** exibe o motivo da última terminação (por exemplo `OOMKilled`)
- **AND** em nenhum momento exibe esse pod apenas como "Running"

#### Scenario: Pod com imagem inacessível mostra o motivo de espera

- **WHEN** um pod não consegue baixar a imagem e seu container está em `ImagePullBackOff`
- **THEN** o painel exibe esse motivo
- **AND** exibe a contagem de reinícios do pod

#### Scenario: Pod saudável aparece como Running

- **WHEN** todos os containers de um pod estão em execução e prontos
- **THEN** o painel exibe o estado `Running`

### Requirement: Painel de services com presença de endpoint

O painel de Services SHALL mostrar nome, tipo, portas e **se o Service tem endpoint**. A aplicação
MUST distinguir três situações: o Service tem endereços, o Service não tem nenhum endereço, e a
leitura de endpoints não pôde ser feita. A ausência do campo de endereços na resposta da API MUST
ser lida como "sem endpoint", nunca como leitura falha.

#### Scenario: Service sem endpoint é marcado como tal

- **WHEN** um Service não casa com nenhum pod e a API, por isso, não traz o campo de endereços
- **THEN** o painel marca esse Service como "sem endpoint"
- **AND** a marcação é visualmente distinta de um erro de leitura

#### Scenario: Service com endpoint mostra a contagem

- **WHEN** um Service tem endereços associados
- **THEN** o painel indica que há endpoint e quantos endereços

#### Scenario: Leitura de endpoints negada não vira "sem endpoint"

- **WHEN** a leitura dos endpoints falha por permissão ou erro
- **THEN** o painel informa que não conseguiu ler os endpoints
- **AND** não marca os Services como "sem endpoint"

### Requirement: Painel de eventos do namespace selecionado

O painel de Eventos SHALL mostrar tipo, motivo, objeto envolvido, mensagem e idade, restrito ao
namespace selecionado. Eventos de tipo `Warning` MUST aparecer antes dos demais.

#### Scenario: Eventos de aviso vêm primeiro

- **WHEN** o namespace selecionado tem eventos de tipo `Warning` e `Normal`
- **THEN** os eventos `Warning` aparecem no topo da lista

#### Scenario: Eventos restritos ao namespace selecionado

- **WHEN** um namespace está selecionado
- **THEN** o painel mostra apenas eventos daquele namespace

### Requirement: Filtro por namespace e busca por nome

A aplicação SHALL oferecer busca por nome que se aplica aos painéis de objetos (Deployments, Pods e
Services), combinada com o filtro por namespace. A busca MUST ser por correspondência parcial e
insensível a maiúsculas.

#### Scenario: Busca por nome reduz os painéis de objetos

- **WHEN** quem opera digita um termo na busca
- **THEN** os painéis de Deployments, Pods e Services mostram apenas objetos cujo nome contém o
  termo
- **AND** a contagem exibida em cada painel reflete o resultado filtrado

#### Scenario: Busca e filtro de namespace se combinam

- **WHEN** um namespace está selecionado e um termo de busca está preenchido
- **THEN** os painéis mostram apenas objetos daquele namespace cujo nome contém o termo

#### Scenario: Busca sem resultado é distinta de painel vazio

- **WHEN** nenhum objeto casa com o termo de busca
- **THEN** o painel informa que nenhum objeto casou com a busca
- **AND** essa mensagem é distinta de "nenhum objeto no namespace" e de erro de leitura

### Requirement: Atraso declarado e atualização manual

A tela SHALL exibir há quanto tempo o retrato foi atualizado e SHALL oferecer atualização manual. A
atualização automática MUST ocorrer em intervalo fixo declarado na interface.

#### Scenario: Relógio de atualização visível

- **WHEN** a interface está carregada
- **THEN** ela mostra há quanto tempo os dados foram lidos do cluster

#### Scenario: Atualização manual disponível

- **WHEN** quem opera aciona a atualização manual
- **THEN** o retrato é relido do cluster e o relógio reinicia
