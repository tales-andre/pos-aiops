# A skill melhora o resultado ou só custa token?

Dois casos medidos, cada um rodado duas vezes em sessão limpa: uma com a skill instalada, outra
sem nada. Mesmo prompt de chamado, mesmo cluster, mesmo estado. Números crus em
[`medicao-com-e-sem-skill.json`](./medicao-com-e-sem-skill.json).

## Os números

| Caso | Config | Achou a causa | Chamadas | Tokens | Duração |
|---|---|---|---|---|---|
| Chamado 1 — OOM em nyx-prod | **com skill** | sim | **13** | 80.425 | **209 s** |
| Chamado 1 — OOM em nyx-prod | sem skill | sim | 18 | 79.983 | 270 s |
| Chamado 3 — selector em nyx-stg | **com skill** | sim | **12** | **65.120** | **137 s** |
| Chamado 3 — selector em nyx-stg | sem skill | sim | 14 | 75.342 | 215 s |

Com skill: **−23% e −36% de tempo**, **−28% e −14% de chamadas**. Tokens empatam no chamado 1 e
caem 14% no chamado 3.

## A resposta honesta: sem skill também achou

Nos dois casos medidos, o agente sem skill chegou **à mesma causa**. Um modelo capaz com `kubectl`
na mão resolve OOM e selector divergente sem método escrito. Quem esperava a skill ser a diferença
entre achar e não achar está com a expectativa errada.

E em um dos casos o baseline foi **mais fundo**: sem skill, o agente descobriu que não havia
`metrics-server`, entrou no container equivalente em staging e leu o cgroup para medir o consumo
real — 34 MiB contra o limite de 24 MiB. Isso é melhor que o laudo com skill, que parou em
"OOMKilled contra 24Mi" sem número medido.

Isso não é acidente: é a regra **"identificada a causa, a triagem acabou"** funcionando como
escrito. A skill fez o agente parar mais cedo — que é o comportamento pedido, com um custo que
agora está medido.

## Onde a skill ganha de verdade

**1. Consistência, que era o problema declarado.** A Trinity não pediu "que alguém ache a causa";
pediu que a triagem parasse de variar por pessoa. As três execuções com skill percorreram as mesmas
camadas na mesma ordem e produziram laudos no mesmo formato. As sem skill produziram estruturas
diferentes entre si, cada uma com a organização que aquele agente achou boa naquele momento.

**2. Velocidade, que em plantão é o que importa.** 36% a menos de tempo no chamado 3. O
`snapshot.py` entrega numa chamada o que o agente sem skill montou em seis.

**3. Segurança — e este é o achado que mais importa.** O agente **sem skill usou `kubectl exec`**
dentro de um container para ler o cgroup. Usou com responsabilidade, em staging e não em produção,
e obteve um dado melhor por causa disso. Mas `exec` é verbo de escrita: nada no ambiente o impedia
de rodar em produção, e nada o impediria de aplicar um patch se tivesse concluído que era o certo.

A skill fecha isso em três camadas — o `snapshot.py` só aceita `get`, o corpo restringe as
ferramentas do MCP às de leitura, e a regra "escreva o que fazer e entregue para um humano" é
explícita. As três execuções com skill não tocaram em nenhum verbo de escrita.

**4. Ela desviou de uma armadilha real.** Os eventos de Warning do `nyx-prod` apontam para
`ImagePullBackOff` de um ReplicaSet de revisão anterior, já zerado. Quem começa a triagem pelos
eventos — o hábito do Dozer — fecha o chamado na causa errada. A skill manda começar pelo estado do
container justamente por isso, e as três execuções com skill sinalizaram o ruído em vez de cair
nele.

## Veredito

A skill **não** compra capacidade de diagnóstico. Compra **método repetível, tempo e um limite de
escrita que não depende da boa vontade de quem está rodando**.

Para um plantão onde a pergunta é "o Dozer e o novato chegam à mesma resposta?", isso é exatamente
o que se queria comprar. Se a pergunta fosse "um agente consegue diagnosticar Kubernetes?", a
resposta seria que ele já conseguia e a skill seria só custo.

**Ajuste que a medição sugere:** a regra de parada está apertada demais. Vale acrescentar que,
quando a causa é de dimensionamento, medir o consumo real faz parte da causa — sem isso o laudo
entrega o diagnóstico e deixa o número para o plantonista adivinhar. Registrado como melhoria, não
aplicado nesta entrega, porque mudaria a skill depois da medição que a avaliou.
