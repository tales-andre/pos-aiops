# Conferência — `manifests/nyx-api-barrado.yaml`

Workload: kube-news (imagem `registry.metacortex.io/nyx/api`), cliente nyx, ambiente prod

Objetos no arquivo: `Deployment/NyxAPI` e `Service/nyx-api`, ambos em `nyx-prod`.
Camadas usadas: `trivy config` (saída em `trivy-config.txt`),
`scripts/conferir_manifests.py` (saída em `conferir-manifests.txt` / `.json`, código de retorno 1)
e leitura do repositório da aplicação em `~/pos-aiops/kube-news`.

## Barra

| Regra | Força | Esperado | Encontrado |
|---|---|---|---|
| 1.1 nome em kebab-case | obrigatório | minúsculas com hífen | `Deployment` chamado `NyxAPI` (linha 4) |
| 1.3 os quatro rótulos | obrigatório | os quatro `app.kubernetes.io` no objeto | `Deployment` só tem `app: nyxapi`; faltam `name`, `instance`, `part-of`, `managed-by` |
| 1.3 os quatro rótulos | obrigatório | os quatro `app.kubernetes.io` no objeto | `Service/nyx-api` não tem rótulo nenhum (não há bloco `labels`) |
| 1.4 selector casa com os rótulos do pod | obrigatório | `selector` idêntico, caractere por caractere, aos rótulos do pod | `Service.spec.selector: app: nyx-api` (linha 34) contra pod `app: nyxapi` (linha 16) — nenhum pod casa, o Service sobe sem endereço |
| 2.1 requests e limits | obrigatório | os quatro campos (`requests`/`limits` de cpu e memória) | nenhum bloco `resources` (Trivy KSV-0011, KSV-0015, KSV-0016, KSV-0018) |
| 2.2 readiness e liveness | obrigatório | as duas declaradas, apontando para endpoint que a aplicação expõe | faltam `readinessProbe` e `livenessProbe` — e a aplicação expõe `/ready` e `/health`, ver seção final |
| 2.3 replicas >= 2 em prod | obrigatório | >= 2 | `replicas: 1` (linha 9) |
| 2.4 estratégia de atualização | obrigatório em prod | `RollingUpdate` com `maxUnavailable: 0` e `maxSurge: 1` | bloco `strategy` ausente |
| 3.1 tag `:latest` | **proibido** | tag imutável ou digest | `registry.metacortex.io/nyx/api:latest` (linha 20, Trivy KSV-0013) |
| 3.2 securityContext | obrigatório | `runAsNonRoot`, `runAsUser`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: ["ALL"]` | nenhum `securityContext`, nem no pod nem no container (Trivy KSV-0001, 0003, 0004, 0012, 0014, 0020, 0021 e KSV-0118 HIGH nos dois níveis) |
| 3.3 segredo em texto puro | **proibido** | `valueFrom.secretKeyRef` | `DATABASE_URL` com a senha literal `s3nh4-do-banco` no `env.value` (linha 25) |
| 3.4 `automountServiceAccountToken` | obrigatório | `false` (o workload não fala com o apiserver) | campo ausente — o token é montado por padrão |

São 12 desvios que barram, sobre 9 regras distintas. Os nove primeiros vieram do script; 2.1, 3.1 e
3.2 vieram do Trivy.

Duas que merecem destaque separado, por serem as mais caras e as menos visíveis:

- **1.4.** É o único desvio aqui que não aparece em revisão nem no `kubectl apply`. O Deployment vai
  ficar `1/1`, o `Service` vai existir, e o objeto `Endpoints` não vem com lista vazia — o campo de
  endereços simplesmente não aparece. Sintoma no cliente: connection refused / 503 sem nenhum evento
  no Deployment. A diferença é literalmente o hífen: `nyxapi` no pod, `nyx-api` no Service.
- **3.3.** É `proibido` e não admite exceção para workload de cliente. O Trivy não pega isso — só o
  script pegou. Como o valor já está num arquivo versionado, trocar para `secretKeyRef` **não basta**:
  a credencial `nyx` / `s3nh4-do-banco` do Postgres `pg.nyx-prod.svc` precisa ser rotacionada, e o
  histórico do Git continua com ela. Isso é chamado para o time dono do banco, não só edição de YAML.
  Leia também o item 3 da última seção: essa variável nem é a que a aplicação usa.

## Justificar no PR

| Regra | Esperado | Encontrado |
|---|---|---|
| 1.5 anotação de dono | `metacortex.io/owner` com o time, e `metacortex.io/runbook` quando existir | nenhuma anotação; não há indicação de dono no manifesto nem no repositório da aplicação — não inventei um valor |
| 2.5 PodDisruptionBudget em prod | PDB com `minAvailable: 1` para workload de prod com mais de uma réplica | não existe PDB no pacote. Hoje o script não acusa porque `replicas: 1`; no momento em que 2.3 for corrigida para 2, a regra passa a valer e o desvio aparece |
| 2.6 `terminationGracePeriodSeconds` | declarar quando o padrão de 30s não serve, e garantir que a aplicação trata SIGTERM | campo ausente. Mais grave do que a ausência: a aplicação **não** trata SIGTERM (ver item 6 abaixo), então ajustar esse campo não compra nada enquanto o código não mudar |
| 3.5 ServiceAccount dedicada | uma SA por workload, sem RBAC quando não fala com a API | usa a `default` do namespace |

## Conforme

- **1.1** no `Service` — `nyx-api` está em kebab-case (o problema é só o Deployment).
- **1.2** namespace `nyx-prod` — formato `<cliente>-<ambiente>` com ambiente válido, nos dois objetos.
- **1.4 do lado do Deployment** — `matchLabels` (linha 12) é idêntico aos rótulos do template do pod
  (linha 16). Quem está fora de sincronia é o `Service`.
- **1.6** nome do container — `api`, não `app`/`main`/`container` (mas ver a ressalva no item 7).
- **3.6** `hostNetwork`, `hostPID`, `privileged` — nenhum declarado.
- **3.7** registry interno — `registry.metacortex.io`. O Trivy acusa `KSV-0125` ("untrusted registry")
  justamente contra esse registry, que é o único que o padrão aceita; o critério dele é o oposto do
  nosso. **Achado ignorado por decisão da skill** — vale o que o script diz sobre a 3.7.
- Porta: `containerPort: 8080` e `targetPort: 8080` batem com a porta em que o processo realmente
  escuta (`src/server.js:81`). O `port: 80` do Service é só a porta de serviço.

Achados do Trivy que **não** correspondem a regra do padrão, registrados como informação e não como
barramento: `KSV-0030` e `KSV-0104` (`seccompProfile.type: RuntimeDefault`). Não estão no Bloco 3;
se o time quiser incluir junto com o `securityContext` da 3.2, é ganho barato.

## O que só se descobre abrindo o projeto

Repositório lido: `~/pos-aiops/kube-news`. Aplicação Node.js/Express com Sequelize sobre Postgres.

1. **Porta e endpoints de saúde existem — este não é o caso "aplicação sem endpoint de saúde".**
   `src/server.js:81` faz `app.listen(8080)`. `src/system-life.js:11` expõe `GET /ready` e
   `src/system-life.js:22` expõe `GET /health`. **Nenhum dos dois consulta o banco**: `/health`
   devolve `{state, machine}` a partir de `os.hostname()`, e `/ready` compara duas datas em memória.
   Então a armadilha clássica da regra 2.2 (liveness que checa banco e reinicia container quando o
   banco fica lento) não se aplica aqui. As probes corretas são `httpGet` na porta 8080, readiness em
   `/ready` e liveness em `/health` — e elas podem apontar para lugares diferentes, como a regra pede.

2. **Ressalva sobre essas probes.** `src/server.js:22` registra `config.middlewares.healthMid` **antes**
   do router (`server.js:23`). Quando alguém aciona `PUT /unhealth`, esse middleware passa a devolver
   500 para todas as rotas do router — inclusive `/ready`. Ou seja, readiness e liveness compartilham
   o mesmo interruptor, e um `/unhealth` derruba as duas ao mesmo tempo. É aceitável (o interruptor é
   ferramenta de teste de caos, não caminho de produção), mas precisa estar escrito no PR: a readiness
   dessa aplicação afirma "o processo subiu", não "consigo atender" — ela não sabe se o Postgres
   respondeu. `/metrics` escapa do interruptor porque o middleware de métricas é registrado antes
   (`server.js:21`).

3. **`DATABASE_URL` não existe para esta aplicação.** `src/models/post.js:8-13` lê `DB_DATABASE`,
   `DB_USERNAME`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` e `DB_SSL_REQUIRE`. Não há nenhuma leitura de
   `DATABASE_URL` em lugar nenhum do código. Duas consequências:
   - o desvio da 3.3 é duplo: o manifesto vaza uma credencial de produção **e** injeta uma variável
     que o processo ignora;
   - com o manifesto como está, a aplicação sobe nos *defaults* do código —
     `localhost:5432`, usuário/base `kubedevnews`, senha `Pg#123` (`post.js:8-11`) — e nunca alcança
     `pg.nyx-prod.svc`. O time vai ver pod `Running` e erro de conexão.
   O campo que precisa virar `secretKeyRef` é **`DB_PASSWORD`**; `DB_HOST`, `DB_PORT`, `DB_DATABASE` e
   `DB_USERNAME` são configuração comum e podem ir por ConfigMap.

4. **A migração de schema roda no start — e a correção das regras 2.3 e 2.4 cria uma corrida.**
   `src/server.js:80` chama `models.initDatabase()`, que em `src/models/post.js:58-60` executa
   `seque.sync({ alter: true })` — ALTER TABLE no start de cada processo. Este é exatamente o caso
   registrado em `references/decisoes-conhecidas.md` ("A migração de banco roda no start da
   aplicação"): subir para `replicas: 2` (regra 2.3) com `maxUnavailable: 0` / `maxSurge: 1`
   (regra 2.4) coloca até três pods rodando `alter` no mesmo banco ao mesmo tempo. **Não basta
   corrigir 2.3 e 2.4 no YAML**: o caminho da casa é extrair a migração para um `Job` próprio e
   sobrescrever `command`/`args` no container para ele só subir o servidor. `initContainer` não
   resolve — roda uma vez por pod, mesma corrida mais cedo. Custo a declarar: passa a existir ordem de
   aplicação (Job antes do Deployment) que não está expressa em nenhum dos dois arquivos. Observação
   extra: `sync({ alter: true })` deixar o ORM alterar schema sozinho em produção já é questionável
   por si só, independente do número de réplicas.

5. **`readOnlyRootFilesystem: true` não precisa de `emptyDir` aqui.** Varri `src/` por `require('fs')`,
   `writeFile`, `/tmp` e `PROMETHEUS_MULTIPROC_DIR`: nenhuma ocorrência. As métricas usam
   `prom-client` 14 em processo único (`src/middleware.js`, `src/server.js:9-18`), sem diretório
   multiprocesso, e `src/static/` é só servido para leitura (`server.js:24`). Então a 3.2 pode ser
   aplicada inteira sem volume auxiliar. Se algum caminho gravável aparecer no primeiro deploy, aí sim
   `emptyDir` no caminho exato — mas não há indício no código.

6. **A aplicação não trata SIGTERM.** `src/server.js` não registra nenhum handler de sinal, não guarda
   o retorno de `app.listen()` e nunca chama `server.close()`. No `kubectl delete`/rollout o Node morre
   na hora e as requisições em voo caem. Isso afeta a 2.6 (aumentar o grace period não drena nada) e
   piora o efeito da 2.3 atual: com uma réplica só, todo deploy é indisponibilidade com erro, não
   apenas latência. A correção de verdade é pedido para o time dono da aplicação.

7. **Qual é o componente, afinal.** A aplicação é um portal de notícias que serve HTML por EJS
   (`server.js:27`, `src/views/`) e tem, de brinde, um `POST /api/post` (`server.js:55`). O container e
   a imagem chamam isso de `api`, o que descreve só parte do que roda. Antes de congelar
   `app.kubernetes.io/name`, confirme com o time se o componente é `api` ou `web` — o rótulo entra no
   inventário e no rateio, e trocar depois é mais caro.

8. **Não fala com o apiserver.** As dependências em `src/package.json` são `express`, `ejs`,
   `body-parser`, `sequelize`, `pg`, `pg-hstore`, `prom-client` e `express-prom-bundle` — nenhum client
   Kubernetes. Confirma que `automountServiceAccountToken: false` (3.4) é seguro e que a SA dedicada da
   3.5 vai sem RBAC nenhum.

9. **Dimensionamento (2.1): não há dado.** Não existe medição de consumo em regime deste workload à
   mão, então não dá para aplicar a regra de bolso de 1,5x a 2x. O manifesto precisa declarar os quatro
   campos de qualquer forma; o que couber ali deve ser marcado no PR como **provisório**, a ser
   revisado depois do primeiro período com métricas — a aplicação já expõe `/metrics`, então o dado
   existe assim que ela subir. Um chute apresentado como medida vira dado errado no inventário.

10. **Aviso para quem for corrigir a 1.3 junto com a 1.4.** Repetir os quatro rótulos em `matchLabels`
    é a leitura literal, mas `matchLabels` é imutável num Deployment, e
    `app.kubernetes.io/managed-by` muda no dia em que o workload migrar de `platform` para `argocd` —
    nesse dia o Deployment terá que ser recriado, não atualizado. Vale escrever isso no PR agora.

---

Veredito: **barrado**, e corretamente. 12 desvios que barram sobre 9 regras, sendo dois de regra
`proibido` (3.1 e 3.3). Além do YAML, três itens saem do escopo do manifesto e são chamado para o
time dono da aplicação: rotação da credencial já comitada, a migração no start (item 4) e o
tratamento de SIGTERM (item 6).
