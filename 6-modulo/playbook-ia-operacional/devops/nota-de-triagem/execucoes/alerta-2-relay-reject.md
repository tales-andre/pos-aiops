# Alerta 2 — Relay / taxa de rejeição (tenant wakanda-systems)

**Modelo:** Gemini 3.5 Flash (`gemini-3.5-flash`) via Google AI Studio · temperatura 1 (padrão) · thinking level Medium · grounding off

## Entrada (`{{ALERTA_CRU}}`)

```text
2026-05-13 03:11:00 UTC [Relay] ingest reject rate 6% for 8min, tenant wakanda-systems,
buffer saturated after deploy 02:55
```

## Saída do modelo (nota de triagem)

```text
ALERTA: Relay - ingest reject rate de 6% por 8min
IMPACTO: ingestão de telemetry degradada para o tenant wakanda-systems
HIPÓTESE INICIAL: deploy das 02:55 causou saturação do buffer
AÇÃO IMEDIATA: rollback do deploy iniciado
ESCALAR PARA: @relay-core se taxa de rejeição não cair em 10min
```
