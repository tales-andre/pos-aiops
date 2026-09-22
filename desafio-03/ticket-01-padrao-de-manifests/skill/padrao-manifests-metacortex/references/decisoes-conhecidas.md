# Decisões conhecidas

Situações em que o padrão não tem resposta pronta e alguém já teve que decidir. Abra quando o
projeto que você está empacotando cair num destes casos — a decisão já foi discutida, e repetir a
discussão do zero custa tempo e tende a produzir resposta pior.

Cada entrada traz o que foi descartado e o custo do caminho escolhido. Se o seu caso for
diferente, decida diferente — mas declare o custo do mesmo jeito.

---

## A aplicação não expõe endpoint de saúde

**Quando aparece.** A regra 2.2 exige readiness e liveness apontando para endpoints que a
aplicação de fato expõe, e o projeto não tem `/health` nem `/ready`. Aconteceu com o `fake-shop`.

**O que não fazer.** Apontar as probes para uma rota de negócio, como `/` ou `/shop`. Essas rotas
consultam o banco, e é exatamente a armadilha que o padrão descreve: banco lento derruba a
liveness, o container reinicia, e o reinício não conserta banco. Com mais de uma réplica, a
cascata derruba o serviço inteiro.

**O que fazer.** Procure a rota mais barata que a aplicação já expõe e que não toque o banco. Em
projeto instrumentado com Prometheus, costuma ser `/metrics`. Se não houver nenhuma,
`tcpSocket` na porta do processo é mais honesto que um `httpGet` que mente.

**O custo a declarar.** A readiness passa a afirmar "o processo subiu", não "consigo atender". Se
a dependência estiver fora, o pod continua recebendo tráfego e devolvendo erro. A correção de
verdade é a aplicação passar a expor `/health` e `/ready` — isso é pedido para o time dono, e vale
registrar na anotação de runbook ou no PR.

---

## A migração de banco roda no start da aplicação

**Quando aparece.** O entrypoint do projeto roda a migração antes de subir o servidor. Aconteceu
com o `fake-shop` (`flask db upgrade` no `entrypoint.sh`).

**Por que vira problema.** A regra 2.3 exige duas réplicas em prod e a 2.4 exige
`maxUnavailable: 0`, o que durante um rollout chega a três pods simultâneos. Todos executam a
migração no mesmo banco ao mesmo tempo.

**O que não fazer.** Mover para `initContainer` — roda uma vez por pod, então tem a mesma corrida,
só que mais cedo. Confiar no lock do migrador também não resolve: a maioria não serializa isso de
forma confiável.

**O que fazer.** Extrair a migração para um `Job` próprio e sobrescrever `command`/`args` no
container da aplicação, para que ele ignore o entrypoint e suba só o servidor.

**O custo a declarar.** Passa a existir ordem de aplicação — o Job antes do Deployment — e essa
ordem não está expressa em nenhum dos dois arquivos. Quem aplicar fora de ordem sobe a aplicação
contra um schema velho.

---

## `readOnlyRootFilesystem` contra uma aplicação que precisa escrever

**Quando aparece.** A regra 3.2 exige `readOnlyRootFilesystem: true` e o processo quebra ao subir.
Aconteceu com o `fake-shop`, que usa `PROMETHEUS_MULTIPROC_DIR` e precisa de `/tmp`.

**O que fazer.** `emptyDir` montado exatamente nos caminhos que a aplicação escreve — o próprio
padrão prevê isso. Descobrir quais caminhos são esses exige ler o projeto: variáveis de ambiente
que apontam para diretório, uso de arquivo temporário, cache local, socket em disco.

**O custo a declarar.** `emptyDir` morre com o pod. Se o que está sendo escrito precisa sobreviver
a um restart, `emptyDir` é a resposta errada e o caso vira volume persistente — o que muda o
desenho do workload.

---

## Os quatro rótulos no selector, e a imutabilidade

**Quando aparece.** A regra 1.4 pede selector idêntico aos rótulos do pod, e a 1.3 pede quatro
rótulos. A leitura literal leva a repetir os quatro no `matchLabels`.

**O custo a declarar.** `matchLabels` é imutável num Deployment. `app.kubernetes.io/managed-by`
muda quando o workload migra de `platform` para `argocd` — e nesse dia o Deployment precisa ser
recriado, não atualizado. Vale escrever isso no PR para o dia em que acontecer.

---

## Banco de dados no mesmo pacote do workload

**Quando aparece.** O projeto depende de Postgres e alguém quer versionar o banco junto.

**O que observar.** A imagem oficial do Postgres colide com a 3.2 em dois pontos —
`runAsNonRoot` e `readOnlyRootFilesystem` — o que exigiria exceção escrita de Segurança, com prazo
de validade. Banco também não é workload sem estado, então 2.3 e 2.4 não se aplicam do mesmo jeito.

**O que fazer.** Trate o banco como infraestrutura, fora do pacote do workload, a menos que exista
decisão contrária registrada.

---

## A imagem que existe não vem do registry interno

**Quando aparece.** A regra 3.7 exige `registry.metacortex.io`, mas a imagem que roda de verdade
no seu ambiente de teste vem de outro lugar.

**O que fazer.** O manifesto entregue aponta para o registry interno. A troca para rodar local é
sobreposição de ambiente — kustomize, variável no pipeline, ou edição fora do arquivo versionado.
Nunca a troca ao contrário: manifesto que vai para revisão com registry público barra.
