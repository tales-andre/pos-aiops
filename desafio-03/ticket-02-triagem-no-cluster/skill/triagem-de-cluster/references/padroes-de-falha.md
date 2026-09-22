# Assinaturas de falha já observadas no parque

Cada entrada traz o que a falha parece na superfície, o que a distingue de falhas parecidas, e
onde a causa realmente estava. Abra quando o retrato do namespace não for conclusivo de imediato.

O que une as três: **em todas havia algo saudável ao lado do que quebrou**. É esse contraste que
encurta a triagem.

---

## Container morre e volta, em laço

**Superfície:** `CrashLoopBackOff`, contador de reinícios subindo, `READY 0/1`.

**A armadilha:** os eventos **não dizem a causa**. Eles trazem `BackOff restarting failed
container`, que só repete o sintoma. Quem começa a triagem pelos eventos não encontra nada e passa
para os logs, que também não ajudam — o processo morre antes de escrever algo útil.

**Onde a causa está:** `status.containerStatuses[].lastState.terminated`, no próprio pod.

| Campo | O que significa |
|---|---|
| `reason: OOMKilled`, `exitCode: 137` | o kernel matou por memória; compare com `limits.memory` |
| `exitCode: 1` com `reason: Error` | a aplicação decidiu sair; agora sim, leia o log |
| `exitCode: 0` | terminou "com sucesso" e o controlador reiniciou — provável erro de comando |

**Detalhe que confunde:** um pod em `CrashLoopBackOff` continua com `phase: Running`. O estado de
falha vive no container, não no pod, então filtrar por fase esconde o problema.

**Caso real (nyx-prod):** `OOMKilled`, `exitCode 137`, contra `limits: {memory: 24Mi}`. Veio de
uma passada de corte de custo que apertou os limites do namespace inteiro sem olhar consumo. O
Postgres ao lado seguia `1/1` porque não tinha limite nenhum declarado.

---

## Pod nunca troca depois de um deploy

**Superfície:** `ImagePullBackOff` ou `ErrImagePull`, `READY 0/N`, e a versão antiga continua
servindo — ou nada serve, se foi a primeira subida.

**O que distingue:** aqui o container nunca executou. Ler log é desperdício, e `describe` do pod já
basta.

**Onde a causa está:** `state.waiting.message`, cruzado com a imagem declarada no Deployment. E
então **fora do cluster** — o cluster só sabe que tentou e não conseguiu.

| Mensagem | Causa provável |
|---|---|
| `manifest unknown` / `not found` | a tag não existe no registry |
| `no match for platform in manifest` | a imagem existe, mas não para a arquitetura do nó |
| `unauthorized` / `authentication required` | credencial de registry ausente ou expirada |
| `context deadline exceeded` | rede ou registry fora do ar |

**Caso real (orion-stg):** tag `v1.14.2` anunciada num release e aplicada no Deployment, mas
inexistente no registry — o repositório publica `v1`, `v2`, `v13`, `v26`, e nada com `1.14.2`. O
Postgres ao lado subiu normal, o que descarta rede e nó de uma vez.

---

## Aplicação saudável e ninguém chega nela

**Superfície:** erro de fora, tipicamente 503, com os pods `Running` e `1/1`.

**O que distingue:** esta é a única das três em que a camada de container está inteira. Se você
ainda está olhando pod, está na camada errada.

**Onde a causa está:** no objeto `Endpoints` do Service. Se ele não traz endereço, nenhum pod
casou com o selector.

**Detalhe da API:** quando não há endereço, o campo **não vem vazio — ele não vem**. Código que
espera lista vazia quebra, e olho humano que procura `[]` não acha. O `Endpoints` também está a
caminho da aposentadoria; a informação equivalente vive em `EndpointSlice`.

**Como confirmar em um passo:** compare `spec.selector` do Service com `metadata.labels` do
template do pod. Diferença de um hífen já basta.

**Caso real (nyx-stg):** Service selecionando `app: nyx-api`, pods rotulados `app: nyxapi`. Os dois
`Deployment` e `Service` subiram sem erro, a revisão passou, e o serviço nunca entregou tráfego. O
`nyx-postgres` no mesmo namespace tinha endpoint normal — o contraste entre os dois Services é o
que aponta o dedo para o metadado.
