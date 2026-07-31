# Elo 2 — Estratégia de migração em fases

**Modelo:** Claude Sonnet 5 via claude.ai · thinking level Medium.

## Entrada

- `{{OUTPUT_ELO_1}}`: o diagnóstico completo do [Elo 1](./elo-1-diagnostico.md) (encadeamento).
- `{{REQUISITOS_MIGRACAO}}`: os mesmos requisitos da migração.

## Saída do modelo (estratégia em fases)

# 1. ORDEM DE MIGRAÇÃO E JUSTIFICATIVA

O diagnóstico classifica explicitamente apenas as 14 etapas de transformação (individualmente e como cadeia) como **NÃO DECIDÍVEL**. Por essa classificação, a transformação não pode ser a Fase 1, e nenhuma fase pode assumir se ela é holística ou paralelizável até a lacuna correspondente ser fechada (inspeção de código/DAG).

A ingestão (consumo do Relay) não está sujeita a essa classificação — não é uma das 14 etapas nem depende de saber se elas são holísticas. Por isso pode avançar primeiro, em paralelo, sem tocar na transformação.

A escrita depende de uma lacuna própria (atomicidade da partição-hora, NÃO DECIDÍVEL hoje), logo também não pode ser redesenhada antes dessa investigação.

O consumo é tratado por consumidor (regra 4), ordenado do mais tolerante ao mais sensível. Com base no que o diagnóstico relata explicitamente (não no que preenche por suposição): Sentinel depende de uma hora fechada para agregação (sem indicação de criticidade financeira); Cerebro tem uma suposição de ordem/completude marcada como NÃO DECIDÍVEL; Pepper depende de um corte diário fixo, de madrugada, para fechamento contábil — a suposição mais explícita e mais cara de quebrar. Ordem: **Sentinel → Cerebro → Pepper**.

Consequência direta: só existem, hoje, duas fases com estrutura completa (Fase 0 e Fase 1). Todas as demais dependem de lacunas do diagnóstico e são apresentadas como NÃO PRONTAS, com nome estável, para referência do próximo elo.

# 2. FASE 0 — FUNDAMENTOS E FECHAMENTO DE LACUNAS BLOQUEANTES

Antes de qualquer fase de migração, precisam existir:

- Infraestrutura para rodar o caminho batch atual e um novo caminho em paralelo, sem interferência mútua (pré-requisito 1 do diagnóstico).
- Telemetria comparável entre os dois caminhos (pré-requisito 2).
- Mecanismo de detecção de divergência entre as duas saídas, com limiar objetivo (pré-requisito 3) — é a peça que vai definir cutover em todas as fases seguintes.
- Design do mecanismo de idempotência/replay para o novo caminho (pré-requisito 6) — precisa existir antes da Fase 1, não depois, para não herdar o modo de falha de "dobro de volume".
- Definição conceitual de um sinal de fechamento (watermark) equivalente ao fechamento de hora (pré-requisito 4) — versão genérica aqui; o refinamento por consumidor específico fica para as fases de consumo.
- Investigação (não decisão) da atomicidade de escrita hoje existente na partição-hora — fecha a lacuna que bloqueia a Fase 3.
- Investigação (não decisão) do código/DAG das 14 etapas de transformação, identificando quais operam evento a evento e quais dependem do lote inteiro — fecha a lacuna que bloqueia a Fase 2.
- Levantamento da frequência real de leitura de Sentinel e Cerebro, e do horário/recorte exato dos relatórios da Pepper — fecha as lacunas que bloqueiam as Fases 4, 5 e 6.
- Quantificação do "dobro de volume" (eventos, tempo, ou ambos) no ponto frágil relatado — dimensiona o tratamento de falha parcial exigido na Fase 1.

Nenhuma dessas atividades decide o que o diagnóstico marcou como NÃO DECIDÍVEL; elas produzem a informação que falta para que a decisão possa ser tomada depois, pelo próximo elo ou por uma revisão deste.

# 3. FASES

## Fase 1 — Ingestão Contínua em Sombra

- **O que migra:** o mecanismo de ingestão — substitui o disparo por cron de 60min ("forge-batch-ingest") por um consumo contínuo do Relay em pequenos blocos.
- **Caminho autoritativo:** o cron atual, com todo o restante da cadeia (transformação, escrita, consumo) inalterado.
- **Caminho em sombra:** novo consumidor contínuo do Relay, escrevendo em um armazenamento intermediário próprio, separado das tabelas particionadas por hora — nenhum consumidor aponta para ele.
- **Consumidor(es) afetado(s):** nenhum diretamente; é validação de captação isolada.
- **Condição de cutover:** esta fase não promove nenhum caminho a autoritativo (não há transformação/escrita ainda do lado novo). O critério de saída da fase é: divergência de volume e latência entre o que o caminho contínuo capta e o que o cron captaria, abaixo do limiar definido na Fase 0, por um período mínimo observado via telemetria comparável.
- **Comportamento sob falha parcial:** uma falha no consumo de um bloco deve gerar replay apenas daquele bloco (via idempotência definida na Fase 0) — não pode se acumular no próximo bloco, o que herdaria o modo de falha de "dobro de volume" do cron atual.
- **Reversão:** desligar o consumidor contínuo e/ou parar de escrever no armazenamento intermediário; como nenhum consumidor real depende dele, a reversão não tem efeito colateral em produção.

# 4. DEPENDÊNCIAS ENTRE FASES

- Fase 1 depende de: telemetria comparável, mecanismo de divergência e design de idempotência da Fase 0 já existentes — sem eles, uma falha na ingestão contínua reproduziria o próprio ponto frágil que a migração precisa eliminar.
- Fase 2 (Transformação Incremental) depende de: investigação do código/DAG das 14 etapas (Fase 0) **e** de a Fase 1 ter rodado tempo suficiente para gerar dados de sombra estáveis para testar contra a lógica de transformação.
- Fase 3 (Escrita Incremental) depende de: investigação da atomicidade de escrita (Fase 0) **e** da Fase 2 estar validada — não se redesenha a escrita antes de saber o que a transformação incremental realmente produz.
- Fases 4, 5 e 6 (consumo) dependem de: sinal de fechamento (watermark) refinado por consumidor, que por sua vez depende da Fase 3 já ter uma escrita incremental com garantia de atomicidade definida. Nenhuma delas pode começar antes da anterior na ordem Sentinel → Cerebro → Pepper, pois cada uma valida o mecanismo de fechamento antes do próximo consumidor mais sensível depender dele.

# 5. FASES NÃO PRONTAS

- **Fase 2 — Transformação Incremental.** Bloqueada porque o diagnóstico marca as 14 etapas, individualmente e como cadeia, como NÃO DECIDÍVEL (seção 4 do diagnóstico) — não há informação sobre quais etapas fazem agregação/window/join sobre o lote inteiro e quais operam evento a evento. Falta: inspeção do código-fonte ou DAG do job Spark (lacuna listada na seção 7 do diagnóstico).
- **Fase 3 — Escrita Incremental com Sinal de Fechamento.** Bloqueada porque a atomicidade da escrita atual na partição-hora é NÃO DECIDÍVEL (seção 1 do diagnóstico). Falta: checar a implementação/configuração de escrita no data warehouse.
- **Fase 4 — Consumo Sentinel.** Bloqueada porque a frequência real de leitura esperada por Sentinel não é informada (NÃO DECIDÍVEL, seção 2 do diagnóstico), impedindo definir o SLA do sinal de fechamento equivalente. Falta: levantar contrato de consumo/configuração de polling de Sentinel.
- **Fase 5 — Consumo Cerebro.** Bloqueada pela mesma lacuna de frequência de Sentinel, agravada por outra: NÃO DECIDÍVEL se Cerebro exige ordem de chegada para indexação (seção 2 do diagnóstico). Falta: levantar contrato de consumo de Cerebro e confirmar se há dependência de ordenação.
- **Fase 6 — Consumo Pepper / Billing.** Bloqueada porque o horário exato e o recorte de dado usado pelos relatórios de billing não são informados com precisão (lacuna, seção 7 do diagnóstico), apenas que rodam "de madrugada" sobre dado assumido fechado. Falta: consultar especificação/agendamento e query-fonte dos relatórios.

# 6. RISCOS TRANSVERSAIS

- Se a investigação da Fase 0 sobre as 14 etapas revelar que a cadeia é holística (depende de agregação sobre a janela de 1h inteira), qualquer suposição informal de que "blocos pequenos" bastam para a Fase 2 cai — a Fase 2, como nomeada aqui, pode precisar ser subdividida antes de ser proposta como fase única.
- A Fase 1 rodando por tempo indefinido sem avançar para a Fase 2 cria dependência oculta: fases seguintes assumem que o caminho em sombra já acumulou dados suficientes para comparação estatisticamente válida — se a Fase 1 for interrompida cedo, a Fase 2 herda essa lacuna sem declarar.
- O mecanismo de idempotência/replay desenhado na Fase 0 precisa ser único e coerente entre ingestão (Fase 1), transformação (Fase 2) e escrita (Fase 3); se cada fase implementar sua própria noção de replay isoladamente, o risco de duplicação na partição (já presente hoje, seção 5 do diagnóstico) pode se recriar na junção entre fases.
- O "sinal de fechamento" genérico definido na Fase 0 é um ponto único de acoplamento entre as três fases de consumo (4, 5, 6); se ele for calibrado pensando apenas no caso mais tolerante (Sentinel), pode não satisfazer a suposição mais rígida da Pepper quando a Fase 6 for desenhada, exigindo retrabalho retroativo no sinal.
- Enquanto a atomicidade de escrita (bloqueio da Fase 3) não for esclarecida, qualquer tentativa de acelerar a Fase 2 assumindo uma escrita incremental "por conveniência" recriaria o risco já relatado de leitura de partição em escrita parcial (seção 5 do diagnóstico) — mesmo em ambiente de sombra, isso invalidaria os dados de divergência coletados.