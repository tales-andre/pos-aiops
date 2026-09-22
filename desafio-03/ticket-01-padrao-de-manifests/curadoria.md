# Curadoria da skill

## Onde tracei a linha entre script e instrução

O critério foi um só: **a regra se decide lendo apenas o YAML, ou precisa do projeto?**

Se a resposta está inteira no manifesto, é script — e script é melhor que instrução aí, porque não
varia entre execuções, não gasta contexto e serve em pipeline. Se a resposta depende de saber o
que a aplicação faz, nenhum script alcança, e vira instrução.

Antes das duas, uma terceira pergunta: o `trivy config` já cobre? A fronteira com o Trivy foi
estabelecida rodando a ferramenta sobre o manifesto barrado, não supondo — 18 achados que
colapsam em 4 regras do padrão. Saída em [`execucoes/00-trivy-baseline.txt`](./execucoes/00-trivy-baseline.txt).

### Regra a regra

| Regra | Força | Destino | Por quê |
|---|---|---|---|
| 1.1 nome em kebab-case | obrigatório | Script | regex sobre `metadata.name` |
| 1.2 namespace `<cliente>-<ambiente>` | obrigatório | Script | regex + lista fechada `dev\|stg\|prod` |
| 1.3 os 4 rótulos `app.kubernetes.io/*` | obrigatório | Script + Instrução | presença das chaves é script; o valor de `part-of` e `instance` exige saber qual projeto é |
| 1.4 selector idêntico aos rótulos do pod | obrigatório | Script | comparação de dicionários; é o erro mais silencioso do parque |
| 1.5 anotações de dono e runbook | recomendado | Instrução | qual time é dono não está no YAML |
| 1.6 nome do container = componente | recomendado | Instrução | exige saber qual é o componente |
| 2.1 requests e limits | obrigatório | Trivy | KSV-0011, 0015, 0016, 0018 |
| 2.1b limits entre 1,5x e 2x o consumo | regra de bolso | Instrução | exige consumo observado em regime |
| 2.2 readiness e liveness | obrigatório | Script + Instrução | presença é script; para onde apontam exige ler o projeto |
| 2.3 `replicas >= 2` em prod | obrigatório | Script | deriva o ambiente do namespace e compara |
| 2.4 `RollingUpdate` 0/1 em prod | obrigatório em prod | Script | comparação literal de campos |
| 2.5 PodDisruptionBudget em prod | recomendado | Script | exige o conjunto de manifests, mas continua mecânico |
| 2.6 `terminationGracePeriodSeconds` | recomendado | Instrução | exige saber se a app drena e quanto leva |
| 3.1 tag `:latest` | proibido | Trivy | KSV-0013 |
| 3.2 securityContext | obrigatório | Trivy | KSV-0001, 0003, 0004, 0012, 0014, 0020, 0106, 0118 |
| 3.2b `emptyDir` nos caminhos de escrita | obrigatório | Instrução | quais caminhos a app escreve só se descobre no projeto |
| 3.3 segredo em texto puro | proibido | Script | heurística sobre `env[].value`; o `trivy config` **não** pegou a senha |
| 3.4 `automountServiceAccountToken: false` | obrigatório | Script + Instrução | presença é script; decidir *se* fala com a API exige o projeto |
| 3.5 ServiceAccount dedicada | recomendado | Script + Instrução | não usar a `default` é script; RBAC mínimo exige o projeto |
| 3.6 `hostNetwork`/`hostPID`/`privileged` | proibido | Script | provavelmente coberto pelo Trivy, mas o manifesto barrado não viola nenhum dos três, então não houve achado. Sem execução que prove, ficou no escopo da skill |
| 3.7 imagem só do registry interno | obrigatório | Script | o KSV-0125 dispara, mas com o critério **invertido** — ver abaixo |

**Contagem:** 3 para o Trivy, 9 para script puro, 4 partidas entre script e instrução, 5 só de
instrução, e o Bloco 4 inteiro fora.

### As regras que se partem ao meio

Quatro regras não cabem num destino só, e essa é a parte interessante da linha. Na 2.2, a
**presença** das duas probes é script; **para onde elas apontam** é instrução. Na 1.3, a presença
dos quatro rótulos é script; o **valor** de `part-of` e `instance` é instrução. O mesmo vale para
3.4 e 3.5. Tratar essas regras como inteiramente mecânicas produziria manifesto que passa no
script e quebra no cluster.

### O falso positivo do Trivy na 3.7

O `KSV-0125` acusa "untrusted registry" contra `registry.metacortex.io`, que é justamente o único
registry que o padrão aceita. O critério dele é o oposto do nosso, então a regra não pôde ser
delegada e ficou no script. O corpo da skill avisa para ignorar esse achado.

## O que ficou no corpo

Só o que é necessário para começar qualquer uma das duas tarefas:

- **A divisão em três camadas**, com o porquê de o script não reimplementar o Trivy. Sem isso, a
  primeira reação de quem usa a skill é reescrever as regras de segurança à mão.
- **Os dois modos**, em passos.
- **A tabela "o que perguntar ao projeto"** — onze perguntas sem resposta no YAML. É o núcleo da
  parte de julgamento, e por isso não foi para arquivo externo: se ela não estiver em contexto
  desde o início, a conferência vira listagem de campos faltando.
- **O formato do relatório**, para que quem lê consiga agir sem reabrir o padrão.
- **O aviso sobre o `KSV-0125`**, porque aparece em toda execução — num arquivo sob demanda, o
  agente tropeçaria nele antes de saber que há explicação.

O corpo tem 147 linhas.

## O que virou arquivo consultado sob demanda

- **`references/padrao.md`** (174 linhas) — o texto literal das regras com a força de cada uma.
  Não é necessário para trabalhar: o script já diz o que está errado. É necessário na hora de
  explicar o barramento a quem o recebeu, ou de decidir se um desvio admite exceção. Carregar isso
  sempre gastaria contexto em tarefa que não precisa.
- **`references/decisoes-conhecidas.md`** (101 linhas) — seis impasses já resolvidos, com o que
  foi descartado e o custo de cada escolha. Só vale a leitura quando o projeto cai num dos casos.

O `SKILL.md` aponta para os dois dizendo **quando** abrir, não só que existem — ponteiro sem
gatilho tende a não ser seguido.

## O que decidi não empacotar

1. **O Bloco 4 inteiro do padrão** — o glossário de Pod, ReplicaSet, Deployment, Service,
   Endpoints, ConfigMap/Secret e probes. É material de onboarding para quem está chegando na
   plataforma. Empacotar gastaria contexto ensinando ao agente o que ele já sabe, e o próprio
   padrão dispensa ao dizer que quem já opera os clusters pode pular esse bloco.

2. **As regras que o Trivy cobre** — 2.1, 3.1 e 3.2. Não por serem menos importantes: a 3.1 é
   `proibido`. É que manter duas verdades sobre a mesma regra é como um padrão começa a divergir
   de si mesmo, e o catálogo do Trivy é mantido por quem faz isso em tempo integral. A skill manda
   rodar a ferramenta e integra o resultado no mesmo relatório.

3. **Correção automática.** A skill confere e relata; não reescreve manifesto de ninguém. Parte
   dos desvios não tem conserto no YAML — credencial já comitada precisa de rotação, criação de
   schema no import precisa de mudança no código. Uma skill que "arruma" esses casos produz
   manifesto limpo sobre problema intacto.

4. **Qualquer coisa sobre cluster rodando.** Diagnóstico de workload em execução é outro problema,
   com outro alcance e outro risco.

## Quais permissões a skill pede

- **Leitura** dos manifests e do repositório da aplicação que está sendo empacotada.
- **Execução** de dois comandos: `trivy config <caminho>` e
  `python3 scripts/conferir_manifests.py <caminho>` (requer PyYAML). Ambos leem arquivos e
  escrevem só na saída padrão.
- **Escrita** de arquivos apenas no modo escrita, e apenas dos manifests que ela produz.
- **Nenhum acesso a cluster.** A skill não lê nem escreve em cluster nenhum, não precisa de
  kubeconfig e não usa o MCP de Kubernetes. Ela trabalha sobre arquivos, do lado de cá da revisão.

O corte em não tocar cluster é deliberado: as duas ferramentas que ela executa são determinísticas
e locais, então a skill inteira roda sem credencial de infraestrutura. Isso a torna segura de
instalar em qualquer máquina do time e de rodar em pipeline de PR.
