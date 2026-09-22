# Curadoria da skill de triagem

## O que o método fixou

Quatro coisas, e só quatro. Tudo que foi fixado é resposta a uma variação que eu observei nos três
chamados — não a uma preferência estética.

**1. A porta de entrada, indexada pelo verbo do sintoma.** "Reinicia" entra pelo estado do
container; "parou depois do deploy" entra pelo `waiting` e pela imagem; "ninguém chega nela" entra
por Service e Endpoints. Isso existe porque era exatamente aqui que o time divergia — o Dozer
começava pelos eventos, o Tank pelos logs. A tabela não é sugestão: começar pelo lugar errado no
chamado 1 leva a um `ImagePullBackOff` de um ReplicaSet já aposentado e fecha o chamado na causa
errada.

**2. A ordem das camadas: declaração, agendamento, container, aplicação, rede.** Com uma regra
explícita contra o erro mais comum, que é pular para o log. Container em `ImagePullBackOff` nunca
executou, então não tem log de aplicação — ler é desperdício garantido.

**3. Quando parar.** Identificada a causa, acabou. Com um teste concreto: você chegou à causa
quando consegue ligar sintoma a fato observado sem dizer "provavelmente".

**4. O formato do laudo**, incluindo a seção obrigatória do que estava saudável ao lado. Essa
seção não é enfeite — é ela que prova que houve descarte, e é o que separa triagem de chute.

## O que deixei o agente decidir

**Quais comandos rodar depois do retrato inicial.** O `snapshot.py` entrega a base; daí em diante
o agente escolhe. Nas três execuções ele escolheu diferente, e todas as três escolhas foram boas:
no chamado 2 foi consultar a API do Docker Hub, no 3 foi usar o proxy da API do Kubernetes para
reproduzir o 503, no 1 foi comparar o `resources` do que quebrou com o do vizinho saudável.
Nenhuma dessas estava escrita na skill. Prescrever a sequência exata teria impedido as três.

**Quanto aprofundar antes de concluir.** A regra diz quando parar, não quantas evidências juntar.

**Como redigir a correção sugerida.** A skill exige que exista e que não seja aplicada; o conteúdo
é julgamento. As três execuções produziram recomendações diferentes em forma, e uma delas
acrescentou espontaneamente que corrigir só no cluster faz o defeito voltar no próximo `apply` do
pipeline — observação que a skill não pedia e que melhora o laudo.

**O que é ruído.** A skill avisa que eventos podem enganar, mas não lista quais ignorar. As três
execuções identificaram sozinhas que os Warnings do ReplicaSet antigo eram irrelevantes.

## O que deliberadamente não entrou

- **Um catálogo de causas por sintoma.** O `padroes-de-falha.md` tem três assinaturas, e esse é o
  teto. Uma tabela grande de "sintoma X → causa Y" faria o agente casar padrão em vez de
  investigar, e o quarto chamado do parque não vai estar na tabela.
- **Correção automática**, por decisão, não por limitação. Ver a seção seguinte.
- **Instrução sobre a aplicação.** Onde ficam os logs do kube-news, qual o endpoint de saúde do
  fake-shop — nada disso está aqui. É conhecimento de manifesto, e mora na outra skill.

## Como garantiu que a skill não escreve no cluster

Esta é a parte em que a resposta óbvia estava errada, e descobri rodando.

**O que não garante nada sozinho:** a flag `ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS=true` do
`mcp-server-kubernetes`. Levantei o que ela faz por handshake MCP direto contra o servidor, com e
sem a flag — resultado em [`execucoes/00-mcp-ferramentas.md`](./execucoes/00-mcp-ferramentas.md).
Ela remove **5** das 24 ferramentas: `kubectl_delete`, `cleanup`, `kubectl_generic`,
`node_management` e `uninstall_helm_chart`.

Continuam expostas, e escrevem no cluster: `kubectl_apply`, `kubectl_create`, `kubectl_patch`,
`kubectl_scale`, `kubectl_rollout`, `exec_in_pod`, `install_helm_chart`, `upgrade_helm_chart` e
`port_forward`.

**Não-destrutivo não é somente-leitura.** O enunciado trata a flag como se fosse a garantia; ela
não é. A garantia teve que ser construída em três camadas:

| Camada | O que faz | Onde |
|---|---|---|
| Ferramenta | `snapshot.py` valida o verbo e só aceita `get`; qualquer outro levanta `RuntimeError` | `scripts/snapshot.py`, função `_kubectl` |
| Instrução | o corpo lista as ferramentas do MCP permitidas e nomeia as que escrevem, para que a exclusão seja consciente | `SKILL.md`, seção "O limite que não se negocia" |
| Processo | correção é escrita no laudo e entregue a um humano; a skill diz explicitamente o que responder a "conserta pra mim" | `SKILL.md`, mesma seção |

**A prova de que funcionou não é a afirmação, é o contraste.** As três execuções com skill
usaram apenas `get` e `describe`. O baseline **sem** skill usou `kubectl exec` dentro de um
container para ler o cgroup — com responsabilidade, em staging, e obtendo um dado melhor por isso.
Mas nada no ambiente o impedia de fazer o mesmo em produção. A diferença entre os dois não foi a
permissão disponível: foi a instrução.

Vale registrar que a terceira camada é a mais frágil das três, porque depende do agente obedecer.
Se isso precisar virar garantia dura, o caminho é o `permissions.deny` do Claude Code ou um MCP
com as ferramentas de escrita realmente removidas — e não uma flag que promete mais do que
entrega.
