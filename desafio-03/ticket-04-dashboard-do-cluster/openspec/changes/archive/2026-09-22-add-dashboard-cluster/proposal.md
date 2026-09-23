# Proposal

## Why

Toda triagem no parque começa igual: seis a dez comandos `kubectl` para montar na cabeça o retrato
de um namespace. O trabalho não é difícil, é repetitivo e é sempre o mesmo. O dashboard encurta os
primeiros dez minutos de todo chamado colocando esse retrato na tela, para quem está **olhando** e
não perguntando — complementando a skill de triagem do Ticket 02, que serve quem pergunta.

Agora, porque o parque já tem casos de falha silenciosa em produção (Service sem endpoint, pod em
`CrashLoopBackOff` reportando `phase: Running`) que a leitura ingênua da API esconde.

## What Changes

- Nova aplicação web local (`dashboard`), somente leitura, que sobe contra o **contexto corrente**
  do kubeconfig da estação — sem argumento de cluster, sem seletor de contexto na tela.
- Cinco painéis de leitura por namespace: Namespaces, Deployments, Pods, Services (com presença de
  endpoint) e Eventos.
- Filtro por namespace e busca por nome aplicados aos painéis de objetos.
- Tratamento explícito das **três armadilhas de forma de dado** da API: `readyReplicas` ausente,
  `phase: Running` em pod que reinicia em laço, e ausência do campo de endereços em Service sem
  endpoint.
- **Degradação parcial** como comportamento de primeira classe: `403` em um recurso não derruba os
  demais painéis; cluster fora do ar e credencial inválida produzem mensagens distintas.
- Invariante de somente-leitura **verificável em um único ponto do projeto**: uma camada de acesso
  com a lista de verbos permitidos explícita.

Sem breaking changes — o projeto não tem código anterior.

## Capabilities

### New Capabilities

- `acesso-cluster`: ponto único de passagem para o apiserver — resolução do contexto corrente,
  invariante de somente-leitura com verbos explícitos, e classificação de falha (fora do ar,
  credencial inválida, permissão negada) em categorias distintas.
- `paineis-do-cluster`: o que cada painel mostra e como derivar os campos que a API responde por
  omissão; filtro por namespace e busca por nome.
- `resiliencia-de-leitura`: comportamento observável quando o ambiente não colabora — degradação
  parcial por recurso, mensagens distintas por categoria de erro, e a distinção entre "nenhum
  objeto" e "não consegui ler".

### Modified Capabilities

<!-- Nenhuma: o projeto ainda não tem specs publicadas em openspec/specs/. -->

## Impact

- **Código novo**: `src/` na raiz do ticket (servidor HTTP da biblioteca padrão, camada de acesso
  ao cluster, página única com JavaScript sem framework).
- **Dependência nova**: cliente oficial `kubernetes` para Python (decisão D2). Nenhuma outra.
- **Superfície de rede**: escuta em `localhost` numa porta configurável (padrão 8700). Sem
  autenticação própria — a credencial é o kubeconfig de quem abre.
- **Carga no apiserver**: cinco consultas `list` por ciclo de atualização, por pessoa olhando
  (decisão D3).
- **Sistemas afetados**: nenhum. A aplicação não escreve no cluster; o invariante é parte do
  contrato, não uma promessa.
