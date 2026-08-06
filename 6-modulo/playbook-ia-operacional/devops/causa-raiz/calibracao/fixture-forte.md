### 1. RESUMO EXECUTIVO

O job de reindexação agendado para 02:00 não terminou na sua janela e continuou escrevendo dentro do horário comercial, e com `refresh_interval: 1s` sobre um heap de 8g essa sobreposição levou o cluster ao circuit breaker. O heap saturado forçou eviction do query cache, o que multiplicou o custo por busca e realimentou a pressão de memória. A partir de 09:58 as buscas passaram a estourar o timeout de 5s e a retornar resultado parcial (11 de 12 shards), e a fila de escrita passou a rejeitar bulks. Por que a reindexação já estava 6h atrasada às 08:02 não é respondível com estes artefatos.

### 2. COBERTURA DOS ARTEFATOS

| Artefato | Janela coberta | Escopo | O que não cobre |
|---|---|---|---|
| 1 — `cerebro.yaml` | estado declarado, sem histórico | cluster (parâmetros) | número de nós, RAM do host, config efetiva em runtime, histórico de mudanças |
| 2 — série de métricas | 08:00–10:00 UTC, pontos de 30min | agregado do Cerebro | 02:00–08:00 (janela do início da reindexação), taxa de queries (QPS), métricas por nó e por shard |
| 3 — logs | 08:02–10:05 UTC | apenas `cerebro-node-3` | demais nós, eventos de cluster (join/leave, realocação de shard), janela 02:00–08:02 |

Consequência do recorte: nenhuma conclusão de escopo cluster-wide pode ser ESTABELECIDA, e a causa do atraso inicial da reindexação está fora da janela disponível.

### 3. BASELINE VERSUS OBSERVADO

| Parâmetro | Configurado | Observado | Veredito |
|---|---|---|---|
| `reindex_job.schedule` | 02:00 diário | task 88123 iniciada 02:00 | dentro do esperado |
| `reindex_job.avg_duration_min` | 90min (fim ~03:30) | 41% às 09:58, ETA unknown — 8h de execução | **fora do esperado, fator ~5,3x** |
| `jvm_heap` | 8g | 61% às 08:00, 94% às 10:00, breaker a 96% | **fora do esperado** |
| `refresh_interval` | 1s | mantido durante reindexação de 10M docs | **fora do esperado para carga de bulk** |
| `query_cache.size_mb` | 512 (6,25% do heap) | hit 74% → 29%, eviction rate em alta | **fora do esperado** |
| `shards: 12` | 12 | busca retornou 11/12 shards; shard 7 em throttling | fora do esperado (degradado, não config) |
| `replicas_per_shard: 1` | 1 (24 cópias de shard) | não observável | não observável com estes artefatos |

### 4. LINHA DO TEMPO CORRELACIONADA

| Horário (UTC) | Sinal | Origem |
|---|---|---|
| 02:00 | reindex task 88123 inicia (agendada) | A1 `schedule` + A3 tag `(scheduled 02:00)` |
| ~03:30 | término esperado — não ocorre | A1 `avg_duration_min: 90` |
| 08:00 | p99 850ms · 4200 docs/s · heap 61% · cache 74% | A2 |
| 08:02:11 | reindex em 38% (3.8M/10M) após 6h | A3 `LoggingTaskListener` |
| 08:14:33 | GC young 620ms, heap 4.9→3.1gb (recupera 1.8gb) | A3 `JvmGcMonitorService` |
| 08:41:07 | throttling de indexação no shard 7, "segment writing can't keep up" | A3 `IndexingMemoryController` |
| 09:00 | p99 2300ms · **9800 docs/s (2,3x)** · heap 79% · cache 58% | A2 |
| 09:03:55 | write thread pool queue 150/200 | A3 `ThreadPool` |
| 09:12:48 | GC old 1.1s, heap 6.3→5.9gb (recupera 0.4gb) | A3 |
| 09:20:02 | reindex em 40% — avançou 2 pontos em 78min | A3 |
| 09:30 | p99 4100ms · 11200 docs/s · heap 88% · cache 41% | A2 |
| 09:31:17 | breaker [parent] a 86%, "approaching limit" | A3 `HierarchyCircuitBreakerService` |
| 09:44:29 | slow query no shard 7, 2380ms | A3 `SearchService` |
| 09:51:08 | queue 188/200 | A3 |
| 09:58:41 | queue 200/200, `EsRejectedExecutionException` em bulk | A3 |
| 09:58:43 | GC old 1.8s, heap 7.6→7.4gb (**recupera 0.2gb**) | A3 |
| 09:58:46.330 | query no shard 7 em 5031ms contra timeout de 5000ms | A3 `QueryPhase` |
| 09:58:46.512 | resultado parcial: 11/12 shards | A3 |
| 09:58:46.701 | breaker [parent] disparado, 96% | A3 |
| 09:58:47.001 | eviction do query cache em alta, hit_ratio 0.29 | A3 `IndicesQueryCache` |
| 10:00 | p99 6700ms · 12400 docs/s · heap 94% · cache 29% | A2 |
| 10:01:12 | `CircuitBreakingException: Data too large [7.9gb/8gb]` | A3 |
| 10:03:39 | 1284 bulks rejeitados em 5min | A3 |
| 10:05:50 | all shards failed em 3 das últimas 20 queries | A3 |

**Ordem de precedência (Passo 4):** o atraso da reindexação precede tudo (já observável às 08:02, antes de qualquer WARN de memória). A vazão de escrita triplica entre 08:30 e 10:00 (4100 → 12400 docs/s). Heap, fila de escrita, latência e cache movem-se todos depois. Portanto: **iniciador candidato = reindexação sobreposta ao horário comercial**; heap, cache, fila e latência são **consequências**.

### 5. CADEIA CAUSAL

1. Reindexação de 10M docs excede sua janela e entra no horário comercial -> a carga de escrita da reindexação passa a somar-se à ingestão viva do dia (docs/s sobe de 4200 para 12400 entre 08:00 e 10:00). **ESTABELECIDO** (A3 08:02:11 e 09:58:44; A2 coluna `indexed_docs_per_s`).
2. `refresh_interval: 1s` sob escrita pesada -> cada shard cria um novo segmento por segundo, multiplicando metadados de segmento e buffer de indexação retidos em heap. **INFERIDO** (A1 `refresh_interval`; mecanismo padrão de refresh do Elasticsearch; A3 08:41:07 "segment writing can't keep up").
3. Buffer de indexação e metadados crescem -> heap sobe de 61% para 94% e o GC deixa de recuperar espaço: 1.8gb no young às 08:14, 0.4gb no old às 09:12, 0.2gb no old às 09:58. **ESTABELECIDO** (A2 `heap_used_pct`; A3 três linhas de `JvmGcMonitorService`). A queda no volume recuperado indica live set crescente, não GC mal ajustado — não há lixo a coletar.
4. Refresh a cada 1s invalida entradas do query cache por segmento, e a pressão de heap força eviction -> hit ratio cai de 74% para 29%. **INFERIDO** para o efeito do refresh (mecanismo de cache por segmento), **ESTABELECIDO** para a eviction (A3 09:58:47.001; A2 `cache_hit_pct`).
5. Cache miss -> cada busca reprocessa o que antes era servido do cache, aumentando alocação por query e realimentando o heap. **INFERIDO** (mecanismo; consistente com p99 subindo 7,9x enquanto o cache cai).
6. Heap em 96% -> `HierarchyCircuitBreakerService` dispara e passa a recusar operações. **ESTABELECIDO** (A3 09:58:46.701 e 10:01:12).
7. Contenção de memória e CPU no nó -> write thread pool satura (150 → 188 → 200/200) e rejeita bulks, 1284 em 5min. **ESTABELECIDO** (A3 09:03:55, 09:51:08, 09:58:41, 10:03:39).
8. Buscas excedem o timeout de 5s e shards recusam operação -> resultado parcial 11/12 shards e "all shards failed" em 3 de 20 queries — os dois sintomas reportados pelo plantão. **ESTABELECIDO** (A3 09:58:46.330, 09:58:46.512, 10:05:50).

### 6. CAUSA-RAIZ

**CAUSA-RAIZ PARCIAL.** O que está estabelecido: a degradação é produzida pela sobreposição da reindexação atrasada com a carga de horário comercial, sobre uma configuração que não tolera essa sobreposição — `refresh_interval: 1s` mantido durante bulk de 10M docs, heap de 8g e 512MB dedicados ao query cache. Classificação: **configuração + agendamento**, não capacidade pura e não carga externa. O elemento que permanece aberto é o gatilho do atraso: às 08:02 a task já estava em 38% após 6h de execução contra uma média de 90min, e a janela 02:00–08:02 não tem nem métrica nem log neste pacote. Confiança **alta** para a cadeia de amplificação de 08:00 a 10:05 (cada elo tem timestamp e métrica correspondentes) e **baixa** para a origem do atraso (zero evidência na janela relevante). Consequência prática: as ações de contenção e correção abaixo são seguras porque atacam a cadeia estabelecida, mas a prevenção fica incompleta até a janela 02:00–08:00 ser recuperada — sem isso, o mesmo atraso pode reaparecer amanhã às 02:00.

### 7. HIPÓTESES DESCARTADAS E NÃO DESCARTADAS

| Hipótese | Evidência a favor | Evidência contra | Veredito |
|---|---|---|---|
| **H1 — Reindexação atrasada sobreposta à carga comercial, amplificada por `refresh_interval: 1s` e heap de 8g** | task em 41% às 09:58 contra ETA de 90min; docs/s 4200→12400; throttling por segment writing; GC recuperando cada vez menos | nenhuma nos artefatos | **sobrevivente** |
| **H2 — Pico de volume de queries (carga externa, comportamento de cliente)** | p99 sobe 7,9x; cache hit cai — compatível com mudança de padrão de query | não há métrica de QPS no pacote; o sinal que triplica é de escrita (`indexed_docs_per_s`), não de leitura; a eviction está logada como consequência de pressão de memória (09:58:47) | **não descartada** — falta QPS para eliminar. Não explica a saturação da fila de *escrita* |
| **H3 — Heap subdimensionado (capacidade)** | 8g com 12 shards; breaker a 96%; `Data too large` | às 08:00 o heap estava em 61% com a reindexação já em curso há 6h — o mesmo cluster operava dentro do envelope antes da sobreposição; heap é insuficiente *para este cenário*, não em absoluto | **descartada como causa-raiz**, retida como fator agravante |
| **H4 — Query cache mal dimensionado (512MB) sendo a causa** | hit ratio despenca; eviction em alta | ordem dos eventos inverte a causalidade: breaker a 96% às 09:58:46.701 precede a eviction logada às 09:58:47.001; o cache é vítima da recuperação de heap | **descartada** |
| **H5 — Data skew / shard 7 quente** | shard 7 aparece em throttling (08:41), slow query (09:44) e timeout (09:58) | o throttling é atribuído a `IndexingMemoryController` (buffer global) e o breaker é `[parent]`, ambos de escopo de nó, não de shard; shard 7 é provavelmente o destino da escrita da reindexação | **não descartada** — falta `_cat/shards` para eliminar |
| **H6 — GC mal ajustado** | pausas de 1.1s e 1.8s no old gen | os ciclos recuperam 1.8gb → 0.4gb → 0.2gb: o padrão é de live set crescente, não de coleta ineficiente. Ajustar GC não cria memória | **descartada** |

### 8. LACUNAS DE EVIDÊNCIA

| Dado que falta | O que decide | Como coletar |
|---|---|---|
| Logs e métricas de 02:00 a 08:02 | a origem do atraso da reindexação — a única peça que fecha a causa-raiz | `kubectl logs cerebro-node-3 --since-time=2026-05-13T02:00:00Z --until-time=2026-05-13T08:02:00Z`; série de métricas na mesma janela |
| Histórico da task 88123 e sua configuração de execução | se a reindexação rodou sem `slices`/throttle, ou se é retomada de execução anterior falha | `GET _tasks/88123`, `GET _tasks?actions=*reindex&detailed`, definição do job no repo de infra |
| Taxa de queries (QPS) e latência por tipo de query | elimina ou confirma H2 | `GET _nodes/stats/indices/search`, painel de QPS do Sentinel na mesma janela |
| Distribuição de shards, docs e store size | elimina ou confirma H5 | `GET _cat/shards/logs-2026.05?v&s=store:desc`, `GET _cat/allocation?v` |
| Logs dos demais nós e eventos de cluster | se a degradação é do nó 3 ou cluster-wide | `kubectl logs -l app=cerebro --since=3h`, `GET _cluster/health?level=indices`, `GET _cat/nodes?v&h=name,heap.percent,ram.percent` |
| RAM do host e número de nós | se há espaço para elevar heap sem violar o limite de 50% da RAM e os 31g de compressed oops | `kubectl describe node`, `GET _nodes/_all/os,jvm` |
| Config efetiva em runtime | se `cerebro.yaml` reflete o cluster ou divergiu | `GET logs-2026.05/_settings`, `GET _cluster/settings?include_defaults=true` |

### 9. AÇÕES

**CONTENÇÃO IMEDIATA** — reverter o sintoma agora, sem tocar em capacidade

1. Cancelar a reindexação. `POST _tasks/88123/_cancel`
   Efeito: remove a fonte da carga de escrita extra; espera-se queda de heap e da fila em minutos.
   Risco no estado atual: baixo. A task está em 41% com ETA desconhecida e o reindex é retomável; nenhum dado é perdido. Preserva a evidência.
   Reversão: reexecutar depois, já com os ajustes da correção 1 e 2.
2. Elevar `refresh_interval` no índice sob escrita. `PUT logs-2026.05/_settings {"index":{"refresh_interval":"30s"}}`
   Efeito: reduz criação de segmentos e invalidação do query cache; alívio de heap. Aplicável a quente, sem reinício.
   Risco no estado atual: médio-baixo — documentos recém-indexados ficam visíveis para busca com até 30s de atraso. Comunicar ao plantão antes.
   Reversão: `PUT logs-2026.05/_settings {"index":{"refresh_interval":"1s"}}`
3. Confirmar recuperação antes de qualquer outra intervenção. `GET _nodes/stats/jvm,thread_pool`, `GET _cat/thread_pool/write?v&h=name,active,queue,rejected`
   Efeito: valida se as ações 1 e 2 bastaram. Se heap cair abaixo de 75% e `queue` esvaziar, pare aqui.
   Risco: nenhum.
   Reversão: não aplicável.

**Não executar agora:** aumento de `jvm_heap`, restart de nó, force merge e delete de índice. Todos exigem reinício ou alocação de memória sob breaker ativo, arriscam realocação de shard com o cluster já saturado, e destruiriam a evidência necessária para fechar a causa-raiz.

**CORREÇÃO** — remover a causa

1. Reescrever o job de reindexação com paralelismo e throttle explícitos: `slices: auto` e `requests_per_second` calibrado para caber na janela de 90min, com `refresh_interval: -1` no início e restauração ao final como parte do próprio job. Reversão: manter a definição anterior versionada e revertível por Git.
2. Adicionar watchdog de janela ao job: se a reindexação não concluir até 06:00, cancelar automaticamente e abrir alerta em vez de deixar avançar sobre o horário comercial. Reversão: desabilitar o watchdog por flag.
3. Reavaliar o orçamento de heap com dado real (`ram.percent` por nó) antes de alterar `jvm_heap: 8g` — e nesse caso, em janela planejada com rolling restart, respeitando heap ≤ 50% da RAM e ≤ 31g. Revisar em conjunto o `query_cache.size_mb: 512`, que hoje disputa heap com o buffer de indexação. Reversão: valores anteriores no `cerebro.yaml`.
4. Recuperar a janela 02:00–08:00 e reabrir esta análise. Sem isso a correção 2 mitiga o efeito do atraso, mas não a sua causa.

**PREVENÇÃO**

1. Alerta de duração: reindexação excedendo `avg_duration_min` × 1,5 (135min) dispara aviso; excedendo 2x, dispara página. Hoje o job passou 8h fora do envelope sem alerta próprio — foi descoberto pelo sintoma no usuário.
2. Alerta de heap em 80% e alerta dedicado para trip do circuit breaker. Os dois sinais estavam nos logs desde 09:31 e não geraram acionamento.
3. Alerta de `write` thread pool queue acima de 50% de `queue_size`. A fila levou 55min de 150/200 até encher — janela ampla para agir antes da rejeição.
4. Incluir no runbook de reindexação a manipulação obrigatória de `refresh_interval` e a proibição de bulk de grande volume dentro do horário comercial.

