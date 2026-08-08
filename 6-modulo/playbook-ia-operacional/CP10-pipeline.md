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

Duas fontes: os `promptfoo eval` locais que alimentam este checkpoint (mesmos comandos que a
action roda por trás — ver o `README.md` de cada prompt) e **duas execuções reais do workflow no
GitHub**, capturadas em produção:

- **Execução manual** (`workflow_dispatch`) contra o `master` como está hoje:
  [run #31099021613](https://github.com/tales-andre/pos-aiops/actions/runs/31099021613)
- **PR de regressão provocada**, branch `cp10/prova-de-regressao`:
  [PR #1](https://github.com/tales-andre/pos-aiops/pull/1) ·
  [run #31099457895](https://github.com/tales-andre/pos-aiops/actions/runs/31099457895) ·
  [comentário da action no PR](https://github.com/tales-andre/pos-aiops/pull/1#issuecomment-5204634581)
  ("0 Success / 3 Failure")

**Resultado real, os dois runs:**

| Prompt | Run manual (`master`) | Run do PR (regressão) |
|---|---|---|
| `nota-de-triagem` | ✅ success | ❌ **failure — Anthropic `[FAIL]` nos 3 casos** (a regressão real: assert `contains: "ESCALAR PARA:"` quebrado); Google `[ERROR]` por rate limit, separado |
| `causa-raiz` | ✅ success | pulado — nada mudou nessa pasta no PR |
| `triagem-de-pods` | ❌ failure — só `[ERROR]` de rate limit do Google, 0 falha de conteúdo | pulado |
| `networkpolicy-sentinel` | ❌ failure — idem, só rate limit | pulado |
| `backpressure-relay` | ❌ failure — idem, só rate limit | pulado |
| `migracao-forge` (Elo 1) | ❌ failure — Anthropic `[FAIL]` real (mesmo achado de escopo do teste local, 5/8) + Google rate limit | pulado |

**Duas coisas que a evidência real prova ao mesmo tempo:**

1. **O gate funciona:** o PR com a regressão provocada falhou pelo motivo certo — o log da action
   mostra `[FAIL]` na coluna do Anthropic para os três alertas, não erro de infraestrutura, e o
   comentário automático no PR reporta "0 Success / 3 Failure". Os outros 5 jobs nem chamaram
   modelo nenhum (pularam por change-detection), confirmando a estratégia "só o que mudou" na
   prática, não só na teoria.
2. **Achado de custo/cota, direto do enunciado deste checkpoint** ("como você lida com o custo de
   chamar modelo a cada PR"): a cota gratuita do Google AI Studio para `gemini-3.5-flash` é de
   **20 requisições por dia** (`RESOURCE_EXHAUSTED`, `limit: 20`). Os testes acumulados do CP08 ao
   CP10 no mesmo dia estouraram essa cota — toda chamada Google subsequente (local e no GitHub)
   passou a errar com `RateLimitExhaustedError` depois de 4 tentativas com backoff de 60s+. Isso
   derrubou 3 jobs do run manual só por infraestrutura, com zero relação com a qualidade dos
   prompts (confirmado lendo o log de cada um: nenhum `[FAIL]` de conteúdo, só `[ERROR]` de rate
   limit). É exatamente o cenário que justifica, na seção "Suíte inteira × só o que mudou" abaixo,
   não rodar os 6 configs a cada PR trivial — e motivo prático (não só teórico) para o time
   considerar upgrade de tier antes de depender deste pipeline em produção real, se o volume de
   PRs crescer. Fica registrado como limitação operacional conhecida, não escondido atrás de um
   `force-run` ou de rodar de novo até "dar certo".

**Regressão real encontrada, sem precisar só da provocada:** o `migracao-forge` (Elo 1) reprovou
de verdade contra o Anthropic Haiku 4.5 — critério de escopo zerado porque o diagnóstico avançou
pra desenho de solução, violando a regra central do elo. Isso já é evidência de reprovação
genuína do gate. Além dela, uma **regressão provocada de propósito** (mais barata — determinística,
sem custo de LLM extra) foi aberta como PR real:

**PR de demonstração:** branch `cp10/prova-de-regressao`, PR contra `master`, com uma edição em
`devops/nota-de-triagem/prompt.md` que remove o campo `ESCALAR PARA` (e os três exemplares que o
usavam) — o assert `contains: "ESCALAR PARA:"` do `promptfooconfig.yaml` (CP08) passa a falhar.
Depois de capturar a falha no Actions (links acima), o PR foi fechado sem merge, sem alterar
`master`.

## Revisão pós-lançamento: por que só Anthropic na suíte de CI

A evidência acima (3 jobs derrubados só por `RateLimitExhaustedError` do Google, em duas
execuções reais) não ficou como nota de rodapé — mudou o desenho. Depois de capturar essa
evidência, os 6 `promptfooconfig.yaml` e o workflow foram atualizados para rodar **só
`anthropic:messages:claude-haiku-4-5-20251001`**. O Google saiu da suíte de CI inteira; o
workflow não passa mais `GOOGLE_API_KEY`.

**Isso é uma reversão explícita do pedido original do CP08** ("adicione um segundo provider de
outro fornecedor" no `promptfooconfig.yaml`). Registrado aqui sem disfarce, com a justificativa:

- **A regra de ≥2 provedores do desafio inteiro já está satisfeita fora da suíte de CI.** Ela
  foi estabelecida lá no início do capstone sobre a *criação/execução* de cada prompt do
  playbook — e todo prompt do CP01 ao CP06 já tem execução real registrada em pelo menos dois
  fornecedores (Anthropic e Google, ver `README.md` de cada prompt). O que muda agora é só qual
  provider o **gate de CI** usa pra gerar a saída que vai ser testada a cada PR — uma decisão de
  engenharia de pipeline, não uma reinterpretação da regra do desafio.
- **O que se perde:** o CP09 mostrou um caso real em que só o Gemini (não o Haiku) fabricou uma
  causa sem suporte — com um provider só na suíte, esse tipo de regressão *específica de um
  fornecedor* deixa de ter chance de aparecer no CI. É uma perda real de cobertura, não
  cosmética.
- **O que se mantém:** o gate continua rodando geração real + juiz real a cada PR, e continua
  pegando regressão de conteúdo de verdade — confirmado depois da mudança: `migracao-forge`
  reprova de novo, com o Haiku sozinho, pelo mesmo motivo de antes (escopo do Elo 1 violado,
  critério zerado, reason do juiz idêntico em conteúdo). A suíte não virou um carimbo de
  aprovação automática só porque perdeu um provider.

**Alternativas comparadas antes de cortar o Google:**

1. **Manter os dois e tolerar a instabilidade** (deixar o job de rate limit falhar de vez em
   quando, contando com reruns manuais). **Rejeitada:** falha de infraestrutura indistinguível de
   regressão real na tela do PR treina o time a ignorar builds vermelhos — o pior resultado
   possível pra um gate, pior que ter só 1 provider confiável.
2. **Segunda chave do Google** (outro projeto/conta, para dobrar a cota de 20 para 40 req/dia,
   alternando entre as duas). **Rejeitada por decisão do Tales:** resolve por mais tempo, não
   resolve de vez — a suíte cresce, o número de PRs cresce, e o teto dobrado volta a ser
   insuficiente mais cedo ou mais tarde; também significa gerenciar mais uma credencial só para
   adiar o mesmo problema.
3. **Um segundo modelo Anthropic** (cogitado: `claude-fable-5`) **em vez de um segundo
   fornecedor**, mantendo 2 providers na suíte. **Rejeitada:** testado via API antes de adotar —
   `claude-fable-5` não aceita `thinking.type.disabled` (erro: *"Thinking defaults to adaptive
   mode when not specified"*), então ele reproduziria exatamente o problema de latência/custo
   que o Gemini tinha antes de eu desligar o thinking dele no CP08 — só que trocando o fornecedor
   instável (Google, por cota) pelo modelo caro (Fable 5, por thinking obrigatório). Não é uma
   melhora, é o mesmo tipo de problema com fornecedor diferente.
4. **Só Anthropic Haiku 4.5** (escolhida). Único modelo, nesta conta, comprovadamente rápido,
   barato e sem thinking obrigatório — os três atributos que a suíte de CI precisa pra rodar em
   todo PR sem virar gargalo de cota nem de custo. Formalizado com o Tales antes de aplicar, pela
   troca explícita de cobertura cross-provider por confiabilidade de pipeline.

`GOOGLE_API_KEY` continua cadastrada como secret do repositório (não removida — pode voltar a
ser útil se o Google entrar de novo em algum uso pontual, ex.: `workflow_dispatch` manual contra
um tier pago), só não é mais lida pelo workflow padrão.

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
  aceito porque é exatamente onde a robustez importa mais.

### Suíte inteira a cada mudança × só os prompts alterados

O workflow define os 6 jobs da matriz sempre, mas cada `promptfoo-action` recebe `prompts:` (os
`.md`/`.js` da própria pasta do prompt) e decide sozinho, olhando o diff do PR, se o job daquele
prompt de fato precisa chamar algum modelo. Três alternativas comparadas:

1. **Rodar a suíte inteira sempre**, sem nenhuma filtragem. **Rejeitada como padrão:** um PR que
   só corrige um typo no `README.md` de uma categoria dispararia os 6 configs (+ 3× `repeat` em
   metade deles) — custo/tempo desnecessário, todo PR, para sempre. O argumento a favor (pega
   drift silencioso: o provider muda o comportamento de um modelo sem o playbook mudar) é real,
   mas é um risco de baixa frequência que não justifica pagar o custo máximo em 100% dos PRs —
   ver mitigação abaixo.
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

`ANTHROPIC_API_KEY` precisa existir como **repository secret** (Settings → Secrets and variables
→ Actions) no `tales-andre/pos-aiops`, configurada por fora deste repositório (nunca commitada —
o mesmo princípio já seguido localmente com `.env`/`.gitignore` desde o CP08).
`GOOGLE_API_KEY` também está cadastrada lá, mas — depois da revisão pós-lançamento acima — o
workflow não a lê mais; ficou como secret ocioso, não removido por precaução (ver seção
anterior). Alternativas comparadas para o mecanismo de guardar a chave (independem de qual/quantos
provedores a suíte usa):

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
