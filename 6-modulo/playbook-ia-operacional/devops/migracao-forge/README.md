---
nome: Migração Batch para Event-Driven
descricao: "Cadeia de três prompts que conduz a migração de um pipeline de lote para orientado a eventos: diagnóstico do estado atual, estratégia de migração em fases reversíveis e plano executável por fase."
versao: 1.0.0
tags: [devops, migracao, event-driven, pipeline, prompt-chaining]
inputs:
  - nome: ESTADO_ATUAL_FORGE
    descricao: "Descrição do pipeline atual em lote (ingestão, transformação, escrita, consumidores, ponto frágil). Entrada externa do Elo 1."
  - nome: REQUISITOS_MIGRACAO
    descricao: "Garantias que a migração precisa preservar (continuidade dos consumidores, reversibilidade, nada de big-bang). Entrada externa dos Elos 1 e 2."
  - nome: OUTPUT_ELO_1
    descricao: "Encadeamento: a saída do Elo 1 (diagnóstico) é o parâmetro de entrada do Elo 2."
  - nome: OUTPUT_ELO_2
    descricao: "Encadeamento: a saída do Elo 2 (estratégia em fases) é o parâmetro de entrada do Elo 3."
  - nome: FASE_ALVO
    descricao: "Nome da fase (definida pelo Elo 2) que o Elo 3 deve detalhar. Entrada externa do Elo 3."
  - nome: RESTRICOES_OPERACIONAIS
    descricao: "Restrições de execução do time (janelas de mudança, o que não pode ser interrompido, tempo de reversão). Entrada externa do Elo 3."
---

# Migração Batch para Event-Driven

## Objetivo

Conduzir a migração de um pipeline de lote para orientado a eventos sem resolver
tudo num prompt só — o que produziria uma resposta rasa. Em vez disso, uma **cadeia
de três prompts** onde a saída de cada elo é o parâmetro de entrada do seguinte:

1. **Elo 1 — Diagnóstico** (RISE): mapeia a cadeia atual, as suposições de cada
   consumidor, os acoplamentos implícitos, os modos de falha herdados e os
   pré-requisitos — sem propor solução.
2. **Elo 2 — Estratégia em fases** (BAB): a partir do diagnóstico, desenha as fases
   de migração rodando em paralelo (não em substituição), com cutover por condição
   e reversão por fase — sem detalhar comandos.
3. **Elo 3 — Plano executável** (RTF): para uma fase-alvo, produz o plano passo a
   passo, executável e reversível por qualquer engenheiro do time.

## Quando usar

- Migração grande demais para um prompt único (batch→streaming, monólito→serviços,
  troca de storage) onde a resposta precisa amadurecer em etapas encadeadas.
- Sempre que a decisão de "como migrar" depender de um diagnóstico rigoroso do
  estado atual antes de qualquer proposta.

## Parâmetros

Entradas externas: `{{ESTADO_ATUAL_FORGE}}`, `{{REQUISITOS_MIGRACAO}}`,
`{{FASE_ALVO}}`, `{{RESTRICOES_OPERACIONAIS}}`.
Encadeamento interno: `{{OUTPUT_ELO_1}}` (Elo 1 → Elo 2) e `{{OUTPUT_ELO_2}}`
(Elo 2 → Elo 3). A saída de um elo é colada literalmente no parâmetro do próximo.

## Exemplo de uso

Rode o Elo 1 com o estado atual + requisitos; pegue a saída e cole em `{{OUTPUT_ELO_1}}`
do Elo 2 junto com os requisitos; pegue a saída do Elo 2 e cole em `{{OUTPUT_ELO_2}}`
do Elo 3, escolhendo uma `{{FASE_ALVO}}` e informando as restrições operacionais.
Execução completa da cadeia sobre o cenário do Forge em [`execucoes/`](./execucoes/).

## Execução

Cadeia rodada de ponta a ponta sobre o cenário do Forge (ingestão por cron de 60min,
14 etapas Spark, tabelas particionadas por hora, dependentes Sentinel/Cerebro/Pepper),
com **Claude Sonnet 5** (via claude.ai) — um elo por vez, cada um em conversa nova,
recebendo a saída do anterior como parâmetro:

| Elo | Framework | Resultado | Arquivo |
|-----|-----------|-----------|---------|
| 1 | RISE | Diagnóstico: 14 etapas marcadas NÃO DECIDÍVEL (cenário não descreve as etapas), suposições por consumidor, 6 pré-requisitos, 6 lacunas. | [elo-1-diagnostico.md](./execucoes/elo-1-diagnostico.md) |
| 2 | BAB | Estratégia: ordem Sentinel→Cerebro→Pepper; Fase 0 (pré-requisitos) e Fase 1 (ingestão em sombra) prontas; Fases 2–6 marcadas NÃO PRONTAS com a lacuna citada. | [elo-2-estrategia.md](./execucoes/elo-2-estrategia.md) |
| 3 | RTF | Plano da Fase 1: passos reversíveis, suposição de feature flag declarada, cutover com limiar remetido à Fase 0 (sem inventar número), reversão em <10min sem parar o batch. | [elo-3-plano-fase-1.md](./execucoes/elo-3-plano-fase-1.md) |

O encadeamento é verificável: o Elo 2 cita "seção 4 do diagnóstico" e herda as
classificações NÃO DECIDÍVEL do Elo 1; o Elo 3 referencia as fases nomeadas pelo Elo 2
e os placeholders de limiar que a estratégia atribuiu à Fase 0.

## Curadoria

- **Por que cadeia (prompt chaining):** a migração tem três decisões de naturezas
  diferentes — diagnosticar, estrategizar, executar — que num prompt único se
  contaminam e saem rasas. Separá-las em elos com escopo fechado (cada elo proíbe
  fazer o trabalho do próximo) força profundidade em cada etapa e torna a saída de
  um elo auditável antes de virar entrada do seguinte.
- **Um framework por elo, casado com a função:**
  - Elo 1 = **RISE** — diagnóstico com input estruturado e passos de raciocínio;
    o slot Input declara a procedência dos dados e os Steps impõem o método.
  - Elo 2 = **BAB** — transição de estado (Before=diagnóstico, After=garantias a
    preservar, Bridge=processo de fases); o "After" como restrições, não como
    solução, impede assumir a resposta.
  - Elo 3 = **RTF** — o que importa é o formato executável e reversível; Role+Task+
    Format entregam o plano sem sobrecarregar de processo.
- **Disciplina de encadeamento:** o Elo 1 termina numa seção "LACUNAS" declarada
  como insumo do próximo; o Elo 2 nomeia as fases de forma estável para o Elo 3
  referenciar. O handoff é desenhado, não acidental.
- **Honestidade epistêmica preservada pela cadeia:** o que o Elo 1 marcou NÃO
  DECIDÍVEL (as 14 etapas), o Elo 2 respeitou marcando as fases dependentes como
  NÃO PRONTAS, e o Elo 3 não inventou os números que a estratégia remeteu à Fase 0.
  A incerteza sobrevive intacta pelos três elos — é o oposto de um prompt monolítico
  que fabricaria uma resposta completa.
- **`{{RESTRICOES_OPERACIONAIS}}` do Elo 3:** o cenário do desafio não fornece
  restrições operacionais, então foram definidas plausíveis para a execução (cutover
  só 00h–06h UTC; billing da Pepper intocável na janela dela; reversão em <10min;
  sem perda de telemetria; deploy via pipeline com revisão). O Elo 3 as tratou
  corretamente — verificou cada passo contra elas e explicou por que não se aplicam
  a uma fase sem cutover.
- **Criação e execução:** a cadeia foi criada via meta-prompting com **Claude
  Sonnet 5**; a execução dos três elos também rodou no Sonnet 5 (claude.ai).
  Combinado com o Gemini dos CP01/02/04 e o Opus 5 do CP03, o playbook cobre dois
  provedores distintos (Anthropic e Google) ao longo do desafio.
- **Escolha de modelo (custo · latência · qualidade · privacidade):** planejamento de
  migração é raciocínio em múltiplos passos encadeados, não uma tarefa de alta
  frequência — Sonnet 5 fica no meio do espectro custo/qualidade da Anthropic, mais
  barato que Opus 5 (usado no CP03 por exigir mais rigor de diagnóstico single-shot) e
  mais capaz que Haiku pra manter coerência entre três chamadas encadeadas. Latência de
  vários segundos por elo é aceitável porque é planejamento, não resposta a incidente
  ativo. Privacidade: o cenário cita nome de pessoa (Pepper, dona dos relatórios de
  billing) e estrutura interna do pipeline — dado de arquitetura interna, não PII de
  cliente final; a exposição não muda entre Anthropic e Google, a mitigação seria
  sanitizar o nome antes do envio.

## Gate de qualidade — LLM-as-judge (CP10)

**Escopo: só o Elo 1 (diagnóstico).** A cadeia inteira exigiria orquestrar 3 chamadas de LLM em
sequência dentro de um teste promptfoo (saída do Elo 1 → entrada do Elo 2 → saída do Elo 2 →
entrada do Elo 3), o que precisaria de um provider customizado que chama a API três vezes por
trás — engenharia real para um checkpoint que já cobre bem o padrão de teste com os outros cinco
prompts. O Elo 1 foi escolhido como representante porque é o único elo autocontido (não depende
de output de elo anterior) e o mais reusado — toda migração futura passa por ele, mesmo que os
elos seguintes mudem. **Lacuna registrada, não escondida:** os Elos 2 e 3 não têm teste
automatizado ainda.

[`elo1-geracao.js`](./elo1-geracao.js) extrai o bloco do Elo 1 de `prompt.md` em runtime, mesmo
padrão do `prompt-geracao.js` do `networkpolicy-sentinel` (CP08) — `prompt.md` continua sendo a
única fonte do texto.

**Rubrica** (4 critérios, 0–2, corte ≥6 e nenhum zerado): fidelidade ao estado atual (sem
inventar mecanismo ou garantia não descrita), escopo respeitado (este elo só diagnostica — nunca
propõe solução, arquitetura-alvo ou tecnologia), acoplamentos e modos de falha (deriva do ponto
frágil relatado, não só repete), honestidade nas lacunas (marca NÃO DECIDÍVEL em vez de assumir).

**Resultado real (`promptfoo eval`):**

| Provider | Score | Gate |
|---|---|---|
| `anthropic:messages:claude-haiku-4-5-20251001` | **5/8** | ❌ **FAIL** — critério 2 (escopo) zerado |
| `google:gemini-3.5-flash` | — | não executado nesta rodada — cota gratuita diária do AI Studio (20 req/dia) esgotada pelos testes do CP08–CP10 no mesmo dia; ver `CP10-pipeline.md` |

**O Haiku 4.5 reprovou de verdade, e é um achado de conteúdo, não um bug de config.** O
diagnóstico ficou correto na reconstrução da cadeia (critério 3: 2, critério 4: 2), mas a seção
de "pré-requisitos de migração" (seção 6 do formato esperado) avançou para desenho de solução —
propôs mecanismo de dupla escrita, validação por checksum, e até perguntou sobre tecnologia de
serialização (Avro/Protobuf/JSON) e warehouse alvo (Snowflake/BigQuery/Redshift). O prompt do
Elo 1 proíbe isso explicitamente ("Nenhuma recomendação de solução... este elo termina no
diagnóstico"), e o juiz pegou a violação com exemplos citados linha a linha. Isso é exatamente o
tipo de regressão sutil — o texto está bem escrito e parece útil, só que descumpre o contrato do
elo — que um assert de `contains`/`regex` não pegaria, e que o gate do CP10 existe para barrar.

**Revisão pós-lançamento:** o Google saiu da suíte de CI (free-tier de 20 req/dia derrubou o
pipeline por infraestrutura, não por qualidade — detalhe em
[`CP10-pipeline.md`](../../CP10-pipeline.md)). Reexecutado só com Haiku 4.5 depois da mudança: **o
mesmo achado se repete** — score 5/8, critério 2 (escopo) zerado, com o juiz citando os mesmos
trechos problemáticos da seção de pré-requisitos. Confirma que é uma característica real e
reproduzível do comportamento do Haiku 4.5 neste prompt, não uma amostra isolada.

## Limitações conhecidas

- A qualidade de cada elo depende do anterior: um diagnóstico pobre propaga lacunas
  por toda a cadeia. O ganho é que a lacuna fica visível e rastreável, não escondida.
- O Elo 3 detalha **uma fase por execução** (`{{FASE_ALVO}}`); a migração completa
  exige rodar o Elo 3 para cada fase conforme suas lacunas forem fechadas.
- A cadeia produz plano e estratégia, não executa a migração — decisões marcadas
  NÃO PRONTAS exigem investigação humana (código/DAG, atomicidade de escrita) antes
  de avançar.
- Dados de cenário com identificadores internos devem ser sanitizados antes do envio
  a modelo externo.
