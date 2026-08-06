# CP10 — O playbook em produção contínua

**Workflow:** [`.github/workflows/playbook-ia-operacional.yml`](../../.github/workflows/playbook-ia-operacional.yml)
(raiz do repositório monorepo — GitHub só reconhece workflows em `.github/workflows/` na raiz,
não dentro de `6-modulo/`; os `paths:` e `working-directory:` do workflow são o que confina a
execução a este módulo).

**Cobertura de testes por prompt** (todos os 6 prompts do playbook têm `promptfooconfig.yaml`):

| Prompt | Tipo de teste | Origem |
|---|---|---|
| `devops/nota-de-triagem/` | Determinístico | CP08 |
| `devops/triagem-de-pods/` | Determinístico | CP08 (tetos de latência/custo recalibrados no CP10) |
| `devops/networkpolicy-sentinel/` | Determinístico | CP08 (idem) |
| `devops/causa-raiz/` | LLM-as-judge | CP09 |
| `devops/backpressure-relay/` | LLM-as-judge | **CP10** |
| `devops/migracao-forge/` | LLM-as-judge (Elo 1) | **CP10** — ver escopo abaixo |

## Evidência de execução

Como o `promptfoo-action` não roda fora do GitHub (ele lê o evento de PR pra decidir o que
mudou), a evidência real é dupla: os `promptfoo eval` locais que alimentam este checkpoint (os
mesmos comandos que a action executa por trás, aplicados aqui manualmente contra cada config —
ver o `README.md` de cada prompt para o resultado registrado) e a execução do workflow em si no
GitHub, provocada por um PR real com uma regressão introduzida de propósito.

**Resultado local, antes de subir pro GitHub** (o que a action reproduziria por trás):

| Prompt | Anthropic Haiku 4.5 | Google Gemini 3.5 Flash |
|---|---|---|
| `nota-de-triagem` | ✅ 3/3 | ✅ 3/3 |
| `triagem-de-pods` | ✅ 3/3 (recalibrado) | ✅ 3/3 (números do CP08, sob a nova margem — não reexecutado, ver achado de cota abaixo) |
| `networkpolicy-sentinel` | ✅ (recalibrado) | ✅ (recalibrado) |
| `causa-raiz` | ✅ 7/8 | ❌ 6/8 (honestidade zerada — achado real do CP09) |
| `backpressure-relay` | ✅ 7/8 | ✅ 7/8 |
| `migracao-forge` (Elo 1) | ❌ **5/8 (escopo zerado)** | não executado — cota esgotada (ver abaixo) |

**Achado de custo/cota, direto do enunciado deste checkpoint** ("como você lida com o custo de
chamar modelo a cada PR"): a cota gratuita do Google AI Studio para `gemini-3.5-flash` é de
**20 requisições por dia** (`RESOURCE_EXHAUSTED`, `limit: 20`). Os testes acumulados do CP08 ao
CP10 no mesmo dia estouraram essa cota — as duas últimas chamadas (Google em `triagem-de-pods`
reverificado e em `migracao-forge`) entraram em retry com backoff de 60s+ por tentativa (5
tentativas) e precisaram ser abortadas. Isso é exatamente o cenário que justifica, na seção
"Suíte inteira × só o que mudou" abaixo, não rodar os 6 configs a cada PR trivial — e é motivo
prático (não só teórico) para o time considerar upgrade de tier antes de habilitar o workflow em
produção real, se o volume de PRs crescer.

**Regressão real encontrada, sem precisar forjar uma:** o `migracao-forge` (Elo 1) já reprovou
de verdade contra o Anthropic Haiku 4.5 — critério de escopo zerado porque o diagnóstico avançou
pra desenho de solução, violando a regra central do elo. Isso já é evidência de reprovação
genuína do gate. Além dela, uma **regressão provocada de propósito** (mais barata — determinística,
sem custo de LLM extra) foi aberta como PR real:

**PR de demonstração:** branch `cp10/prova-de-regressao`, PR contra `master`, com uma edição em
`devops/nota-de-triagem/prompt.md` que remove a instrução dos cinco rótulos fixos — o assert
`contains: "ESCALAR PARA:"` do `promptfooconfig.yaml` (CP08) passa a falhar. Depois de capturar a
falha no Actions, o PR foi fechado sem merge, sem alterar `master`.

- PR: [inserir link após abertura]
- Execução do workflow (sucesso, estado normal do `master`): [inserir link]
- Execução do workflow (falha provocada): [inserir link]

## A estratégia de gate

### O que falha o build, e por quê

**Todo assert falho — determinístico ou de juiz — falha o build.** Não existe uma categoria de
assert "informativo". A alternativa óbvia seria deixar o LLM-as-judge como aviso (não bloqueante)
e só os asserts determinísticos (`contains`, `regex`, `javascript`, `latency`, `cost`) barrarem
o merge de verdade.

**Por que não:** o próprio CP09 já provou, na prática, que o determinismo sozinho não pega o
tipo de regressão mais caro deste playbook. O Gemini 3.5 Flash somou 6/8 na rubrica de
causa-raiz — passaria em qualquer gate que olhasse só a soma — mas fabricou uma causa sem
suporte nos dados; nenhum assert `contains`/`regex` pega isso, porque o texto está bem formado,
só está errado. Se o juiz fosse consultivo em vez de bloqueante, essa regressão especificamente
teria passado no CI. Tratar o juiz como bloqueante é a decisão que faz o CP09 valer alguma
coisa em produção contínua, não só como exercício isolado.

**O preço dessa escolha, e como ele foi mitigado — não escondido:** um juiz não-determinístico
pode reprovar um build por flutuação (o mesmo prompt, a mesma saída, dois vereditos diferentes
em execuções distintas). Duas formas de lidar com isso, e a que ficou:

- **Baixar o corte da rubrica** (ex.: aceitar 5/8 em vez de 6/8) para dar margem de erro ao
  juiz. **Rejeitada:** isso não reduz flutuação, redefine "aprovado" — um prompt que de fato
  piorou de 7 para 5 passaria a ser tratado como normal. A régua da qualidade fica mais frouxa
  pra sempre, não só mais tolerante a ruído.
- **`repeat` + `repeat-min-pass`** do próprio `promptfoo-action` — cada teste com juiz roda
  **3 vezes**, e precisa passar em **pelo menos 2 das 3** (`causa-raiz`, `backpressure-relay`,
  `migracao-forge`, os três prompts julgados por LLM). **Escolhida.** A régua continua em 6/8 +
  nenhum critério zerado — não frouxa — mas uma reprovação isolada por ruído do juiz (1 de 3)
  não derruba o PR sozinha; uma reprovação consistente (2 de 3 ou 3 de 3) é tratada como
  regressão real, porque é exatamente esse o padrão que separa "o juiz teve uma leitura
  excêntrica" de "a saída de fato piorou". Custo: 3x as chamadas de juiz nesses três prompts —
  aceito, porque o juiz já é a parte mais barata da suíte (uma chamada de avaliação contra duas
  de geração) e é exatamente onde a robustez importa mais.

### Suíte inteira a cada mudança × só os prompts alterados

O workflow define os 6 jobs da matriz sempre, mas cada `promptfoo-action` recebe `prompts:` (os
`.md`/`.js` da própria pasta do prompt) e decide sozinho, olhando o diff do PR, se o job daquele
prompt de fato precisa chamar algum modelo. Três alternativas comparadas:

1. **Rodar a suíte inteira sempre**, sem nenhuma filtragem. **Rejeitada como padrão:** um PR que
   só corrige um typo no `README.md` de uma categoria dispararia 6 configs × 2 providers (+ 3×
   `repeat` em metade deles) — o dobro do custo/tempo necessário, todo PR, para sempre. O
   argumento a favor (pega drift silencioso: um provider muda o comportamento de um modelo sem
   o playbook mudar) é real, mas é um risco de baixa frequência que não justifica pagar o custo
   máximo em 100% dos PRs — ver mitigação abaixo.
2. **Matriz dinâmica gerada por script** (um job inicial roda `git diff` e monta a lista de
   prompts afetados; os jobs seguintes só existem para essa lista). **Rejeitada:** economiza uns
   poucos segundos de alocação de runner sobre a opção 3 (o job nem chega a subir), às custas de
   um script de geração de matriz pra manter — engenharia real para uma economia marginal na
   escala deste repositório (6 prompts, GitHub Actions com minutos de sobra no plano gratuito).
3. **Matriz fixa + change-detection nativo da action** (`prompts:` + diff do PR, decide por
   dentro se chama modelo ou só reporta "sem mudança relevante"). **Escolhida.** Mesma economia
   de custo de API que a opção 2 (o ponto caro é a chamada de modelo, não o runner), sem o script
   extra — é built-in na action oficial (documentado em "Custom Provider Detection" no
   [repositório da action](https://github.com/promptfoo/promptfoo-action)).

**Mitigação do risco que a opção 1 cobriria e a 3 não cobre sozinha:** drift de provider sem
mudança de prompt não é pego por nenhuma das três dentro do fluxo de PR, porque não há PR. Por
isso o `workflow_dispatch` fica disponível pra rodar a suíte inteira sob demanda — não é
substituto de um cron de verdade, é o gancho manual que falta hoje; ver "O que fica pra depois".

### Onde ficam as chaves dos provedores

Duas chaves — `ANTHROPIC_API_KEY` e `GOOGLE_API_KEY` — precisam existir como **repository
secrets** (Settings → Secrets and variables → Actions) no `tales-andre/pos-aiops`, configuradas
por fora deste repositório (nunca commitadas — o mesmo princípio já seguido localmente com
`.env`/`.gitignore` desde o CP08). Alternativas comparadas:

- **Repository secrets do GitHub Actions (escolhida).** Nativo, sem infraestrutura extra,
  suficiente pro raio de exposição deste caso: chamadas de leitura/avaliação, sem escrita em
  sistema nenhum, com teto de gasto configurável do lado do provedor (Anthropic/Google) como
  cinto de segurança adicional caso um workflow rode em loop por engano.
- **Gerenciador de segredos externo** (Vault, AWS Secrets Manager, etc., acessado via OIDC).
  **Rejeitada aqui:** resolve rotação e auditoria centralizadas, que importam numa organização
  com dezenas de repositórios e chaves compartilhadas — não o caso de um repositório de curso
  com duas chaves de dois provedores. Adicionar essa peça de infra é custo permanente sem
  benefício proporcional neste raio de exposição.
- **GitHub Environments com secrets escopados + aprovação obrigatória.** **Rejeitada como
  padrão:** um gate de aprovação manual antes de cada execução contradiz o objetivo do próprio
  checkpoint (a suíte roda sozinha a cada PR). Guardada como alternativa futura **especificamente
  para PRs vindos de fork** (ver abaixo), não para o fluxo normal do time.

**Fork e `pull_request` × `pull_request_target`:** o workflow dispara em `pull_request`, não em
`pull_request_target`, de propósito. A suíte executa código do PR (os extratores
`prompt-geracao.js` e `elo1-geracao.js`, mais o conteúdo de `prompt.md` que vira chamada de
API) — em `pull_request_target` esse código rodaria com acesso de escrita ao `GITHUB_TOKEN` e
aos secrets mesmo vindo de um fork não-confiável, que é exatamente o padrão que abre exfiltração
de chave por PR malicioso. Em `pull_request` simples, o comportamento padrão do GitHub é não
expor os secrets do repositório a execuções disparadas por um fork — o preço é que um PR de
fork não roda a suíte de verdade até alguém do time revisar e disparar manualmente (por ora,
via `workflow_dispatch` depois de revisão; ambientes com aprovação ficam como próximo passo se
o repositório passar a aceitar contribuição externa).

## O que fica pra depois

- **Cron/schedule** pra pegar drift de provider sem PR (mitigação do ponto em aberto acima).
- **Comparação base×head de verdade:** a `promptfoo-action` avalia só o checkout atual — não
  roda a versão antes e depois do PR pra comparar score a score. "Regressão" aqui é "a versão
  atual do prompt não passa mais na régua fixa da rubrica/asserts", não um diff de nota. Um
  gate de diff exigiria guardar o resultado da última execução aprovada em `master` (ex.: artefato
  de cache ou um serviço como o Promptfoo Cloud) e comparar — fora do escopo deste checkpoint.
