---
name: padrao-manifests-metacortex
description: Escreve e confere manifests Kubernetes contra o Padrão de Manifests da Metacortex — nomenclatura, rótulos, resiliência e segurança. Use sempre que alguém for criar, revisar ou corrigir manifesto Kubernetes de qualquer cliente do parque (Deployment, Service, Job, CronJob, ConfigMap, Secret), inclusive quando a pessoa apenas perguntar "esse manifesto está no padrão da casa?", pedir para empacotar uma aplicação para subir num cluster, ou relatar Service que não entrega tráfego. Vale mesmo quando o pedido não cita o padrão: todo manifesto que entra num cluster do parque passa por essa revisão, e é mais barato acertar antes do que ser barrado depois.
---

# Padrão de Manifests da Metacortex

Esta skill existe porque o padrão da casa é uma página de wiki longa demais para alguém abrir no
meio de uma tarefa e conferir regra por regra. O resultado previsível é manifesto subindo torto,
revisão barrando, e o ciclo recomeçando.

Dois modos, e o de conferência é o mais frequente — no parque se mexe em manifesto pronto o tempo
todo.

## Como o trabalho se divide

Três camadas, e misturá-las é o erro que faz a conferência ficar cara e incompleta.

| Camada | Cobre | Como |
|---|---|---|
| `trivy config` | regras 2.1, 3.1, 3.2, 3.6 — endurecimento de container | ferramenta pronta |
| `scripts/conferir_manifests.py` | regras 1.1, 1.2, 1.3, 1.4, 2.2 (presença), 2.3, 2.4, 2.5, 3.3, 3.4, 3.5, 3.7 | script deste pacote |
| julgamento | para onde a probe aponta, caminhos graváveis, dono, componente, dimensionamento | você, lendo o projeto |

As duas primeiras camadas são determinísticas: rode, não opine. O Trivy tem catálogo próprio de
más configurações de Kubernetes e faz isso melhor do que qualquer regra reescrita à mão — por
isso o script deliberadamente **não** reimplementa o que ele cobre. Duas verdades sobre a mesma
regra é como um padrão começa a divergir de si mesmo.

A terceira camada é a única que precisa de você, e é a que justifica esta skill existir. Nenhuma
ferramenta lê o código da aplicação para descobrir que ela não expõe `/health`.

**Um aviso sobre o Trivy.** O achado `KSV-0125` ("untrusted registry") dispara contra
`registry.metacortex.io`, que é justamente o único registry que o padrão aceita. O critério dele é
o oposto do nosso. Ignore esse achado e confie no que o script diz sobre a regra 3.7.

## Modo conferência

Use quando existe manifesto e a pergunta é "isso passa na revisão?".

1. **Rode as duas ferramentas.**
   ```bash
   trivy config <caminho>
   python3 <skill>/scripts/conferir_manifests.py <caminho>
   ```
   O script sai com código 1 se algo barra, o que serve em pipeline.

2. **Descubra qual aplicação é.** O manifesto diz o nome e a imagem; o projeto diz o resto. Sem
   isso a conferência fica pela metade — dizer "faltam as probes" não é conferir, é listar. Abra
   o repositório da aplicação e responda as perguntas da seção
   [O que perguntar ao projeto](#o-que-perguntar-ao-projeto).

3. **Junte as três camadas num relatório só**, no formato abaixo.

4. **Classifique cada desvio pela força da regra**, não pela sua opinião sobre gravidade.
   `obrigatório` barra, `recomendado` pede justificativa no PR, `proibido` não admite exceção.
   Consulte `references/padrao.md` quando precisar citar a regra ou explicar o porquê dela.

## Modo escrita

Use quando a tarefa é empacotar uma aplicação que ainda não tem manifesto.

1. **Leia o projeto antes de escrever qualquer YAML.** Porta, endpoints, dependências, variáveis
   de ambiente, o que o entrypoint faz, o que a aplicação escreve em disco. Escrever primeiro e
   corrigir depois produz manifesto que passa no script e quebra no cluster.

2. **Resolva os pontos de julgamento**, com as perguntas da próxima seção. Se o caso já for
   conhecido — aplicação sem endpoint de saúde, migração no start, `readOnlyRootFilesystem`
   contra aplicação que escreve — leia `references/decisoes-conhecidas.md` antes de decidir do
   zero.

3. **Escreva os manifests.** Um Deployment sozinho quase nunca basta: o padrão puxa junto
   ServiceAccount dedicada (3.5), Service, e PDB em prod com mais de uma réplica (2.5).

4. **Confira o que você escreveu**, rodando o modo conferência sobre o próprio resultado. Isso
   pega o que a pressa esconde, especialmente a regra 1.4.

5. **Registre as decisões que você tomou** — as que o padrão não respondia. Quem mantiver esse
   manifesto daqui a um ano vai perguntar por que a probe aponta para `/metrics`, e o commit não
   responde.

## O que perguntar ao projeto

Estas perguntas não têm resposta no YAML. São elas que separam conferência de listagem.

| Pergunta | Regra que depende disso |
|---|---|
| Em que porta o processo escuta? | `targetPort`, probes |
| Existe endpoint de saúde? Ele consulta o banco? | 2.2 |
| Readiness e liveness podem apontar para lugares diferentes? | 2.2 |
| O entrypoint faz algo além de subir o servidor (migração, seed)? | 2.4, e o desenho do pacote |
| Quais caminhos a aplicação escreve em disco? | 3.2 (`readOnlyRootFilesystem`) |
| Ela conversa com o apiserver do Kubernetes? | 3.4, 3.5 |
| Quais variáveis carregam credencial? | 3.3 |
| Qual é o nome do componente — `api`, `worker`, `web`? | 1.3, 1.6 |
| Qual time é dono e existe runbook? | 1.5 |
| A aplicação trata SIGTERM e quanto tempo leva para drenar? | 2.6 |
| Há consumo observado em regime? | 2.1, a regra de bolso de 1,5x a 2x |

Quando não houver resposta — e frequentemente não haverá, para dimensionamento e dono — diga que
não há, em vez de inventar um valor. Um `resources` provisório declarado como provisório é
honesto; um chute apresentado como medida vira dado errado no inventário.

## Formato do relatório

Use esta estrutura na conferência. Ela existe para que quem lê consiga agir sem reabrir o padrão.

```markdown
# Conferência — <caminho>

Workload: <aplicação>, cliente <cliente>, ambiente <ambiente>

## Barra
| Regra | Força | Esperado | Encontrado |

## Justificar no PR
| Regra | Esperado | Encontrado |

## Conforme
<lista curta das regras atendidas>

## O que só se descobre abrindo o projeto
<as conclusões que vieram do código, com o arquivo e a linha>
```

Duas coisas que valem destaque sempre que aparecerem, porque são as mais caras e as menos
visíveis:

- **Regra 1.4.** O sintoma não aparece na revisão nem no `kubectl apply`. O Deployment fica
  `2/2`, o Service nunca entrega tráfego, e o objeto `Endpoints` não vem com lista vazia — o campo
  de endereços simplesmente não aparece.
- **Regra 3.3.** É `proibido`, e o Trivy não pega credencial embutida em manifesto. Se o valor já
  foi comitado, trocar para `secretKeyRef` não basta: a credencial precisa ser rotacionada.

## O que esta skill pede para rodar

- **Leitura** dos manifests e do repositório da aplicação.
- **Execução** de `trivy config` e de `python3 scripts/conferir_manifests.py` (precisa de PyYAML).
- **Nada de cluster.** A skill não lê nem escreve em cluster nenhum: ela trabalha sobre arquivos.
  Diagnóstico de workload rodando é outro assunto e outra skill.

## Referências

- `references/padrao.md` — o texto das regras, com a força de cada uma. Abra para citar a regra
  ou explicar o porquê dela a quem recebeu o barramento.
- `references/decisoes-conhecidas.md` — casos em que o padrão não tem resposta e alguém já
  decidiu, com o que foi descartado e o custo. Abra antes de decidir do zero.
