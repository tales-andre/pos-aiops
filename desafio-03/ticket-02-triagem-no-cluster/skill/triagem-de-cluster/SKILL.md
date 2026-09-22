---
name: triagem-de-cluster
description: Método de triagem para workload que já existe no cluster Kubernetes do parque e está emitindo sinal de falha — pod que reinicia, deployment que não fica pronto, Service já aplicado que não entrega tráfego (sem endpoints, 502, timeout), cliente relatando que está fora do ar. Use sempre que o objeto já existir no cluster e houver sintoma observado ao vivo, inclusive quando vier como alerta de monitoramento, chamado de plantão ou frase solta do tipo "o pod do nyx-prod não sobe" ou "por que esse deployment está 0/3". A triagem só lê o cluster e para quando encontra a causa; ela não aplica correção. Não use quando o objeto ainda não existe no cluster — arquivo de manifesto a escrever, revisar, ou cujo apply foi rejeitado pela API — nem para pergunta conceitual sem incidente associado.
---

# Triagem de cluster

No parque, o alerta acusa o sintoma e a triagem varia por pessoa: um começa pelos eventos, outro
pelos logs, quem entrou mês passado começa por onde der. Isso é folclore de plantão, e folclore
não escala. Esta skill fixa o método.

O alcance ao cluster vem do `mcp-server-kubernetes` ou do `kubectl` direto. O que falta nunca é
braço — é critério.

## O limite que não se negocia

**A triagem lê. Nunca escreve.** Nenhuma correção é aplicada por iniciativa própria, mesmo quando
a ferramenta permite — e ela permite: a flag `ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS` do
`mcp-server-kubernetes` remove `kubectl_delete`, `cleanup`, `kubectl_generic`, `node_management` e
`uninstall_helm_chart`, mas **mantém** `kubectl_apply`, `kubectl_create`, `kubectl_patch`,
`kubectl_scale`, `kubectl_rollout` e `exec_in_pod`. Não-destrutivo não é somente-leitura.

A garantia real vem de três camadas, e você depende das três:

1. O script `scripts/snapshot.py` só aceita o verbo `get` — qualquer outro levanta erro.
2. Ao usar o MCP, restrinja-se a `kubectl_get`, `kubectl_describe`, `kubectl_logs`,
   `explain_resource` e `list_api_resources`.
3. Quando a causa exigir mudança, **escreva o que fazer e entregue para um humano decidir**.
   Triagem que conserta esconde a causa: o sintoma some, ninguém aprende, e volta na semana
   seguinte.

Se o pedido for "conserta pra mim", responda com o diagnóstico e o comando sugerido, e diga que a
aplicação é decisão de quem está de plantão.

## Por onde começar, a partir do sintoma declarado

O sintoma que chega é sempre vago — "o cliente diz que está fora do ar". O que muda a porta de
entrada é o **verbo** que a pessoa usou:

| O que disseram | Porta de entrada | Por quê |
|---|---|---|
| "reinicia", "cai sozinho", "fica subindo e morrendo" | estado do container: `lastState.terminated` | a causa da morte está ali, e **não** nos eventos |
| "parou depois do deploy", "publicamos e quebrou" | estado do container: `state.waiting` + imagem declarada | a causa costuma estar fora do cluster, no registry |
| "não sobe", "fica 0/N", "não fica pronto" | condições do Deployment, depois o container | o Deployment diz o que falta antes de você caçar pod |
| "responde erro de fora", "ninguém chega nela", "503" | Service e Endpoints | se o pod está saudável, o problema não é o container |
| "está lento" | logs e recursos, mas confirme que há sintoma real antes | lentidão sem número é percepção, não chamado |

Rode primeiro o retrato completo — ele é barato e evita seis comandos:

```bash
python3 <skill>/scripts/snapshot.py <namespace>
```

Ele traz, em ordem: prontos/desejados, estado dos containers com `waiting` e `lastState`, recursos
declarados, eventos de Warning, coerência entre selector e rótulos, e o que está saudável ao lado.

## Em que ordem descer as camadas

Da declaração para a execução, parando assim que a causa aparecer:

1. **Declaração** — o que o Deployment pediu (réplicas, imagem, recursos, probes).
2. **Agendamento** — o pod foi agendado? Se ficou `Pending`, a causa é nó, quota ou afinidade, e
   nada abaixo importa.
3. **Container** — subiu? Morreu? Por quê? Esta é a camada que mais resolve e a mais pulada.
4. **Aplicação** — logs, e só agora. Log é caro de ler e quase nunca é onde a causa está quando o
   container sequer fica de pé.
5. **Rede** — Service, Endpoints, selector. Só faz sentido investigar aqui depois de saber que o
   pod está saudável.

Pular camada para baixo é o erro comum: ler log de container que está em `ImagePullBackOff` não
produz nada, porque o container nunca executou.

## Quando cruzar duas fontes em vez de aprofundar numa só

Aprofundar é o instinto; cruzar é o que resolve. Cruze quando:

- **Uma fonte diz "está bem" e o sintoma persiste.** Pod `Running` e `1/1` com o cliente
  reclamando é o caso clássico: a resposta está em outro objeto, não mais fundo no mesmo.
- **O objeto depende de metadado para achar outro.** Service acha pod por rótulo, e rótulo é
  texto. Compare `spec.selector` com os rótulos do template do pod, caractere por caractere.
- **A causa pode estar fora do cluster.** `ImagePullBackOff` é o cluster dizendo que tentou; se a
  tag existe ou não é pergunta para o registry.
- **O que quebrou tem vizinho saudável.** Se o banco sobe e a aplicação não, no mesmo namespace e
  com as mesmas credenciais, a diferença entre os dois é o caminho mais curto para a causa.

## Quando parar

**Identificada a causa, a triagem acabou.** Não siga para o conserto, não colete evidência extra
"por garantia", não abra o código da aplicação se a causa já é de configuração.

Você chegou à causa quando consegue escrever uma frase que liga o sintoma declarado a um fato
observado, sem "provavelmente". `OOMKilled` com `limits.memory: 24Mi` é causa. "Parece problema de
memória" não é.

Se depois de percorrer as cinco camadas não houver causa, o resultado honesto é dizer o que foi
descartado e o que falta olhar — e não produzir um palpite com cara de laudo.

## Formato do laudo

```markdown
# Triagem — <namespace>

**Sintoma declarado:** <o que disseram>
**Causa:** <uma frase, ligando sintoma a fato observado>

## Como cheguei
| Camada | O que olhei | O que encontrei |

## O que estava saudável ao lado
<o que descartei, e por isso não é a causa>

## Correção sugerida (não aplicada)
<o que fazer, e de quem é a decisão>
```

A seção do que está saudável não é enfeite: é ela que separa triagem de chute. Quem só mostra o
que quebrou não provou que olhou o resto.

## Referência

- `references/padroes-de-falha.md` — assinaturas de falha já observadas no parque, com o que cada
  uma parece na superfície e onde a causa realmente estava. Abra quando o retrato não for
  conclusivo de imediato.
