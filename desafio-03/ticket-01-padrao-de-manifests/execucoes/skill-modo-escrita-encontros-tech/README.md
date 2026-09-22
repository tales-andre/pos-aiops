# encontros-tech — empacotamento para `helio-prod`

Workload: **encontros-tech**, cliente **helio**, ambiente **prod**.
Skill usada: `padrao-manifests-metacortex`, **modo escrita** (passos 1 a 5 do SKILL.md).
Fonte lida: `~/pos-aiops/encontros-tech` (commit `0f5bbad`, "Removendo Docker").

Entregue neste diretório:

| Arquivo | O que é |
|---|---|
| `encontros-tech-app.yaml` | ServiceAccount, Deployment, Service, PodDisruptionBudget |
| `encontros-tech-schema.yaml` | Job que cria o schema — **aplicar antes** do outro |
| `conferir-manifests.txt` / `.json` | saída do `scripts/conferir_manifests.py` sobre o que foi escrito |
| `trivy-config.txt` | saída do `trivy config` sobre o que foi escrito |

---

## 1. Os fatos que vieram do projeto

Isto é o que nenhuma ferramenta descobre sozinha — veio de ler o código.

### Porta

**8000.** Duas fontes concordam: `EXPOSE 8000` e
`CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "main:app"]` no `src/Dockerfile` (removido
no commit `0f5bbad`, recuperado com `git show 0f5bbad^:src/Dockerfile`), e
`PORT=8000` no `.env.exemple`.

**Armadilha registrada:** a variável `PORT` **não** muda a porta em produção.
`src/main.py:63` só usa `settings.PORT` dentro de `if __name__ == '__main__'`, que é o
servidor de desenvolvimento do Flask. Sob gunicorn quem manda é o `-b` do `CMD`. Por isso
o manifesto **não** declara `PORT`: declarar sugeriria um controle que não existe. Mudar a
porta exige mudar a imagem.

### Endpoints

Levantados em `src/routers/page_router.py`, `src/routers/api_router.py` e `src/main.py`:

| Rota | Origem | Toca o banco? |
|---|---|---|
| `GET /` | `page_router.py:17` | **sim** (`get_events`) |
| `GET /events/new` | `page_router.py:42` | não (só renderiza template) |
| `GET /events/<int:id>` | `page_router.py:61` | **sim** |
| `GET /events/edit/<token>` | `page_router.py:47` | **sim** |
| `POST /events/` e `POST /events/edit/<token>` | `page_router.py:75,116` | **sim** |
| `POST /api/events/`, `GET /api/events/`, `GET|PUT /api/events/by-token/<token>` | `api_router.py` | **sim** |
| `GET /metrics` | `PrometheusMetrics(app)` em `src/main.py:35` | **não** |

**Não existe `/health` nem `/ready`.** Nenhuma rota de saúde em lugar nenhum do projeto.

### O que o entrypoint faz além de subir o servidor

Não há `entrypoint.sh` — mas há efeito colateral no import, que é pior porque é invisível
no manifesto:

- `src/main.py:21` → `event_model.Base.metadata.create_all(bind=engine)`.
  **Cria a tabela `events` no Postgres toda vez que o módulo é importado.** Sob
  `gunicorn -w 4`, isso acontece uma vez por worker.
- `src/main.py:32` → `os.makedirs(settings.PROMETHEUS_MULTIPROC_DIR, exist_ok=True)`.
- `src/core/database.py:6` → `create_engine(DATABASE_URL)` no import.

Consequência prática: **se o banco estiver fora, o processo não sobe** — morre no import,
não em runtime. O pod vai para `CrashLoopBackOff`, não para "pronto e devolvendo erro".

### O que a aplicação escreve em disco

| Caminho | Quem escreve |
|---|---|
| `/tmp/prometheus_multiproc` | `os.makedirs` em `src/main.py:32`, valor default de `PROMETHEUS_MULTIPROC_DIR` (`src/core/settings.py:27`); `prometheus_client` grava os arquivos `.db` de métrica multiprocess ali |
| diretório temporário do sistema (`/tmp`) | arquivos de heartbeat dos workers do gunicorn |
| `/app/**/__pycache__` | CPython, se o bytecode não estiver desabilitado |

Nada mais. Não há upload, cache em disco, socket em arquivo nem log em arquivo — o
logging vai todo para stdout (`src/core/logging.py:56`, `StreamHandler(sys.stdout)`).
**Conclusão: um `emptyDir` em `/tmp` resolve, e nada precisa sobreviver ao pod.**

### Credenciais

| Variável | Onde aparece | Tratamento |
|---|---|---|
| `DATABASE_URL` | `src/core/settings.py:10` | carrega usuário **e** senha dentro da URL (`postgresql://usuario:senha@host:5432/base`) → a variável inteira é sensível → `secretKeyRef` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `.env.exemple` | eram só do `docker-compose` (removido). **Não vão para o manifesto** — em prod o banco é infraestrutura, não sobe daqui |
| `SECRET_KEY` do Flask | **embutido no código**, `src/main.py:25`: `app.config['SECRET_KEY'] = 'your-secret-key-here'  # TODO: Move to settings` | **não tem como corrigir pelo manifesto** — não é lido de variável de ambiente. Ver "O que falta", item 1 |

A regra 3.3 é `proibido` e vale para manifesto; o `SECRET_KEY` está fora do alcance dela,
mas está dentro do alcance do estrago: é a chave que assina o cookie de sessão e as
mensagens de `flash`, está pública no repositório e é idêntica em qualquer instalação.

### Não fala com o apiserver

Nenhum import de cliente Kubernetes no projeto; o único cliente de rede é o SQLAlchemy
contra o Postgres. Daí `automountServiceAccountToken: false` (3.4) e ServiceAccount
dedicada **sem nenhum RBAC** (3.5).

### Componente, dono e dimensionamento

- **Componente: `web`.** O mesmo processo Flask serve as páginas HTML (`page_router`) e a
  API JSON em `/api/events` (`api_router`). Não são dois workloads, é um. Chamar de `api`
  esconderia metade do que ele faz.
- **Dono e runbook: não há a informação.** O repositório não tem CODEOWNERS, nem
  `docs/`, nem menção a time. O único autor no `git log` é o autor do projeto original
  (Fabricio Veronez), que não é um time da Metacortex. **Não inventei um nome**: as
  anotações `metacortex.io/owner` e `metacortex.io/runbook` (1.5, recomendado) ficaram
  fora, com pendência registrada.
- **Consumo observado: não há.** Nenhum dado de métrica, nenhum histórico. O `resources`
  é provisório e está declarado como provisório no YAML.
- **SIGTERM:** o gunicorn trata e drena dentro do `graceful_timeout` (30s de fábrica). As
  requisições são HTTP curtas — não há fila nem processamento longo no processo. Os 30s
  do padrão bastam, e ficaram escritos explicitamente (2.6).

---

## 2. As decisões que eu tive que tomar

O padrão não respondia nenhuma destas. Cada uma vem com o que foi descartado e o custo.

### Decisão 1 — Um pacote só, sem banco junto

O projeto depende de Postgres e o `docker-compose.yml` removido subia um `postgres:15-alpine`
ao lado. **Não trouxe o banco para o pacote**, seguindo a decisão conhecida "Banco de dados
no mesmo pacote do workload": a imagem oficial do Postgres colide com a 3.2 em `runAsNonRoot`
e `readOnlyRootFilesystem`, o que exigiria exceção escrita de Segurança, e banco não é
workload sem estado.

**Custo:** o pacote não sobe sozinho. Ele pressupõe um Postgres já provisionado e alcançável
a partir de `helio-prod`, e a URL dele no Secret `encontros-tech-db`.

### Decisão 2 — Probes em `/metrics`, nas duas

A aplicação não expõe endpoint de saúde (fato levantado acima), e este é exatamente o caso
da decisão conhecida "A aplicação não expõe endpoint de saúde".

**Descartado:** apontar para `/` ou `/api/events/`. As duas consultam o Postgres. Com
liveness em rota que toca banco, banco lento derruba a liveness, o container reinicia, e o
reinício não conserta banco — com 2 réplicas a cascata leva o serviço inteiro.

**Descartado também:** `tcpSocket` na 8000. `/metrics` existe (`prometheus_flask_exporter`
registra em `src/main.py:35`) e é mais informativo: prova que o WSGI está respondendo, não
só que a porta abriu.

**Escolhido:** `httpGet /metrics` para readiness e liveness, com períodos diferentes, mais um
`startupProbe` no mesmo caminho com `failureThreshold: 24` (até ~120s) para cobrir o boot, que
inclui uma ida ao banco.

**Custo declarado:** a readiness afirma "o processo subiu", não "consigo atender". Se o
Postgres cair **depois** do boot, o pod continua `Ready`, recebendo tráfego e devolvendo 500.
Isso é atenuado aqui — e só aqui — pelo fato de o processo não conseguir nem iniciar sem
banco (`create_all` no import): a falha aparece no deploy seguinte como `CrashLoopBackOff`.
A correção de verdade é o time dono expor `/health` (com checagem de banco, para readiness) e
`/ready` ou `/livez` (sem banco, para liveness).

### Decisão 3 — Job de schema, mesmo sabendo que ele não elimina a corrida

`create_all` no import de `main.py` + `gunicorn -w 4` + `replicas: 2` + `maxUnavailable: 0`
(3 pods durante o rollout) = até 12 execuções concorrentes de `create_all` no mesmo banco.
`create_all` consulta o catálogo e só então emite `CREATE TABLE`: duas execuções que consultam
na mesma janela emitem juntas, e uma leva `DuplicateTable`.

A decisão conhecida "A migração de banco roda no start da aplicação" manda extrair para um Job
e **sobrescrever `command`/`args`** no container da aplicação. **A segunda metade não se aplica
aqui**, e isso merece ficar escrito: no `fake-shop` a migração estava num `entrypoint.sh`, que
o `command` ignora. Aqui está no corpo de `main.py` — qualquer comando que carregue `main:app`
executa o `create_all`. Não existe comando que suba o servidor e pule aquela linha.

**Descartado:** `initContainer` — mesma corrida, só que mais cedo (é o que a decisão conhecida
já registra).

**Escolhido:** `encontros-tech-schema.yaml`, um Job que importa `models.event` direto (sem
passar por `main.py`, para não subir Flask nem o exporter) e cria o schema uma vez. Com a
tabela já existente, o `create_all` dos pods vira no-op e a corrida some na prática.

**Custo declarado, em dois níveis:**
1. Passa a existir **ordem de aplicação** — Job antes do Deployment — e essa ordem não está
   expressa em nenhum dos dois arquivos, só nos comentários e aqui. Quem aplicar fora de
   ordem reabre a corrida.
2. O Job **reduz** a janela, não a fecha. Num cluster vazio, aplicar só o Deployment ainda
   reproduz o problema. O conserto definitivo é tirar o `create_all` de `main.py` e passar a
   usar um migrador de verdade (Alembic) — pedido para o time dono.

### Decisão 4 — Um `emptyDir` em `/tmp`, não dois

`readOnlyRootFilesystem: true` (3.2) contra uma aplicação que escreve — decisão conhecida
homônima. Os dois escritores encontrados (`/tmp/prometheus_multiproc` e o heartbeat do
gunicorn) caem dentro de `/tmp`, então um único volume cobre os dois; montar
`/tmp/prometheus_multiproc` separado, como no `fake-shop`, seria redundante aqui.
`PROMETHEUS_MULTIPROC_DIR` foi declarado explicitamente no `env` — com o mesmo valor default
do projeto — só para que o caminho gravável fique visível ao lado do `volumeMounts`.
`PYTHONDONTWRITEBYTECODE=1` entrou junto: sem ele o CPython tenta escrever `__pycache__` em
`/app`, falha em silêncio e recompila a cada import.

**Custo declarado:** `emptyDir` morre com o pod. As métricas multiprocess do intervalo em
curso se perdem no restart — aceitável, porque quem guarda série temporal é o Prometheus, não
o pod. Se algum dia a aplicação passar a escrever algo que precise sobreviver, `emptyDir` vira
resposta errada e o caso passa a ser volume persistente.

### Decisão 5 — O Secret **não** está neste pacote

A regra 3.3 é `proibido` e cobre "nem em `env.value`, nem em ConfigMap, nem em comentário".
Escrever um `kind: Secret` com a URL do banco — mesmo em `stringData`, mesmo com placeholder —
coloca o formato da credencial num arquivo versionado e convida alguém a preencher e commitar.

**Escolhido:** o manifesto **referencia** um Secret que precisa existir antes, criado fora do
repositório:

```
Secret: encontros-tech-db   (namespace helio-prod)
Chave:  url
Valor:  postgresql://<usuario>:<senha>@<host>:5432/<base>
```

**Custo declarado:** o pacote tem uma dependência externa não versionada. Se o Secret não
existir, o pod fica em `CreateContainerConfigError` — falha clara, não silenciosa.

**Rotação:** o repositório versiona `encontros_tech/encontros_tech` como usuário e senha em
`.env.exemple` e `src/.env.example`. São valores de exemplo, mas se alguma instalação os tiver
adotado, trocar para `secretKeyRef` não basta: a credencial precisa ser **rotacionada**.

### Decisão 6 — Nome, rótulos e imagem

- **Namespace `helio-prod`** (1.2): cliente `helio` + ambiente `prod`. Não entreguei manifesto
  de Namespace — pela 1.2 quem cria é o Construct.
- **Rótulos:** `name: encontros-tech-web` (o componente), `instance: helio-prod` (a instalação,
  igual ao namespace), `part-of: encontros-tech` (o produto do cliente),
  `managed-by: platform`. O Job usa `name: encontros-tech-schema` — o que, de quebra, garante
  que os pods dele nunca sejam selecionados pelo Service.
- **Os quatro rótulos inteiros no `matchLabels` e no `selector`** (1.4, decisão conhecida
  "Os quatro rótulos no selector, e a imutabilidade"). **Custo declarado:** `matchLabels` é
  imutável num Deployment. No dia em que este workload migrar de `platform` para `argocd`, o
  Deployment precisa ser **recriado**, não atualizado.
- **Imagem `registry.metacortex.io/encontros-tech/web:v1`** (3.7). A imagem que existe hoje é
  pública — `fabricioveronez/encontros-tech-labs:v1`, do `docker-compose.yml` removido — e
  precisa entrar pelo Loom. O caminho `<produto>/<componente>` segue a forma do exemplo do
  padrão (`registry.metacortex.io/nyx/api:2.9.1`); **não achei no projeto nenhuma convenção
  que diga se o registry é namespaceado por cliente ou por produto** — se for por cliente,
  corrija para `helio/…` antes do merge.
- **Tag `v1`:** é a única referência de versão que o artefato tem. Ela passa na 3.1 (não é
  `:latest`), mas é mutável, e o padrão prefere digest. **O digest não é inventável aqui** —
  fixar `@sha256:…` depois que o Loom espelhar.

---

## 3. Saída das ferramentas de verificação

Passo 4 do modo escrita: rodar o modo conferência sobre o próprio resultado.

### `conferir_manifests.py` — passa

```
$ python3 .../scripts/conferir_manifests.py <este diretório>
Resumo: 0 barram, 0 pedem justificativa, 27 conformes.
```

Código de saída **0**. As 11 regras mecânicas foram exercitadas nos 6 objetos:
1.1, 1.2, 1.3, 1.4 (dos dois lados — Deployment e Service), 2.2, 2.3, 2.4, 2.5, 3.4, 3.5, 3.7.
Saída completa em `conferir-manifests.txt`; detalhe por achado em `conferir-manifests.json`.

### `trivy config` — passa, com o falso positivo conhecido

```
$ trivy config <este diretório>
encontros-tech-app.yaml     Tests: 100 (SUCCESSES: 99, FAILURES: 1)
encontros-tech-schema.yaml  Tests:  99 (SUCCESSES: 98, FAILURES: 1)

KSV-0125 (MEDIUM): ... uses an image from an untrusted registry.
```

**O único achado é o `KSV-0125`, e ele é o falso positivo que o SKILL.md documenta:** dispara
contra `registry.metacortex.io`, que é justamente o único registry que o padrão aceita. O
critério do Trivy é o oposto do nosso. A regra 3.7 está conforme pelo script. Nenhum achado
`HIGH` ou `CRITICAL`; as regras 2.1, 3.1, 3.2 e 3.6, que são o território do Trivy, passaram
nos dois arquivos. Saída completa em `trivy-config.txt`.

---

## 4. O que falta — informação que não existe no projeto

Não inventei valor para nenhum destes. Todos precisam de resposta humana antes do merge.

1. **`SECRET_KEY` do Flask está embutida no código** (`src/main.py:25`,
   `'your-secret-key-here'`). Não é lida de ambiente, então **nenhum manifesto conserta isso**.
   É pedido de mudança no código, e a chave precisa ser rotacionada quando virar variável.
   Enquanto não for, cookie de sessão e `flash` são forjáveis por quem lê o repositório.
2. **Dono e runbook** (1.5): não há informação no projeto. As anotações ficaram fora dos
   manifests em vez de receberem um nome inventado.
3. **Dimensionamento** (2.1): não há consumo observado. `requests 100m/256Mi`,
   `limits 500m/512Mi` é chute declarado, calibrado só pela forma do processo (4 workers
   gunicorn, cada um com Flask + SQLAlchemy + pool). O primeiro número a revisar é a memória:
   4 workers em 512Mi é apertado se cada um passar de ~120Mi.
4. **Endereço do Postgres de prod**: não está no projeto (o `.env.exemple` aponta para
   `localhost`). Vai no Secret `encontros-tech-db`.
5. **Convenção de caminho no registry interno**: `<produto>/<componente>` ou
   `<cliente>/<produto>`? Segui a forma do exemplo do padrão; confirmar com quem opera o Loom.
6. **Não existe build**: o `Dockerfile` foi removido no commit `0f5bbad` e a imagem pública
   referenciada usava `FROM python` sem tag (ou seja, `latest`) e sem `USER`. O manifesto
   força `runAsUser: 10001`, o que deve funcionar porque a aplicação só lê de `/app` — mas
   **isso não foi verificado rodando**. Quando o Loom espelhar/reconstruir a imagem, validar
   que ela sobe como não-root antes do primeiro deploy.

**Observação lateral, fora do escopo do padrão:** `src/routers/page_router.py:37` renderiza
`error.html` no tratamento de erro, e esse template **não existe** em `src/templates/`. Ou
seja, quando a listagem falhar (banco fora, por exemplo), a própria página de erro estoura
`TemplateNotFound`. Vale no mesmo pedido ao time dono.
