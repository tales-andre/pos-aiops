---
nome: Triagem de Pods
descricao: Diagnostica pods problemáticos de um cluster Kubernetes a partir de um snapshot, cruzando status, eventos e logs para chegar à causa provável e à ação de plantão.
versao: 1.0.0
tags: [devops, kubernetes, sre, troubleshooting, plantao]
inputs:
  - nome: snapshot
    descricao: Snapshot bruto do cluster — saída concatenada de kubectl get pods, kubectl describe pod e kubectl logs — colada na entrada.
---

# Triagem de Pods

## Objetivo

Dar ao plantonista de SRE uma triagem rápida e confiável da saúde dos pods de um
cluster Kubernetes. O prompt recebe um snapshot **já coletado** (não executa nada
no cluster) e devolve, para cada pod problemático, a **causa provável** — obtida
cruzando status, eventos e logs — mais a **próxima ação** do plantão. Quando não
há nada problemático, ele diz isso explicitamente, sem inventar achado.

## Quando usar

- Primeira leitura de um incidente: "o que está quebrado agora e o que faço?".
- Passagem de turno: consolidar o estado de um namespace em segundos.
- Confirmar que um cluster está saudável antes/depois de um deploy.

Não substitui investigação profunda — é a camada de triagem que aponta para onde
olhar.

## Parâmetros

| Parâmetro | Descrição |
|-----------|-----------|
| `{{snapshot}}` | Saída bruta concatenada de `kubectl get pods`, `kubectl describe pod` e `kubectl logs` (com `--previous` quando houver). Pode estar truncado, fora de ordem ou com múltiplos namespaces. |

## Exemplo de uso

Substitua `{{snapshot}}` pela coleta do cluster:

```text
$ kubectl get pods -n sentinel-prod
NAME                            READY   STATUS             RESTARTS       AGE
sentinel-api-7d9c8b6f4-h4m2t    0/1     CrashLoopBackOff   14 (90s ago)   42m
...
$ kubectl describe pod sentinel-api-7d9c8b6f4-h4m2t -n sentinel-prod
    Last State: Terminated  Reason: OOMKilled  Exit Code: 137
    Limits: memory: 512Mi
...
$ kubectl logs sentinel-api-7d9c8b6f4-h4m2t -n sentinel-prod --previous
[FATAL] [runtime] out of memory, shutting down process
```

Saída (resumida): identifica o pod, aponta a causa **OOMKilled / limite de 512Mi
insuficiente** (não apenas "CrashLoopBackOff"), marca o crash loop como sintoma e
recomenda `kubectl set resources ... --limits=memory=1Gi`. Execução completa em
[`execucoes/`](./execucoes/).

## Execução

Rodado contra os três snapshots de exemplo do desafio, com **Gemini 3.5 Flash**
(`gemini-3.5-flash`) no Google AI Studio (thinking level Medium, grounding off):

| Caso | Cenário | Resultado |
|------|---------|-----------|
| [Entrada 1](./execucoes/entrada-1-crashloop-oom.md) | Pod em CrashLoopBackOff | Chega em OOMKilled / heap 512Mi; crash loop tratado como sintoma. |
| [Entrada 2](./execucoes/entrada-2-imagepull-pending.md) | Dois pods que não sobem | Cita os dois: tag `2.9.2` inexistente (`manifest unknown`) e `Insufficient cpu`, com severidades distintas. |
| [Entrada 3](./execucoes/entrada-3-saudavel.md) | Cluster saudável | Declara "sem achados"; trata `RESTARTS 1 (3d ago)` como evento antigo já estabilizado, sem inventar problema. |

## Curadoria

- **Framework: RISE** (Role · Input · Steps · Expectation). A tarefa é diagnóstico
  com saída estruturada, e o componente **Steps** permite impor o procedimento de
  raciocínio ("cruze STATUS + Events + Logs antes de concluir"). RTF/TAG não têm
  slot para o raciocínio; CARE arriscaria o modelo copiar a causa do exemplo; BAB
  é para transformação de estado, não diagnóstico.
- **Regra central explícita:** a seção "COMO DIAGNOSTICAR" separa o papel de cada
  fonte (STATUS = *que*, Events = *onde*, Logs = *por quê*) e exige a interseção.
  É o que faz o modelo chegar em OOMKilled em vez de repetir CrashLoopBackOff.
- **Blindagem do caso saudável:** a definição de "pod problemático" e a seção
  "HONESTIDADE E LIMITES" impedem falso positivo — validado na Entrada 3, onde o
  `RESTARTS 1 (3d ago)` não virou alerta.
- **Formato de saída fixo** (RESUMO, PODS PROBLEMÁTICOS por severidade, SEM
  ACHADOS, PONTOS CEGOS, 60 SEGUNDOS) deixa a saída legível e testável — base para
  os asserts determinísticos do Checkpoint 08.
- **Escolha de modelo:** Gemini 3.5 Flash equilibra qualidade de raciocínio e
  custo. Alternativa mais barata (Flash Lite) fica anotada para o CP08, onde o
  teto de custo por chamada pesa na decisão.

## Limitações conhecidas

- Diagnostica **apenas com o que está no snapshot**: se faltarem logs ou eventos,
  entrega hipótese (marcada como tal) e o comando que fecharia a lacuna.
- Não acessa o cluster nem métricas de uso (`kubectl top`) — não confirma consumo
  real de recursos, só o declarado nos limits/requests.
- Qualidade depende da coleta: um snapshot enviesado (só um pod, sem describe)
  reduz a profundidade do diagnóstico.
- Dados de produção devem ser sanitizados antes do envio a modelo externo
  (hostnames internos, nomes de tenant) — ver nota de sanitização do playbook.
