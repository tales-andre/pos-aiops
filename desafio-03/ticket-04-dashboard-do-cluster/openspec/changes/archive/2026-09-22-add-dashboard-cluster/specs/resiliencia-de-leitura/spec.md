# Spec Delta

## Purpose

Define o comportamento observável quando o ambiente não colabora — cluster fora do ar, credencial
inválida, permissão negada para um tipo de recurso — de modo que a tela nunca fique em branco, nunca
mostre rastro de pilha e nunca faça uma falha de leitura parecer lista vazia.

## ADDED Requirements

### Requirement: A interface carrega mesmo sem cluster

A aplicação SHALL servir a interface independentemente do estado do cluster. A aplicação MUST NOT
falhar ao subir porque o apiserver está inacessível, e MUST NOT apresentar tela em branco nem rastro
de pilha na interface em nenhuma circunstância.

#### Scenario: Cluster fora do ar carrega a tela e explica

- **WHEN** o contexto corrente aponta para um endereço que não responde
- **THEN** a interface carrega normalmente
- **AND** o cabeçalho mostra o contexto e o servidor tentado
- **AND** a tela exibe, em linguagem clara, que o cluster não respondeu, citando o endereço tentado
- **AND** oferece nova tentativa

#### Scenario: Nunca tela em branco nem rastro de pilha

- **WHEN** qualquer falha ocorre durante a leitura do cluster
- **THEN** a interface exibe uma mensagem descritiva
- **AND** não exibe rastro de pilha nem fica em branco

### Requirement: Credencial inválida distinta de cluster fora do ar

Quando o cluster responde mas a autenticação não passa, a aplicação SHALL exibir mensagem distinta
da de cluster inalcançável, porque a ação de quem lê é outra.

#### Scenario: Credencial expirada ou inválida

- **WHEN** o apiserver responde com falha de autenticação
- **THEN** a tela indica credencial inválida ou expirada
- **AND** a mensagem é distinta da mensagem de cluster fora do ar

### Requirement: Degradação parcial por recurso

Quando a permissão é negada para **um** tipo de recurso, os painéis dos recursos acessíveis SHALL
continuar funcionando normalmente. O painel do recurso negado MUST exibir "sem permissão para ler
&lt;recurso&gt;". A aplicação MUST NOT falhar a tela inteira por causa de um `403`.

#### Scenario: 403 em um recurso não derruba os demais painéis

- **WHEN** a credencial corrente pode ler pods mas não pode ler Services
- **THEN** o painel de Pods mostra os pods normalmente
- **AND** o painel de Services mostra "sem permissão para ler services"
- **AND** os demais painéis acessíveis continuam populados

#### Scenario: Permissão negada é distinta de lista vazia

- **WHEN** um painel não pôde ser lido por falta de permissão
- **THEN** ele exibe a negativa de permissão
- **AND** não exibe "nenhum objeto"

### Requirement: Namespace sem objetos distinto de erro

Quando um namespace acessível não tem objetos de um tipo, a aplicação SHALL exibir "nenhum objeto",
de forma distinta de qualquer condição de erro.

#### Scenario: Namespace vazio informa ausência de objetos

- **WHEN** o namespace selecionado não tem nenhum Deployment e a leitura foi bem-sucedida
- **THEN** o painel de Deployments exibe "nenhum objeto"
- **AND** essa mensagem é distinta de erro de leitura e de permissão negada
