# Calibração do juiz (CP09)

Antes de confiar o gate de qualidade da causa-raiz a um LLM-as-judge, calibrei o juiz contra
minha própria nota manual — método pedido pelo checkpoint: "pontue você mesmo algumas saídas
e ajuste o prompt do juiz até a nota dele ficar a no máximo 1 ponto da sua em cada critério".

## Método

Duas fixtures fixas, julgadas via provider `echo` (não gera nada — só entrega o texto pro juiz
avaliar), para isolar a qualidade do **juiz** da qualidade do **gerador**:

- [`fixture-forte.md`](./fixture-forte.md) — a saída real do CP03 (Claude Opus 5), já
  verificada manualmente como análise completa e correta.
- [`fixture-fraca.md`](./fixture-fraca.md) — amostra sintética, escrita deliberadamente fraca
  (**não é uma execução real do prompt**, está marcada como tal no próprio arquivo): inverte
  causa e efeito, propõe reinício de nó com o circuit breaker ativo, e fabrica uma causa
  ("falha de rede") sem suporte nos artefatos.

Rodar: `promptfoo eval -c calibracao.promptfooconfig.yaml --no-cache`.

## Minha nota manual vs. a nota do juiz

| Critério | Fixture forte — manual | Fixture forte — juiz | Fixture fraca — manual | Fixture fraca — juiz |
|---|---|---|---|---|
| 1. Causa-raiz correta | 2 | 2 | 1 | 0 |
| 2. Correlação × causa | 2 | 2 | 0 | 0 |
| 3. Ação proporcional | 2 | 2 | 0 | 0 |
| 4. Honestidade epistêmica | 2 | 2 | 0 | 0 |
| **Total** | **8** | **8** | **1** | **0** |
| Gate | PASS | PASS | FAIL | FAIL |

Maior diferença: 1 ponto (critério 1 da fixture fraca — eu dei crédito parcial por ela citar
"heap elevado" de passagem; o juiz não deu, porque a fixture não conecta isso à reindexação
nem ao horário comercial, então nem chega a ser um começo de causa correta). **Dentro da
tolerância de 1 ponto pedida pelo checkpoint em todos os 8 pares critério×fixture.**

## O que foi ajustado

**Nada precisou ser ajustado no `rubricPrompt` — passou na primeira tentativa.** O que tornou
isso possível, e que registro aqui porque é a parte replicável do método:

1. **A fixture fraca foi desenhada para forçar cada critério a falhar por um motivo
   diferente** (causa incompleta, correlação invertida, ação perigosa, honestidade fabricada)
   — sem isso, uma calibração com só a fixture forte não prova que o juiz sabe reprovar, só
   que ele sabe aprovar algo já obviamente bom.
2. **O `rubricPrompt` pede o raciocínio por critério dentro de `reason` antes do número final**
   — isso faz o juiz "mostrar o trabalho" em vez de só cuspir uma nota, o que tanto melhora a
   qualidade da nota (menos atalho) quanto torna a divergência auditável quando existe.
3. **`pass` é calculado pelo próprio juiz seguindo a regra composta** (total ≥ 6 E nenhum
   critério zerado), não só um threshold numérico do promptfoo — necessário porque "nenhum
   critério zerado" não é expressável só com `threshold` sobre a soma. Isso foi testado de
   verdade na execução real do gate (não na calibração): ver `README.md` da causa-raiz,
   caso em que o Gemini somou 6 mas zerou honestidade e foi reprovado — provando que a regra
   composta está ativa, não só decorativa.

## Um bug de configuração encontrado (não do juiz)

A primeira rodada do gate **real** (fora desta calibração, contra saídas geradas de verdade)
deu um falso "erro de parsing" no Gemini e depois um falso reprovado no Haiku — não porque o
juiz calibrado errou, mas porque o `max_tokens` padrão dos providers geradores cortava a saída
de causa-raiz no meio (é um prompt de 9 seções, bem mais longo que os do CP08). Corrigido
subindo `max_tokens`/`maxOutputTokens` para 8192 nos dois geradores. Detalhe completo na seção
"Testes de qualidade (CP09)" do `README.md` da causa-raiz.
