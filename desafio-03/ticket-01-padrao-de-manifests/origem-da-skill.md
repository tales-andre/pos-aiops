# Origem da skill

## De qual fluxo nasceu

Do trabalho feito à mão, antes de existir qualquer skill — os mesmos dois usos que a skill hoje
cobre, executados manualmente uma vez cada:

- **Escrita** — empacotei o `fake-shop` (cliente orion, ambiente prod) do zero contra o padrão,
  lendo o código do projeto para resolver o que o padrão não respondia: a aplicação não expõe
  endpoint de saúde, roda migração no start, carrega a senha do banco em variável de ambiente e
  precisa escrever em disco apesar do `readOnlyRootFilesystem`.
- **Conferência** — conferi o manifesto barrado regra a regra, abrindo o `kube-news` para
  responder o que o YAML não respondia. Foi ali que ficou claro que as probes que faltam só se
  resolvem sabendo que `/ready` e `/health` existem na 8080 e que nenhum dos dois consulta o
  banco.

Os dois modos da skill existem porque foram esses os dois trabalhos que eu realmente fiz. Não
foram deduzidos da leitura do padrão.

O conteúdo da skill saiu direto desse fluxo:

| O que aconteceu no fluxo manual | O que virou na skill |
|---|---|
| Conferi kebab-case, namespace, rótulos, selector, replicas, strategy, registry e `env.value` lendo só o YAML | as checagens de `scripts/conferir_manifests.py` |
| Precisei abrir o projeto para decidir probe, migração, caminhos graváveis, componente e dono | a tabela "o que perguntar ao projeto" no corpo |
| Resolvi quatro impasses no fake-shop que o padrão não previa | `references/decisoes-conhecidas.md` |
| Reli o Bloco 4 e não usei nenhuma vez | ficou de fora |

## Por qual caminho

1. Li o padrão inteiro.
2. Rodei `trivy config` sobre o manifesto barrado para descobrir, executando e não supondo, o
   quanto o ferramental existente já cobre. Saída em
   [`execucoes/00-trivy-baseline.txt`](./execucoes/00-trivy-baseline.txt): 18 achados que
   colapsam em 4 regras do padrão.
3. Classifiquei cada regra em quatro destinos — Trivy, script, instrução, fora. O resultado está
   em [`curadoria.md`](./curadoria.md).
4. Fiz o trabalho à mão nos dois modos, sobre `fake-shop` e `kube-news`.
5. Empacotei o que tinha acabado de fazer.
6. Rodei a skill nos dois modos, em sessão limpa.

O passo 2 veio antes do 3 de propósito: sem execução real, a fronteira entre "o Trivy já pega" e
"a skill precisa pegar" seria chute, e a skill terminaria reimplementando catálogo pronto.

## Com qual ferramenta

- **Claude Code**, modelo Opus 5, com a skill `skill-creator` da Anthropic conduzindo a produção.
- Ferramental determinístico usado durante o fluxo: `trivy` 0.74.0 e Python 3.12 com PyYAML 6.0.1.
- As duas execuções do passo 6 rodaram em **sessões limpas**, com agentes sem nenhum contexto da
  conversa em que a skill foi escrita, recebendo apenas o caminho da skill e a tarefa. Foi assim
  de propósito: uma skill testada por quem a escreveu, na mesma sessão, testa a memória do autor,
  não a skill.

Do processo do `skill-creator` foram usadas a captura de intenção, a redação e a execução dos
casos de teste. O laço de avaliação quantitativa dele — baseline sem skill, benchmark, revisor
visual — não foi executado: o Ticket 01 pede a saída real das duas execuções, e a comparação com
e sem skill é o que o Ticket 02 pede.

## O que as execuções da skill mostraram

A conferência em sessão limpa encontrou três coisas que a conferência manual não tinha pegado:

1. O `DATABASE_URL` do manifesto barrado **não é lido** pelo `kube-news` — a aplicação usa
   `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD`, `DB_HOST` e `DB_PORT`. O manifesto vaza uma
   credencial e injeta uma variável ignorada ao mesmo tempo.
2. O `kube-news` também cria schema no start (`sync({alter: true})`), então corrigir 2.3 e 2.4
   cria a mesma corrida que existe no fake-shop.
3. O `healthMid` é registrado antes do router, então `PUT /unhealth` derruba readiness e liveness
   juntas.

E a escrita em sessão limpa apontou um limite da própria skill: a receita de
`decisoes-conhecidas.md` para migração no start pressupõe que ela esteja num entrypoint. No
`encontros-tech` o `create_all` roda no import do módulo, então sobrescrever `command` não
resolve — o Job reduz a corrida, não elimina. O agente não seguiu a receita cegamente porque o
corpo da skill explica o porquê de cada regra, e não só o que fazer.
