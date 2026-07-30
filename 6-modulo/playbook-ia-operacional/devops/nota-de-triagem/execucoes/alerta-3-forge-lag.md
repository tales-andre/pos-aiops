# Alerta 3 — Forge / consumer lag (batch atrasado)

**Modelo:** Gemini 3.5 Flash (`gemini-3.5-flash`) via Google AI Studio · temperatura 1 (padrão) · thinking level Medium · grounding off

## Entrada (`{{ALERTA_CRU}}`)

```text
2026-05-13 11:40:22 UTC [Forge] consumer lag 9min and climbing, batch forge-batch-ingest
delayed after previous job failure, downstream Sentinel starting to lag
```

## Saída do modelo (nota de triagem)

```text
ALERTA: Forge - consumer lag de 9min e subindo às 11:40:22 UTC
IMPACTO: visualização de dashboards no Sentinel atrasada para todos os tenants
HIPÓTESE INICIAL: atraso no batch forge-batch-ingest após falha do job anterior
AÇÃO IMEDIATA: reprocessamento do job forge-batch-ingest iniciado
ESCALAR PARA: @data-platform se lag não reduzir em 20min
```
