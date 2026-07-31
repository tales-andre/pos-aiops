# Elo 1 — Diagnóstico do estado atual

**Modelo:** Claude Sonnet 5 via claude.ai · thinking level Medium.

## Entrada

`{{ESTADO_ATUAL_FORGE}}`:

```text
Forge hoje:
- ingestão: um job em cron acorda a cada 60min (o "forge-batch-ingest")
- transformação: 14 etapas de processamento encadeadas (em Spark), ~40min no total
- destino: grava em tabelas no data warehouse, particionadas por hora
- ponto frágil: se um lote falha, o próximo acumula o dobro de volume
- quem depende do Forge: Sentinel (lê as tabelas agregadas), Cerebro (indexa
  os eventos transformados) e os relatórios de billing da Pepper (rodam de madrugada)
```

`{{REQUISITOS_MIGRACAO}}`:

```text
O que a migração precisa garantir:
- consumir do Relay continuamente, processando em pequenos blocos no lugar do lote de 1h
- manter quem depende do Forge funcionando durante a transição
- nada de virada única (big-bang): a migração tem que ir em passos e poder voltar atrás
```

## Saída do modelo (diagnóstico)

1. MAPA DA CADEIA ATUAL

| estágio | mecanismo | garantia hoje oferecida |
|---|---|---|
| Ingestão | job em cron que acorda a cada 60min ("forge-batch-ingest") | disparo em intervalo fixo de tempo (agendamento); nenhuma garantia de completude ou idempotência é descrita no estado atual — NÃO DECIDÍVEL se há proteção contra reprocessamento |
| Transformação | 14 etapas encadeadas em Spark, ~40min no total | ordem de execução sequencial dentro de uma mesma execução batch; nenhuma garantia de atomicidade entre etapas é relatada |
| Escrita | grava em tabelas no data warehouse, particionadas por hora | particionamento por hora como unidade de organização do dado; atomicidade da escrita (commit único da partição vs. escrita incremental) é NÃO DECIDÍVEL — não relatada |
| Consumo | Sentinel, Cerebro e relatórios de billing da Pepper leem as tabelas/eventos produzidos | nenhuma garantia de sincronização entre escrita e leitura é descrita; cada consumidor tem expectativa própria (ver seção 2) |

2. CONSUMIDORES E SUAS SUPOSIÇÕES

| consumidor | o que lê | frequência esperada | suposição que quebra em modelo contínuo |
|---|---|---|---|
| Sentinel | tabelas agregadas (dado explícito: "lê as tabelas agregadas") | NÃO DECIDÍVEL — não informada | assume que a agregação corresponde a uma hora fechada e completa; num modelo de blocos contínuos não há "hora fechada" a menos que se defina um watermark equivalente |
| Cerebro | eventos transformados, para indexação (dado explícito: "indexa os eventos transformados") | NÃO DECIDÍVEL — não informada | assume um conjunto de eventos já transformado e estável para indexar; em processamento contínuo o evento chega antes de qualquer noção de "lote fechado", o que pode quebrar a suposição de ordem/completude no momento da indexação — NÃO DECIDÍVEL se Cerebro exige ordem de chegada, pois isso não é relatado |
| Relatórios de billing (Pepper) | tabelas do data warehouse (mesmas tabelas particionadas por hora), rodando de madrugada (dado explícito: "rodam de madrugada") | diária, em horário fixo de madrugada | assume que, no horário em que rodam, todas as partições-hora relevantes já estão fechadas e estáveis (não vão mais mudar); em modelo contínuo não existe esse instante de corte natural — a hora "nunca fecha" |

3. ACOPLAMENTOS IMPLÍCITOS

- **Particionamento por hora como unidade transacional**: as tabelas são "particionadas por hora" — isso é usado, na prática, como a unidade que os relatórios de billing tratam como estável, já que rodam de madrugada esperando dados fechados; o mecanismo exato do acoplamento é a coincidência entre o intervalo de ingestão (60min) e o grão de partição (hora).
- **Cron como sinal implícito de fechamento**: o disparo do "forge-batch-ingest" a cada 60min é o único mecanismo relatado que define quando um período de dados é considerado "pronto"; não há watermark ou sinal de completude independente do agendamento.
- **Acúmulo em dobro após falha, acoplado ao ciclo fixo de 60min**: o ponto frágil relatado ("se um lote falha, o próximo acumula o dobro de volume") mostra que o desenho assume implicitamente que cada execução processa um volume de ~1 hora; a unidade de trabalho está amarrada ao intervalo do cron, não ao volume real de dados.
- **Cadeia de 14 etapas como bloco único de ~40min**: as etapas são descritas como "encadeadas", ou seja, o desenho atual trata a transformação como uma unidade sequencial só concluída ao final das 14 etapas — não há indicação de que etapas intermediárias produzam saída consumível antes do fim da cadeia.

4. CLASSIFICAÇÃO DOS 14 ESTÁGIOS

| estágio (ou grupo de estágios) | classificação | justificativa |
|---|---|---|
| As 14 etapas de transformação (individualmente) | NÃO DECIDÍVEL | o estado atual só informa que existem "14 etapas de processamento encadeadas (em Spark), ~40min no total"; não há nome, função ou tipo de operação (map/filter row-wise vs. agregação/window/join que exige o lote inteiro) de nenhuma etapa. Sem essa informação não é possível dizer se alguma etapa é holística, paralelizável ou mista. O que resolveria a ambiguidade: o DAG ou o código-fonte do job Spark, identificando quais etapas fazem groupBy/window/join contra o lote completo e quais operam evento a evento |
| A cadeia como um todo (as 14 etapas em conjunto) | NÃO DECIDÍVEL | mesmo agregando, o estado atual não diz se o resultado final depende de alguma agregação sobre a janela de 1h (o que a tornaria holística) ou se é apenas uma sequência de transformações independentes por evento (o que a tornaria paralelizável). O que resolveria: descrição funcional de ao menos a etapa final, que é a que determina a forma do dado escrito na partição-hora |

5. MODOS DE FALHA HERDADOS

- **Acúmulo em dobro após falha** (explicitamente relatado): se um lote falha, o próximo ciclo de 60min processa o volume acumulado do período perdido mais o novo, dobrando o volume — cenário: falha isolada em uma execução, seguida do próximo disparo normal do cron.
- **Sobreposição de execuções (overlap) do cron**: como o volume pode dobrar após falha, uma execução que processa volume maior pode ultrapassar os 60min do próximo disparo — cenário: execução atrasada por acúmulo ainda rodando quando o cron dispara a próxima janela, sem que o estado atual descreva um mecanismo de exclusão mútua.
- **Leitura de partição em escrita parcial**: como a atomicidade da escrita na partição-hora é NÃO DECIDÍVEL, existe o risco de Sentinel, Cerebro ou os relatórios de billing lerem uma partição enquanto ela ainda está sendo escrita — cenário: falha ou atraso a meio da gravação de uma partição, coincidindo com o horário de leitura de um dos consumidores.
- **Falha a meio da cadeia de 14 etapas**: como as etapas são encadeadas e nenhuma garantia de atomicidade entre elas é relatada, uma falha na etapa N pode deixar resultado intermediário sem se propagar ou sem ser descartado de forma limpa — cenário: falha na etapa 8 de 14, sem informação sobre se há checkpoint/rollback.
- **Reprocessamento sem idempotência**: não há menção de mecanismo de replay ou de deduplicação; se o ciclo que falhou for reexecutado (ou se o próximo ciclo reabsorver o período perdido), não há garantia relatada de que os dados não sejam duplicados na partição-hora — cenário: reexecução manual ou automática de um período já parcialmente escrito.

6. PRÉ-REQUISITOS DE MIGRAÇÃO

1. **Capacidade de rodar os dois caminhos em paralelo (batch atual + novo caminho contínuo)** — bloqueante porque o requisito explícito de "nada de virada única" só é cumprível se o caminho atual continuar servindo os consumidores enquanto o novo é validado.
2. **Telemetria comparável entre os dois modelos** — bloqueante porque, sem uma métrica equivalente entre o resultado do batch e o do processamento contínuo, não há como afirmar que a migração preserva o comportamento que Sentinel, Cerebro e Pepper hoje dependem.
3. **Mecanismo de detecção de divergência entre as duas saídas** — bloqueante para decidir, em cada passo da migração, se é seguro avançar ou se é preciso voltar atrás, cumprindo o requisito de reversibilidade.
4. **Definição de um sinal de "fechamento" equivalente ao fechamento de hora, para cada consumidor** — bloqueante porque Sentinel e os relatórios de billing da Pepper hoje dependem de uma hora fechada e estável (seção 2); sem um substituto explícito (ex.: algum tipo de watermark), a suposição desses consumidores quebra assim que o dado passar a chegar em blocos contínuos.
5. **Esclarecimento da atomicidade de escrita hoje existente na partição-hora** — bloqueante porque, sendo hoje NÃO DECIDÍVEL, não dá para desenhar nem validar paridade de comportamento no novo modelo sem antes saber a garantia real que está sendo substituída.
6. **Garantia de idempotência/replay no que for construído** — bloqueante para que a migração possa "voltar atrás" sem risco de duplicar ou perder dados durante os passos intermediários, dado que esse mecanismo não é relatado como existente hoje.

7. LACUNAS DE DIAGNÓSTICO

| o que falta saber | por que impede concluir | como descobrir |
|---|---|---|
| Nome e lógica de cada uma das 14 etapas do Spark job (quais fazem agregação/window/join sobre o lote inteiro, quais operam evento a evento) | impede classificar cada estágio como holístico, paralelizável ou não decidível (seção 4) | inspecionar o código-fonte ou o DAG de execução do job, listando o tipo de operação (map/filter vs. groupBy/window/join) de cada etapa |
| Atomicidade da escrita na tabela particionada por hora (overwrite atômico da partição vs. escrita incremental) | impede avaliar se há hoje risco de leitura parcial e se o modelo de partição-hora pode ser reaproveitado como unidade de commit no novo modelo | checar a implementação/configuração da escrita no data warehouse (modo de escrita, se existe staging + swap atômico, etc.) |
| Frequência real de leitura esperada por Sentinel e por Cerebro | impede definir um SLA de "fechamento" equivalente no modelo contínuo (pré-requisito 4) | levantar contratos de consumo, configuração de polling ou logs de acesso desses dois sistemas às tabelas/eventos do Forge |
| Existência (ou ausência) de mecanismo de idempotência/replay no "forge-batch-ingest" atual | impede avaliar o risco real de duplicação ao reexecutar ou ao herdar volume acumulado | revisar o código de ingestão e o histórico de incidentes ligados a reprocessamento |
| Horário exato e recorte de dado usado pelos relatórios de billing da Pepper | impede garantir que um corte contínuo de dado não quebra o fechamento contábil que hoje depende de "rodar de madrugada" sobre dado estável | consultar a especificação/configuração de agendamento e a query-fonte desses relatórios |
| Definição precisa do "dobro de volume" no ponto frágil relatado (dobro de eventos, dobro de tempo de processamento, ou ambos) | impede quantificar o problema de backpressure que qualquer novo desenho precisa encarar | levantar métricas históricas de execução (volume processado e duração) do "forge-batch-ingest" em execuções normais e em execuções pós-falha |