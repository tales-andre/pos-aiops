# Origem da skill de triagem

## De qual fluxo nasceu

Da triagem feita à mão nos três chamados, antes de existir skill. Evidência bruta em
[`execucoes/fluxo-manual-chamado-1.txt`](./execucoes/fluxo-manual-chamado-1.txt),
[`-2`](./execucoes/fluxo-manual-chamado-2.txt) e
[`-3`](./execucoes/fluxo-manual-chamado-3.txt).

Foi rodando os três que apareceu o que o método precisava fixar — e nenhum dos três achados
abaixo é dedutível da leitura do enunciado:

**1. Os eventos mentem por omissão.** No chamado 1, os eventos do namespace trazem só
`BackOff restarting failed container`. A causa — `OOMKilled`, `exitCode 137` — está apenas em
`status.containerStatuses[].lastState.terminated`. Quem começa pelos eventos, como é o hábito de
metade do time, não encontra e parte para os logs, que também não ajudam porque o processo morre
antes de escrever. Daí a tabela "por onde começar" ser indexada pelo **verbo do sintoma**, e não
pela ferramenta preferida de quem atende.

**2. O cluster às vezes só sabe que tentou.** No chamado 2, `ImagePullBackOff` é tudo que o
cluster tem. Se a tag existe ou não é pergunta para o registry, fora do cluster. Isso virou o
critério "quando cruzar duas fontes em vez de aprofundar numa só".

**3. Pod saudável é sinal de troca de camada, não de fim de investigação.** No chamado 3 os dois
pods estão `Running 1/1` e o cliente recebendo 503. Enquanto a atenção ficar no container não se
acha nada. Virou a regra de subir para a camada de rede assim que o container estiver íntegro.

E o que atravessa os três: **sempre havia algo saudável ao lado do que quebrou**. O Postgres
subiu nos três namespaces. Esse contraste é o caminho mais curto para a causa, e por isso o
`snapshot.py` tem uma seção só para ele.

## Por qual caminho

1. Subi um cluster local `kind` e apliquei os três ambientes do enunciado.
2. Descobri, rodando, que a imagem `kube-news:v1` só tem build `arm64` e não sobe em x86_64 — o
   que mascarava os defeitos plantados dos chamados 1 e 3 com um `ImagePullBackOff` falso. Troquei
   para `v1.0.0`, multi-arch. O chamado 2 manteve a tag original, porque ali a falha de pull **é**
   o defeito. Registrado em [`ambientes/README.md`](./ambientes/README.md).
3. Triei os três à mão, guardando a saída.
4. Levantei o que o `mcp-server-kubernetes` realmente expõe, por handshake MCP direto — ver
   [`execucoes/00-mcp-ferramentas.md`](./execucoes/00-mcp-ferramentas.md).
5. Empacotei o método no que tinha acabado de fazer.
6. Rodei a skill nos três chamados, em sessão limpa.
7. Medi com e sem skill, e testei o roteamento contra a outra skill.

## Com qual ferramenta

- **Claude Code**, modelo Opus 5.
- Cluster: `kind` v0.20.0 sobre Docker 29.1.3, dentro do WSL Ubuntu 24.04.
- Alcance ao cluster: `kubectl` v1.27 e `mcp-server-kubernetes` registrado em
  [`.mcp.json`](../../.mcp.json) na raiz do repositório, com
  `ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS=true` e `KUBECONFIG` apontando para o cluster de laboratório —
  nunca para o contexto de produção da estação.
- As três execuções do passo 6 e os dois baselines rodaram em **sessões limpas**, sem contexto da
  conversa em que a skill foi escrita.

## A que causa a skill chegou em cada chamado

| Chamado | Sintoma declarado | Causa encontrada | Laudo |
|---|---|---|---|
| 1 — `nyx-prod` | "a API reinicia sozinha" | `OOMKilled`, `exitCode 137`, contra `limits.memory: 24Mi` | [laudo](./execucoes/com-skill-chamado-1/laudo.md) |
| 2 — `orion-stg` | "parou depois da publicação, o pod nunca trocou" | tag `v1.14.2` inexistente no registry, confirmada por HTTP 404 no Docker Hub | [laudo](./execucoes/com-skill-chamado-2/laudo.md) |
| 3 — `nyx-stg` | "responde 503 para quem chama de fora" | selector do Service `app: nyx-api` contra rótulo do pod `app: nyxapi` | [laudo](./execucoes/com-skill-chamado-3/laudo.md) |

Duas execuções corrigiram o próprio enunciado do chamado, o que só é possível olhando o cluster:

- No chamado 2, "o pod nunca trocou" sugere versão anterior ainda servindo. Não é o caso: existe
  só a revisão 1, um único ReplicaSet, e `Endpoints` vazio. A loja não está servindo versão velha
  — não está servindo nada, e não há rollback para onde voltar. Isso sobe a urgência do chamado.
- No chamado 1, a troca de tag que antecedeu o incidente **não introduziu** o defeito: o `24Mi`
  já estava lá desde a revisão 1, mascarado porque o pod sequer chegava a rodar.

## O que as execuções mostraram sobre a própria skill

O `references/padroes-de-falha.md` traz os três casos com as assinaturas certas — o que cria um
risco de a skill entregar a resposta em vez do método. Duas das três execuções registraram
explicitamente que **não** se apoiaram na referência como prova e verificaram cada fato no cluster
ao vivo. Isso funcionou aqui, mas é um risco a vigiar: um quarto chamado com sintoma parecido e
causa diferente é o teste que a skill ainda não passou.
