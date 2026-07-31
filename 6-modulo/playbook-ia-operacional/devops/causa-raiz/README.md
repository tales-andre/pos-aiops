---
nome: Análise de Causa-Raiz
descricao: Analisa a causa-raiz de uma degradação cruzando configuração, métricas e logs até separar causa de sintoma, com estados epistêmicos rotulados e ações não-destrutivas.
versao: 1.0.0
tags: [devops, sre, rca, observabilidade, elasticsearch]
inputs:
  - nome: CONFIG_CLUSTER
    descricao: Arquivo de configuração versionado do cluster (ex.: cerebro.yaml) com os parâmetros que definem o baseline esperado.
  - nome: SERIE_METRICAS
    descricao: Série temporal de métricas do sistema no período da degradação (latência, vazão, heap, cache).
  - nome: TRECHO_LOGS
    descricao: Trecho dos logs nativos cobrindo a mesma janela das métricas.
---

# Análise de Causa-Raiz

## Objetivo

Levar a IA a raciocinar até a causa-raiz de uma degradação — separando causa de
sintoma — a partir de um pacote de três artefatos de fontes distintas (configuração,
métricas e logs) cobrindo a mesma janela de tempo. O prompt impõe um processo de nove
passos (inventário, baseline vs. observado, linha do tempo, precedência, hipóteses
concorrentes, eliminação por evidência, mecanismo, fechamento, remediação) e obriga
cada conclusão a citar sua origem e a ser rotulada como ESTABELECIDO, INFERIDO ou
DESCONHECIDO. É o prompt que o time reusa a cada degradação, trocando só o pacote.

## Quando usar

- Análise de causa-raiz de um incidente de degradação (latência, saturação, erros)
  quando há artefatos de fontes diferentes para cruzar.
- Sempre que o risco de confundir sintoma com causa for alto e a remediação for cara.
- Não substitui acesso ao cluster: trabalha só com os artefatos fornecidos e declara
  o que fica fora do alcance deles.

## Parâmetros

| Parâmetro | Descrição |
|-----------|-----------|
| `{{CONFIG_CLUSTER}}` | Configuração versionada do cluster (baseline esperado). |
| `{{SERIE_METRICAS}}` | Série temporal de métricas no período da degradação. |
| `{{TRECHO_LOGS}}` | Trecho dos logs nativos, mesma janela das métricas. |

## Exemplo de uso

Preencha os três parâmetros com o pacote de artefatos coletado (config + métricas +
logs da mesma janela) e envie. A saída são nove seções: resumo executivo, cobertura
dos artefatos, baseline vs. observado, linha do tempo correlacionada, cadeia causal,
causa-raiz (ou causa-raiz parcial), hipóteses descartadas/não descartadas, lacunas de
evidência e ações (contenção, correção, prevenção). Execução completa sobre o incidente
do Cerebro em [`execucoes/artefatos-cerebro.md`](./execucoes/artefatos-cerebro.md).

## Execução

Rodado sobre o pacote de artefatos da degradação do Cerebro (config `cerebro.yaml`,
métricas 08:00–10:00 e log do `cerebro-node-3`), com **Claude Opus 5** (`claude-opus-5`,
via claude.ai, temperatura 0.2). Resultado resumido:

- **Causa-raiz (parcial):** reindexação atrasada sobreposta à carga de horário comercial,
  sobre uma configuração intolerante (`refresh_interval: 1s` durante bulk de 10M docs,
  heap 8g), levando a saturação de heap → circuit breaker → timeouts de busca e queda do
  cache. Classificação: configuração + agendamento.
- **Parcial** porque o gatilho do atraso da reindexação (janela 02:00–08:02) está fora
  dos artefatos — honestidade epistêmica em vez de fechar a cadeia com suposição.
- Cache hit caindo é tratado como **efeito**, não causa (ordem em milissegundos: breaker
  às 09:58:46.701 precede a eviction às 09:58:47.001).
- Ações separam contenção (cancelar reindex, subir `refresh_interval` a quente),
  correção e prevenção, com a regra de **não aumentar recurso como primeira ação**.

## Criação via meta-prompting

Prompt gerado e refinado com **Claude Opus 5** (via claude.ai) a partir dos requisitos;
a execução acima também rodou no Opus 5. Combinado com o Gemini usado nos CP01/CP02,
fecha a exigência de dois provedores distintos ao longo do desafio. O meta-prompt em si
não é entregável.

## Sanitização (pré-envio a modelo externo)

Os artefatos vão para um modelo fora do perímetro. A decisão de tratamento aqui é o inverso de um filtro de DLP genérico: o valor diagnóstico depende de correlacionar a **mesma entidade** entre os três artefatos, então a operação correta é **pseudonimização consistente com mapa mantido localmente**, não redação cega. Redigir sem preservar identidade quebra o Passo 3 do prompt e produz uma análise inútil.

**Tratar antes de enviar:**

| Classe | Ocorrência neste pacote | Tratamento |
|---|---|---|
| Segredos e credenciais | ausentes aqui, mas `cerebro.yaml` é o tipo de arquivo que carrega endpoints autenticados, tokens de snapshot e credenciais de repositório | bloqueio duro. Qualquer match de credencial aborta o envio — não pseudonimiza, não mascara |
| Identificadores de tenant | ausentes neste pacote, presentes na mesma pipeline em outros alertas | `TENANT_1`, `TENANT_2`… mapa local. Correlação preservada |
| Nomes de nó e pod | `cerebro-node-3` | `NODE_C` estável em todos os artefatos |
| Nomes de índice | `logs-2026.05` | `INDEX_A` — a data no nome do índice também revela retenção e volume |
| Hostnames internos, FQDNs, IPs e CIDRs | ausentes neste pacote | `HOST_X`, `CIDR_1`. Bloqueio se for endpoint interno resolvível |
| Caminhos de repositório e URLs internas | referência ao repositório de infra | remover |
| Timestamps absolutos | todos os artefatos | deslocamento por offset constante único para o pacote. Preserva todos os deltas — que é o que o Passo 4 usa — e oculta a janela real de manutenção |
| Volumes de negócio | `10M docs`, contagens de tenant | arredondar para ordem de magnitude quando o valor exato não for necessário. Aqui `10M` é necessário (define o progresso de 41%), então mantém |

**Não tratar** — redigir estes campos é falso positivo com custo diagnóstico direto: valores de métrica, percentuais de heap e cache, níveis de log, classes Java do Elasticsearch, nomes e valores de parâmetro de configuração, números de shard, IDs de task, mensagens de exceção. Nenhum deles identifica pessoa, cliente ou credencial, e todos são elos da cadeia causal.

**Ordem de operações:** bloqueio de segredo primeiro (falha fecha o envio), pseudonimização depois, deslocamento temporal por último. O mapa reverso fica local, e a saída do modelo é reidratada na volta antes de chegar ao plantonista.

---

## Curadoria

### 4.1 Justificativa do framework

**R-I-S-E**, por critério 4 da decision tree do `prompt-lab-guia.md`: o modelo processa um input específico seguindo um processo estruturado, e o guia aponta explicitamente troubleshooting e diagnóstico técnico como o caso de uso do framework. O que decide a favor dele aqui é a existência do slot **Input** como seção de primeira classe: o pacote de três artefatos de fontes heterogêneas precisa ser declarado com procedência, porque o valor diagnóstico está no cruzamento e o modelo precisa saber o que cada fonte pode e não pode sustentar.

Descartados:
- **C-A-R-E** — foi a escolha do checkpoint anterior e aqui é inadequado. Exigiria exemplos de I/O, e um exemplo de RCA completo ancora o modelo na história causal do exemplo. Em diagnóstico isso é o pior viés possível: o modelo tende a reencontrar a causa que já viu.
- **R-T-F** — entrega o formato mas não tem onde colocar o processo. Sem os nove passos, o modelo pula direto do sintoma à conclusão, que é exatamente a falha que o pedido quer evitar.
- **T-A-G** — as ações são sequenciais, mas o Goal aqui não é mensurável a priori: não se sabe qual é a causa antes de analisar. TAG serviria para o job de reindexação corrigido, não para a análise.
- **B-A-B** — o "before" é desconhecido. Usá-lo obrigaria a assumir o estado inicial, que é justamente o que está em aberto.

### 4.2 Justificativa das técnicas

- **Chain-of-Thought explícito** (Wei et al., 2022) — os nove passos do STEPS são o CoT estruturado como processo auditável, não como "pense passo a passo". A diferença importa: o Passo 4 (ordem de precedência) é o que impede o modelo de eleger o sinal mais dramático como causa. Sem ele, o candidato natural é o heap a 94%, que é consequência.
- **Self-Consistency** (Wang et al., 2022) — aplicada como hipóteses concorrentes obrigatórias com eliminação por evidência, e não como múltiplas execuções agregadas. A exigência de no mínimo três hipóteses, incluindo uma de causa externa e uma de configuração, força o modelo a construir o caso contra a própria conclusão. Justificativa pelo custo de erro: um RCA errado dispara remediação errada em produção.
- **Zero-shot deliberado** — decisão consciente, não omissão. Ver 4.1: few-shot em diagnóstico ancora causalidade. O formato é garantido pela seção EXPECTATION, que é específica o bastante para dispensar exemplo.

### 4.3 Regras que carregam o peso do prompt

Quatro restrições respondem por quase todo o ganho de qualidade e valem ser destacadas para quem reusar o prompt:

1. **Três estados epistêmicos rotulados** (ESTABELECIDO / INFERIDO / DESCONHECIDO). Sem eles o output mistura o que os logs mostram com o que o modelo sabe de Elasticsearch, e o plantonista não consegue auditar. Na execução, é o que separa o elo 3 (métrica direta) do elo 5 (mecanismo aplicado).
2. **Causa-raiz parcial é resultado válido.** Sem essa autorização explícita, o modelo fecha a cadeia com uma suposição plausível sobre a janela 02:00–08:00 e entrega uma falsa conclusão. Com ela, a lacuna virou o item 4 da correção.
3. **Correlação não é causalidade — nomeie o mecanismo.** É o que derruba H4: o query cache tem a correlação temporal mais forte de todo o pacote (74→29 acompanhando p99), e a ordem dos milissegundos em 09:58:46.701 versus 09:58:47.001 inverte a direção da causalidade.
4. **Proibição de aumentar recurso como primeira ação.** A resposta reflexa a `heap 94%` é subir o heap. Isso adiaria o colapso, exigiria restart sob breaker ativo e apagaria a evidência.

### 4.4 Achados que só apareceram por cruzamento

Registro do que nenhum artefato isolado entregava — é o argumento para manter o pacote de três como input mínimo:

- **A configuração sozinha** parece razoável. `refresh_interval: 1s` só se torna defeito quando cruzado com a reindexação ativa do log e com a vazão de escrita da métrica.
- **A métrica sozinha** sugere heap subdimensionado. É o log que mostra o GC recuperando 1.8gb → 0.4gb → 0.2gb, o que reclassifica o problema de "heap pequeno" para "live set crescente".
- **O log sozinho** não dá a magnitude: é a métrica que mostra a escrita triplicando de 4200 para 12400 docs/s, o que estabelece a sobreposição de cargas.
- **A quebra de expectativa** só existe no cruzamento: `avg_duration_min: 90` do Artefato 1 contra `41% às 09:58` do Artefato 3 é o achado que reordena toda a análise — e nenhum dos dois artefatos, isolado, contém a comparação.

### 4.5 Como validar antes de promover

- Rodar o mesmo pacote 3x a temperatura 0.2 e verificar se a causa-raiz e o conjunto de hipóteses descartadas se mantêm. Variação em H2 ou H5 é esperada (são as não descartadas); variação em H1 invalida o prompt.
- **Teste de artefato incompleto:** enviar apenas métricas e log, sem a configuração. O output deve declarar a ausência no inventário e não deve declarar `refresh_interval` nem heap como fora do esperado — não há baseline. Se declarar, o prompt está permitindo fabricação.
- **Teste de armadilha:** injetar um pacote em que o sinal mais dramático é consequência óbvia de um sinal discreto anterior. O Passo 4 deve pegar.
- **Teste de sanitização:** rodar o pacote pseudonimizado (`NODE_C`, `INDEX_A`, timestamps deslocados) e confirmar que a cadeia causal sobrevive intacta. Se a análise degradar, a camada de sanitização está redigindo demais.

## Limitações conhecidas

- Só conclui com o que está nos artefatos: se o gatilho estiver fora da janela coberta,
  entrega causa-raiz **parcial** e nomeia a lacuna, em vez de fabricar a origem.
- Log de um único nó em cluster multi-nó torna toda conclusão cluster-wide INFERIDA,
  nunca ESTABELECIDA.
- A qualidade depende de os três artefatos cobrirem a **mesma janela**; janelas
  desalinhadas reduzem a interseção usável para correlação causal.
- Dados de produção devem passar pela camada de sanitização acima antes do envio a
  modelo externo — pseudonimização consistente, não redação cega.
