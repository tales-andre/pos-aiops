---
nome: Nota de Triagem
descricao: Transforma um alerta cru de monitoramento em uma nota de triagem padronizada de cinco campos, para leitura em segundos e passagem de turno sem reinterpretação.
versao: 1.0.0
tags: [devops, sre, plantao, incidentes, observabilidade]
inputs:
  - nome: ALERTA_CRU
    descricao: Alerta cru de monitoramento (uma ou mais linhas), como sai do sistema de alerting, colado na entrada.
---

# Nota de Triagem

## Objetivo

Padronizar a primeira nota que o plantonista abre quando um alerta dispara. Recebe
um alerta cru (em formato livre) e devolve uma nota de cinco campos fixos — ALERTA,
IMPACTO, HIPÓTESE INICIAL, AÇÃO IMEDIATA, ESCALAR PARA — legível em segundos por
quem assume o turno seguinte, sem precisar reconstruir contexto do alerta original.

## Quando usar

- Abertura de incidente: primeira nota no canal, a partir do alerta cru.
- Passagem de turno: garantir que todas as notas seguem o mesmo padrão.
- Qualquer alerta de plataforma de observabilidade multi-tenant (Sentinel, Relay,
  Forge, Cerebro ou componente equivalente).

## Parâmetros

| Parâmetro | Descrição |
|-----------|-----------|
| `{{ALERTA_CRU}}` | Alerta cru de monitoramento, uma ou mais linhas, como sai do alerting. É o único parâmetro. |

## Exemplo de uso

Entrada em `{{ALERTA_CRU}}`:

```text
2026-05-13 03:11:00 UTC [Relay] ingest reject rate 6% for 8min, tenant wakanda-systems,
buffer saturated after deploy 02:55
```

Saída:

```text
ALERTA: Relay - ingest reject rate de 6% por 8min
IMPACTO: ingestão de telemetry degradada para o tenant wakanda-systems
HIPÓTESE INICIAL: deploy das 02:55 causou saturação do buffer
AÇÃO IMEDIATA: rollback do deploy iniciado
ESCALAR PARA: @relay-core se taxa de rejeição não cair em 10min
```

## Execução

Rodado contra os três alertas crus do desafio, com **Gemini 3.5 Flash**
(`gemini-3.5-flash`) no Google AI Studio (temperatura 1 padrão, thinking Medium,
grounding off). Uma execução por alerta, sem histórico compartilhado.

| Caso | Cenário | Verificação |
|------|---------|-------------|
| [Alerta 1](./execucoes/alerta-1-sentinel-autoscaler.md) | Sentinel / autoscaler no teto | Escala para `@plantao-plataforma` (fallback correto — Sentinel não tem dono no mapa), sem reciclar handle dos exemplos. |
| [Alerta 2](./execucoes/alerta-2-relay-reject.md) | Relay / rejeição (quase igual ao Exemplar 1) | Preserva `6%/8min` e `wakanda-systems`; **não** importa `2%/5min` dos exemplos — a cerca contra contaminação segurou. |
| [Alerta 3](./execucoes/alerta-3-forge-lag.md) | Forge / consumer lag | Escolhe **uma** ação (reprocessar o job) e escala para `@data-platform` com janela de 20min. |

Todas as saídas: cinco rótulos na ordem fixa, `ESCALAR PARA:` com handle `@palavra`,
dentro do limite de 8 linhas.

## Curadoria

### Método (a decisão central do checkpoint)

O padrão podia ser ensinado de três formas — a escolha e o descarte das outras:

| Método | Avaliação |
|--------|-----------|
| **Few-shot output-only (escolhido)** | Os três exemplares do time são notas prontas, sem o alerta cru que as originou. Injetá-los como exemplares de *saída* calibra tom, granularidade e comprimento de linha — caros de descrever, baratos de demonstrar — sem forjar pares de I/O que não existem. |
| Few-shot clássico (input→output) | **Descartado.** Exigiria inventar os alertas crus dos exemplares (injeta correlação falsa); usar as três entradas de teste como exemplos seria vazamento (avaliar nos mesmos dados que ensinaram). |
| Zero-shot com spec rígida | **Descartado como método único, mantido como camada.** Spec sozinha reproduz os campos mas não o registro do time. Entrou como a seção REQUIREMENTS, com os exemplares fazendo a calibração. |

**Framework: CARE** (Context · Action · Requirements · Examples) — é o único do guia
que trata Examples como seção de primeira classe, e a tarefa é dominada por formato
e consistência, não por raciocínio de diagnóstico (por isso não é RISE como no CP01).

**Criação via meta-prompting:** o prompt foi gerado e refinado com **Claude Opus 5**
(`claude-opus-5`, via claude.ai) dirigindo a redação a partir dos requisitos; a
**execução** nos três alertas rodou no **Gemini 3.5 Flash**. Dois provedores distintos
(Anthropic na criação, Google na execução). O meta-prompt em si não é entregável.

**A armadilha do checkpoint** é misturar as duas listas (exemplares de formato × alertas
de entrada). O prompt marca os exemplares como *output-only*, com instrução explícita de
não inferir o formato de entrada a partir deles nem reaproveitar seu conteúdo — validado
no Alerta 2, onde o modelo não copiou `2%/5min` nem `~12% dos tenants`.

**CoT interno, não exposto:** os cinco passos de raciocínio ficam na seção ACTION, com
instrução de não aparecerem no output. Classificar mal o blast radius ou o owner é o erro
mais caro em triagem; o raciocínio explícito reduz isso sem poluir uma nota que precisa
ser lida em 10 segundos.

### Regras derivadas por engenharia reversa dos exemplares

- **Separação métrica/consequência.** ALERTA carrega o número; IMPACTO nunca o repete —
  traduz para consequência ("dashboards atrasados"). Sem a regra, o modelo duplica a métrica.
- **A janela de escalonamento é tempo-de-efeito, não severidade.** Nos exemplares: rollback
  → 10min, pausa de reindexação → 15min, repartição → 20min. Não há correlação com blast
  radius (o exemplar com impacto em todos os tenants tem a janela mais longa). A regra
  codificada é o tempo esperado de efeito da ação imediata.

### Observações sobre as execuções reais

- **Alerta 1** foi o mais difícil: dispara no Sentinel, mas o sinal de saturação está no
  Relay e a causa no tenant. A regra "ALERTA nomeia o componente onde disparou; os demais
  vão para IMPACTO/HIPÓTESE" resolveu. Caiu no fallback `@plantao-plataforma` — ver pendência 1.
- **Alerta 2** era o caso de risco de contaminação (quase isomórfico ao Exemplar 1). Preservou
  `6%/8min` e o tenant correto — valida a cerca da seção EXAMPLES.
- **Alerta 3** tinha duas ações plausíveis (reprocessar o job ou aumentar partições). A regra
  de ação única forçou a escolha da que ataca a causa.

### Pendências (para o time / a Carol Danvers)

1. **Sentinel não tem owner no mapa de escalonamento** — o Alerta 1 caiu no fallback
   `@plantao-plataforma` (auto-escalonamento). Definir o time dono antes de produção.
2. **Autoridade para rate limit por tenant** — a ação sugerida pressupõe que o plantonista
   pode aplicar rate limit sozinho; se exige aprovação, deixa de ser "imediata".
3. **Janelas 10/15/20min** foram inferidas dos exemplares — confirmar com dados medidos.

## Testes determinísticos (CP08)

Config: [`promptfooconfig.yaml`](./promptfooconfig.yaml). Roda os 3 alertas reais acima contra
dois provedores — **Anthropic** (`claude-haiku-4-5-20251001`) e **Google**
(`gemini-3.5-flash`) — verificando os cinco rótulos, o handle `@palavra` em `ESCALAR PARA:`,
o limite de 8 linhas, e os tetos operacionais de latência (≤5s) e custo (≤US$0,01).

**Resultado real (`promptfoo eval`):**

| Provider | Alerta 1 | Alerta 2 | Alerta 3 |
|---|---|---|---|
| `anthropic:messages:claude-haiku-4-5-20251001` | ✅ PASS (2,3s · US$0,0026) | ✅ PASS (1,3s · US$0,0024) | ✅ PASS (1,6s · US$0,0025) |
| `google:gemini-3.5-flash` | ✅ PASS (1,6s · US$0,0036) | ✅ PASS (1,5s · US$0,0033) | ✅ PASS (1,4s · US$0,0033) |

**6/6 passou.** Nenhum ajuste no prompt foi necessário — a saída já é curta e o formato de
cinco campos é rígido o bastante para regex/contains pegarem qualquer desvio.

**Um ajuste no provider, não no prompt:** a primeira rodada reprovou os 3 casos do Gemini só
em latência/custo (7–12s, US$0,02–0,03) — não em conteúdo. O modelo estava gerando tokens de
"thinking" por padrão mesmo numa tarefa de formatação fixa, sem ganho de qualidade. Ajuste:
`generationConfig.thinkingConfig.thinkingBudget: 0` no provider do Gemini no
`promptfooconfig.yaml` — não mexe no prompt em si, só desliga um modo de raciocínio que essa
tarefa não precisa. Depois do ajuste, os três casos do Gemini caíram para ~1,5s e passaram.
Esse é exatamente o tipo de trade-off latência/custo × modelo que o checkpoint pede para
registrar: para uma tarefa de formato fixo, thinking ligado é custo puro, sem retorno.

## Limitações conhecidas

- A qualidade da nota depende do alerta cru: se ele não trouxer sinal causal, a HIPÓTESE
  INICIAL usa a fórmula de ausência em vez de inventar causa.
- O mapa de ownership é fixo no prompt — precisa ser atualizado quando times/serviços mudam.
- Alertas com dados sensíveis (tenant, hostname interno) devem ser sanitizados antes do envio
  a modelo externo — ver nota de sanitização do playbook.
