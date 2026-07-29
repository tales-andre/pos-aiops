# Entrada 1 — pod reiniciando (CrashLoopBackOff / OOMKilled)

**Modelo:** Gemini 3.5 Flash (`gemini-3.5-flash`) via Google AI Studio · thinking level: Medium · grounding: off

## Entrada (`{{snapshot}}`)

```text
$ kubectl get pods -n sentinel-prod
NAME                            READY   STATUS             RESTARTS       AGE
sentinel-api-7d9c8b6f4-2xk9p    1/1     Running            0              6d
sentinel-api-7d9c8b6f4-h4m2t    0/1     CrashLoopBackOff   14 (90s ago)   42m
sentinel-worker-5b8f9c8d-jq7rs  1/1     Running            0              6d
sentinel-scheduler-6c4d7f-nn8vx 1/1     Running            0              6d
$ kubectl describe pod sentinel-api-7d9c8b6f4-h4m2t -n sentinel-prod
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
    Limits:         memory: 512Mi
    Requests:       memory: 256Mi
Events:
  Type     Reason   Age                 From     Message
  ----     ------   ----                ----     -------
  Warning  BackOff  2m (x18 over 40m)   kubelet  Back-off restarting failed container api
$ kubectl logs sentinel-api-7d9c8b6f4-h4m2t -n sentinel-prod --previous
2026-05-13 10:14:02 [INFO]  [api] startup complete, version 2.9.1
2026-05-13 10:14:48 [INFO]  [cache] loading 6h alert cache (heap 410Mi/512Mi)
2026-05-13 10:15:10 [WARN]  [runtime] high GC pressure, heap 498Mi/512Mi
2026-05-13 10:15:12 [FATAL] [runtime] out of memory, shutting down process
```

## Saída do modelo

🔺 RESUMO

Um dos dois pods da API (sentinel-api) está em falha intermitente devido a estouro do limite de memória (OOMKilled) durante a inicialização ao carregar o cache de alertas. Há perda de redundância no serviço de API, embora uma réplica ainda esteja operacional.

Pods analisados: 4 · Problemáticos: 1 · Saudáveis: 3

🚨 PODS PROBLEMÁTICOS
[ALTO] sentinel-api-7d9c8b6f4-h4m2t — sentinel-prod

Estado: CrashLoopBackOff · 0/1 · 14 restarts
Sinais cruzados:

get: Em CrashLoopBackOff há 42 minutos, com reinicializações frequentes (última há 90 segundos).

events: O contêiner foi encerrado pelo sistema operacional/kubelet com status OOMKilled (Exit Code 137), indicando que ultrapassou o limite físico de memória configurado em 512Mi.

logs: A aplicação acusa alta pressão de Garbage Collection (heap 498Mi/512Mi) e encerra com erro fatal (out of memory) logo após iniciar o carregamento de 6 horas do cache de alertas.

Causa provável: O limite de memória de 512Mi definido no Kubernetes é insuficiente para a carga inicializada pela aplicação (o cache de alertas consome quase todo o heap disponível logo no boot). O crash ocorre de forma consistente durante a rotina de inicialização do cache.

Ação agora:

Aumente temporariamente o limite de memória (limits.memory) do deployment sentinel-api para no mínimo 1Gi para estabilizar o ambiente.

Monitore se o pod afetado entra em estado Running estável após a alteração.

Se não resolver: Investigue a possibilidade de reduzir o intervalo de tempo do cache inicial carregado pela aplicação através de variáveis de ambiente, ou analise possíveis vazamentos de memória (memory leaks) na versão 2.9.1.

🔍 PONTOS CEGOS

Métricas de consumo do pod saudável: Não há dados de uso de recursos do pod sentinel-api-7d9c8b6f4-2xk9p para avaliar se ele também está operando próximo do limite de 512Mi.
-> Verifique com: kubectl top pod sentinel-api-7d9c8b6f4-2xk9p -n sentinel-prod

⚡ SE VOCÊ SÓ TEM 60 SEGUNDOS

Execute o comando abaixo para elevar o limite de memória da API para 1Gi e permitir que a réplica inicialize o cache com segurança:

kubectl set resources deployment sentinel-api -n sentinel-prod --limits=memory=1Gi
