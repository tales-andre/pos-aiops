# CP09 — Gate de qualidade com LLM-as-judge

**Config:** [`devops/causa-raiz/promptfooconfig.yaml`](./devops/causa-raiz/promptfooconfig.yaml)
**Rubrica, gate e resultado real:** seção "Gate de qualidade — LLM-as-judge (CP09)" de
[`devops/causa-raiz/README.md`](./devops/causa-raiz/README.md).
**Calibração do juiz:** [`devops/causa-raiz/calibracao/`](./devops/causa-raiz/calibracao/README.md)

## A rubrica (4 critérios, escala 0–2, corte ≥6)

1. **Causa-raiz correta** — aponta a causa real, não só o sintoma.
2. **Correlação × causa** — separa causa de consequência.
3. **Ação proporcional** — nem sobre nem subdimensionada.
4. **Honestidade epistêmica** — não fabrica certeza onde os dados não sustentam.

**Corte:** nota total ≥ 6 (de 0–8) **e** nenhum critério individual zerado.

## Resumo executivo

- **Calibração:** rodei o juiz (`claude-opus-5`) contra duas saídas fixas — a real do CP03
  (forte) e uma amostra sintética deliberadamente fraca (calibração, não execução real) — e
  comparei com minha nota manual. Maior divergência: 1 ponto num critério, dentro da
  tolerância pedida. Nenhum ajuste no `rubricPrompt` foi necessário.
- **Gate real**, rodado contra duas gerações reais da causa-raiz do incidente do CP03:

  | Provider | Score | Gate |
  |---|---|---|
  | `anthropic:messages:claude-haiku-4-5-20251001` | 7/8 | ✅ PASS |
  | `google:gemini-3.5-flash` | 6/8 | ❌ FAIL — honestidade zerada |

  O Gemini somou 6 (passaria num corte só por soma) mas **fabricou uma causa sem suporte nos
  artefatos** e rotulou uma inferência como `[ESTABELECIDO]` — o critério de honestidade foi
  a zero e a regra composta (soma ≥ 6 E nenhum critério zerado) reprovou corretamente. Esse é
  o caso concreto que justifica a regra composta em vez de só um corte numérico.
- **Um bug de configuração corrigido antes do resultado acima ser confiável:** o `max_tokens`
  padrão dos dois providers geradores cortava a saída de causa-raiz (9 seções, mais longa que
  qualquer prompt do CP08) no meio do relatório — o que produzia reprovações e um erro de
  parsing no juiz que não refletiam a qualidade real do modelo. Corrigido com `max_tokens`/
  `maxOutputTokens: 8192` explícitos. Detalhe completo na curadoria do README da causa-raiz.

## Por que só causa-raiz

O checkpoint pede o gate para os prompts de saída aberta que o CP08 não cobriu (causa-raiz,
backpressure, migração), mas escreve a tarefa em cima de um único config,
`devops/causa-raiz/promptfooconfig.yaml`, com a rubrica específica desse prompt — os outros
dois ficam de fora do escopo desta entrega.
