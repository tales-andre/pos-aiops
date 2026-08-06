---
nome: Decisão de Backpressure
descricao: "Apoia uma decisão de arquitetura sob sobrecarga comparando várias opções contra as restrições (SLA, orçamento, perda de dado) antes de recomendar, com matriz de decisão e recomendação em camadas."
versao: 1.0.0
tags: [devops, arquitetura, backpressure, sre, decisao]
inputs:
  - nome: ESTADO_ATUAL
    descricao: Estado atual do sistema sob sobrecarga (throughput, pico, retenção, consumidores) em números.
  - nome: RESTRICOES
    descricao: Restrições que a solução precisa satisfazer (SLAs, orçamento, invariantes como não perder dado).
  - nome: OPCOES_EM_MESA
    descricao: Opções que o time já levantou; não é lista fechada nem endosso.
---

# Decisão de Backpressure

## Objetivo

Instruir uma decisão de arquitetura cara — como segurar a sobrecarga de um barramento
de eventos (backpressure) — sem cuspir uma resposta única. O prompt recebe o estado
atual, as restrições e as opções em mesa, e força a IA a **comparar mais de um caminho**:
quantifica o gap, identifica a restrição vinculante, pontua cada opção contra cada
restrição numa matriz, expõe o preço de cada uma, reprova as inadequadas com o
mecanismo da falha e recomenda em camadas por reversibilidade crescente. O raciocínio
importa tanto quanto a recomendação.

## Quando usar

- Decisões de capacidade / backpressure / priorização sob SLA e orçamento.
- Qualquer escolha de arquitetura com múltiplas opções e restrições em tensão, onde
  o custo do erro justifica ver a matriz antes da recomendação.
- Não decide sozinho: entrega a matriz e a recomendação em camadas para quem assina.

## Parâmetros

| Parâmetro | Descrição |
|-----------|-----------|
| `{{ESTADO_ATUAL}}` | Estado atual em números (throughput, pico, retenção, consumidores). |
| `{{RESTRICOES}}` | Propriedades que a solução precisa ter (SLAs, orçamento, não perder dado). |
| `{{OPCOES_EM_MESA}}` | Opções já levantadas pelo time — não fechada, não ordenada, não endossada. |

## Exemplo de uso

Preencha os três parâmetros com o cenário (estado + restrições + opções) e envie. A
saída são nove seções: leitura do gap, restrição vinculante, matriz de decisão,
preço de cada opção, opções reprovadas, recomendação em camadas, orçamento, lacunas
que podem inverter a recomendação e falsificador. Execução completa sobre o cenário
do Relay em [`execucoes/cenario-relay.md`](./execucoes/cenario-relay.md).

## Execução

Rodado sobre o cenário de sobrecarga do Relay (throughput 180k/s, pico 320k/s por
25min, retenção 4h; SLAs de Sentinel ≤60s e Forge ≤15min; orçamento +8%; proibição de
perda de telemetria), com **Gemini 3.6 Flash** (`gemini-3.6-flash`). Resultado resumido:

- **Gap:** déficit de 140k msgs/s no pico → **210M msgs** acumuladas; tempo de drenagem
  marcado NÃO DECIDÍVEL (falta a taxa pós-pico), com cenários extremos calculados.
- **Restrição vinculante:** SLA do Sentinel (≤60s), violado por 1.440s (2.400%) sem
  mitigação — margem muito maior que a do Forge.
- **Matriz 6×4** completa (opção nula + as 4 da mesa + quotas/backpressure fora da lista),
  com veredito numérico em cada célula.
- **Reprova** priorização, DLQ, divisão por cliente e quotas — cada uma pelo mecanismo
  da falha — e recomenda **autoscaling elástico** em camadas (isolamento de consumer
  groups → autoscaling por lag → buffer de retenção), com o **falsificador**: se o
  spin-up passar de 45s, a recomendação cai.

## Curadoria

- **Framework: BAB (Before-After-Bridge).** BEFORE = estado atual, AFTER = as restrições
  (o estado desejado expresso como propriedades a satisfazer), BRIDGE = o processo de
  10 passos que liga um ao outro. BAB é o encaixe certo porque a tarefa é uma **transição
  de estado sob restrição**, não um diagnóstico (RISE) nem uma saída de formato fixo
  (CARE). O "After" como conjunto de restrições — e não como solução — é o que impede o
  prompt de assumir a resposta antes de comparar.
- **Técnica: raciocínio comparativo (tree-of-thought).** O núcleo é gerar opções
  concorrentes (≥5, incluindo a nula e uma fora da lista) e pontuá-las numa matriz
  opção×restrição antes de qualquer recomendação. A regra "recomendação sem matriz
  completa é reprovada" é o que força a comparação em vez da resposta única.
- **Quantificação obrigatória:** "ATENDE sem número é reprovado" e "nunca estime dado
  ausente" transformam a matriz em algo auditável e mantêm a honestidade epistêmica
  (NÃO DECIDÍVEL como resultado válido).
- **Classificação de restrição** (contratual / estrutural / financeira) evita tratar
  orçamento como equivalente a SLA contratual na hora de pontuar — mapeia direto no
  cenário (Sentinel=contratual, não-perda=estrutural, orçamento=financeira).
- **Recomendação em camadas por reversibilidade** e o **falsificador** final entregam
  não só o quê, mas o que observar para saber que a decisão errou.
- **Execução no Gemini 3.6 Flash** (diferente do 3.5 usado nos CP01/02) para variar o
  modelo dentro do provedor Google; a tarefa é de raciocínio pesado (~49s) e o modelo
  respeitou a estrutura e as regras invioláveis sem encurtar a análise.

## Gate de qualidade — LLM-as-judge (CP10)

Saída aberta (matriz de decisão, sem resposta única) — mesmo padrão de gate do CP09 aplicado
aqui: [`promptfooconfig.yaml`](./promptfooconfig.yaml) gera a decisão de verdade com os dois
providers do CP08 (`claude-haiku-4-5-20251001` + `gemini-3.5-flash`) contra o cenário real do
Relay, e julga com um terceiro modelo (`claude-opus-5`) numa rubrica de 4 critérios: matriz
completa e honesta (todo `ATENDE` com número, nenhum dado ausente estimado), restrição
vinculante corretamente identificada, preço declarado + reprovação explícita de opção
inadequada, e recomendação em camadas com falsificador. Corte: soma ≥ 6 de 8 **e** nenhum
critério zerado — mesma regra composta da causa-raiz.

**Resultado real (`promptfoo eval`):**

| Provider | Score | Gate |
|---|---|---|
| `anthropic:messages:claude-haiku-4-5-20251001` | 7/8 | ✅ PASS |
| `google:gemini-3.5-flash` | 7/8 | ✅ PASS |

Nenhum ajuste foi necessário — os dois geradores produziram matriz completa, preço declarado e
falsificador presente na primeira execução real. No pipeline do CP10, este teste roda com
`repeat: 3` / `repeat-min-pass: 2` (não 1 execução só), pela mesma razão do CP09: um juiz LLM
pode flutuar, e uma reprovação isolada não deveria derrubar o PR sozinha.

## Limitações conhecidas

- A qualidade da matriz depende de o cenário trazer números; sem eles, o prompt produz
  a matriz toda como NÃO DECIDÍVEL e devolve a lista de medições necessárias (é o
  comportamento correto, mas não é uma recomendação acionável).
- Não valida os números do cenário: se a entrada estiver errada, a matriz herda o erro.
- A recomendação é insumo para decisão humana, não uma decisão automática — o próprio
  prompt devolve conflitos irreconciliáveis ao humano em vez de arbitrar.
- Dados de cenário com identificadores sensíveis (tenant, cliente) devem ser
  sanitizados antes do envio a modelo externo.
