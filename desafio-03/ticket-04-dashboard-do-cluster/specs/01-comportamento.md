# Especificação de comportamento — dashboard do cluster

Descreve **o que** a aplicação faz, observável de fora. Decisões de **como** estão em
[`02-decisoes.md`](./02-decisoes.md).

## Invocação

A aplicação roda na máquina de quem opera, contra o kubeconfig da estação, sobre o contexto que
estiver corrente no momento em que ela sobe.

```
dashboard [--porta 8700]
```

Sem argumento de cluster, sem argumento de contexto. Trocar de cluster é trocar o contexto por
fora e reiniciar.

## O invariante

**Somente leitura.** Nenhuma operação de escrita: sem `apply`, `delete`, `scale`, `patch` ou
`exec`. A garantia precisa estar **visível no projeto** — um único ponto de passagem para o
apiserver, com a lista de verbos permitidos explícita nele, de modo que alguém verifique lendo uma
função e não o código inteiro.

## O que a tela mostra

Cabeçalho fixo com o **contexto corrente e o servidor**, sempre visível. Numa ferramenta que só
lê, saber para onde se está olhando é a informação mais importante da tela.

| Painel | Conteúdo | Regra de exibição |
|---|---|---|
| Namespaces | lista, com o selecionado destacado | serve de filtro para todos os outros painéis |
| Deployments | nome, prontos/desejados | `0/3` quando `readyReplicas` estiver **ausente**, não zero |
| Pods | nome, estado, reinícios, motivo quando em falha | o motivo vem de `state.waiting.reason` ou `lastState.terminated.reason`, nunca de `phase` |
| Services | nome, tipo, portas, **se tem endpoint** | "sem endpoint" quando não há endereço, distinguindo ausência de campo de lista vazia |
| Eventos | tipo, motivo, objeto, mensagem, idade | só do namespace selecionado, `Warning` primeiro |

Mais **filtro por namespace** e **busca por nome**, que se aplicam aos painéis de objetos.

### As três armadilhas de forma de dado

São requisito de comportamento, não detalhe de implementação:

1. **Pod em `CrashLoopBackOff` tem `phase: Running`.** A tela mostra o estado do *container*, não
   a fase do pod. Um pod reiniciando em laço nunca aparece como "Running" sem qualificação.
2. **`Deployment` sem réplica pronta não traz `readyReplicas`.** A ausência é lida como zero.
3. **Service sem endpoint não traz o campo de endereços vazio — não traz o campo.** A tela
   distingue "sem endpoint" de "não consegui ler".

## Quando o ambiente não colabora

| Cenário | Comportamento exigido |
|---|---|
| Cluster não responde | a tela carrega, mostra o contexto e o erro em linguagem clara, com o endereço tentado; oferece nova tentativa |
| Credencial expirada ou inválida | mensagem distinta de "fora do ar", porque a ação de quem lê é outra |
| Permissão negada para **um** tipo de recurso | os painéis acessíveis continuam funcionando; o painel negado mostra "sem permissão para ler <recurso>" |
| Namespace sem objetos | "nenhum objeto", distinto de erro |

O terceiro é o mais importante: falhar a tela inteira porque um recurso deu `403` é o
comportamento ingênuo, e é justamente o que acontece ao abrir com um contexto de leitura restrita.

**Nunca:** tela em branco, stack trace na interface, ou erro silencioso que pareça lista vazia.

## Atualização

A tela reflete o estado do cluster com atraso declarado e visível. O relógio de "atualizado há X"
fica na tela, e existe atualização manual. A estratégia escolhida e o que ela custa estão em
`02-decisoes.md`.

## Critérios de aceite

1. Sobe contra o contexto corrente e mostra qual é, sem receber argumento de cluster.
2. Lista namespaces, e selecionar um filtra os demais painéis.
3. Um Deployment sem réplica pronta aparece como `0/N`, não em branco.
4. Um pod em `CrashLoopBackOff` aparece com o motivo da falha, não como "Running".
5. Um Service sem endpoint aparece marcado como tal, distinto de erro de leitura.
6. Com o cluster fora do ar, a tela carrega e explica; não fica em branco.
7. Com permissão negada para um recurso, os outros painéis continuam funcionando.
8. Busca por nome e filtro por namespace funcionam sobre os painéis de objetos.
9. Nenhum caminho de código alcança verbo de escrita — verificável em um único ponto do projeto.
