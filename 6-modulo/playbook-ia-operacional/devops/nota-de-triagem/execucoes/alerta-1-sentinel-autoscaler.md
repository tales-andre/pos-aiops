# Alerta 1 — Sentinel / autoscaler no teto (tenant stark-industries)

**Modelo:** Gemini 3.5 Flash (`gemini-3.5-flash`) via Google AI Studio · temperatura 1 (padrão) · thinking level Medium · grounding off

## Entrada (`{{ALERTA_CRU}}`)

```text
2026-05-12 14:02:09 UTC [Sentinel] autoscaler hit max replicas (60/60) on sentinel-api,
queue depth on Relay growing 2k/min, CPU avg 88%, tenant stark-industries
sending 4x baseline volume after onboarding new region
```

## Saída do modelo (nota de triagem)

```text
ALERTA: Sentinel - autoscaler hit max replicas (60/60) on sentinel-api, queue depth on Relay growing 2k/min, CPU avg 88%
IMPACTO: API e dashboards do Sentinel degradados para todos os tenants
HIPÓTESE INICIAL: onboarding de nova região do tenant stark-industries enviando 4x o volume baseline
AÇÃO IMEDIATA: rate limit temporário aplicado para o tenant stark-industries
ESCALAR PARA: @plantao-plataforma se sentinel-api não estabilizar em 15min
```
