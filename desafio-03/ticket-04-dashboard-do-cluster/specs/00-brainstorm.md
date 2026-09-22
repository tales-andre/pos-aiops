# Brainstorm — enxergar o cluster

Documento de maturação de escopo, escrito antes de qualquer código.

## O problema

Toda triagem começa igual: alguém abre o terminal e roda de seis a dez comandos para montar na
cabeça o retrato de um namespace. `get pods`, `get deploy`, `describe` do que está estranho,
`get events`, `get svc`, `get endpoints`. O trabalho não é difícil — é repetitivo, e é sempre o
mesmo.

O Morpheus quer esse retrato na tela. **Não é substituir o terminal**: é encurtar os primeiros dez
minutos de todo chamado. Quem precisar de `kubectl` depois vai usar `kubectl`.

Vale notar a relação com o Ticket 02: a skill de triagem já reduz esses dez minutos para quem tem
um agente à mão. O dashboard resolve o mesmo problema para quem está olhando, não perguntando — e
serve como painel aberto ao lado durante o chamado.

## O corte de escopo que define o desenho

**Contexto corrente, e só ele.** O kubeconfig da estação de quem opera tem mais de um destino —
no caso real, `lattice-dev`, `lattice-stg` e `lattice-prod`, este último com credencial de leitura
restrita. A aplicação lê o contexto corrente e pronto: nada de seletor de cluster na tela, nada de
trocar destino sem sair da aplicação.

Quem quiser olhar outro cluster troca o contexto por fora, como já faz hoje. Isso é deliberado, não
preguiça: um seletor de cluster na tela é um botão que, num momento de pressa, aponta a pessoa para
produção achando que está em staging.

## O que precisa aparecer

| Objeto | O que mostrar | Por que importa |
|---|---|---|
| Namespaces | a lista | é o filtro principal de tudo |
| Pods | estado, contagem de reinícios, e o **motivo** quando em falha | é a camada que mais resolve triagem |
| Deployments | prontos sobre desejados | responde "está no ar?" antes de olhar pod |
| Services | se têm endpoint | um Service sem endpoint é falha invisível |
| Eventos | os recentes do namespace selecionado | contexto do que acabou de acontecer |

Mais filtro por namespace e busca por nome — um cluster do parque tem centenas de objetos, e rolar
a lista não é funcionalidade.

## As armadilhas de forma de dado

Três, e todas vêm da API responder por omissão em vez de por valor vazio:

1. **`Endpoints` sem endereço não traz o campo vazio — não traz o campo.** Código que espera lista
   vazia quebra; olho humano que procura `[]` não acha. A distinção entre ausência e vazio decide
   como o dashboard mostra "sem endpoint".
2. **`Deployment` não traz `readyReplicas` quando nenhuma réplica está pronta.** `0/3` precisa ser
   derivado de um campo ausente, não lido.
3. **Pod em `CrashLoopBackOff` continua com `phase: Running`.** Filtrar por fase esconde o
   problema; o estado de falha vive em `containerStatuses`, em `state.waiting.reason` e
   `lastState.terminated.reason`.

Há ainda uma decisão de durabilidade: o objeto `Endpoints` está a caminho da aposentadoria, e a
informação equivalente vive em `EndpointSlice`. Qual consumir é decisão registrada, não detalhe.

## O ambiente não colabora, e isso é o normal

Três cenários que precisam de comportamento definido, porque acontecem:

- **Cluster que não responde** — contexto apontando para um endereço fora do ar
- **Credencial expirada** — o cluster responde, a autenticação não passa
- **Permissão negada para um tipo de recurso enquanto os outros continuam acessíveis** — é o que
  acontece ao abrir com um contexto de leitura restrita como o `platform-ro`. O mais interessante
  dos três, porque o comportamento ingênuo (falhar tudo) é claramente errado: o dashboard deve
  mostrar o que conseguiu ler e dizer o que não conseguiu.

Tela em branco com stack trace no console não atende em nenhum dos três.

## O invariante

**Somente leitura.** Nenhum apply, delete ou scale. E aqui é mais sensível que no Ticket 03,
porque a aplicação fala com produção. A garantia precisa estar **visível no projeto**, não só na
intenção de quem escreveu — alguém abrindo o código tem que conseguir verificar isso sem ler tudo.

## O que fica de fora desta fatia

- Multicluster e seletor de contexto na tela
- Qualquer escrita: editar, escalar, reiniciar, deletar
- Logs de container e terminal embutido
- Histórico e persistência — o dashboard mostra o agora
- Autenticação própria; quem abre já tem kubeconfig, e é essa a credencial
