# CP08 — Testes determinísticos com promptfoo

**Os três arquivos de configuração:**

- [`devops/nota-de-triagem/promptfooconfig.yaml`](./devops/nota-de-triagem/promptfooconfig.yaml)
- [`devops/triagem-de-pods/promptfooconfig.yaml`](./devops/triagem-de-pods/promptfooconfig.yaml)
- [`devops/networkpolicy-sentinel/promptfooconfig.yaml`](./devops/networkpolicy-sentinel/promptfooconfig.yaml)
  (mais [`prompt-geracao.js`](./devops/networkpolicy-sentinel/prompt-geracao.js), que extrai o
  Prompt 1 de `prompt.md` em vez de duplicar o texto — ver curadoria abaixo)

A saída real de cada `promptfoo eval` (pass/fail, latência, custo) e a curadoria completa —
o que passou, o que falhou, e o que foi ajustado no prompt/teste versus o que ficou registrado
como achado de trade-off — estão na seção **"Testes determinísticos (CP08)"** do `README.md`
de cada prompt:

- [`devops/nota-de-triagem/README.md`](./devops/nota-de-triagem/README.md#testes-determinísticos-cp08) — **6/6 passou.**
- [`devops/triagem-de-pods/README.md`](./devops/triagem-de-pods/README.md#testes-determinísticos-cp08) — conteúdo 6/6 correto; **0/6 no teto de latência/custo**.
- [`devops/networkpolicy-sentinel/README.md`](./devops/networkpolicy-sentinel/README.md#testes-determinísticos-cp08) — conteúdo 2/2 correto; **0/2 no teto de latência**.

## Resumo executivo

Dois provedores em todos os três configs: **Anthropic** (`claude-haiku-4-5-20251001`) e
**Google** (`gemini-3.5-flash`, com `thinkingConfig.thinkingBudget: 0` — ver abaixo por quê).

| Prompt | Conteúdo | Latência (≤5s) | Custo (≤US$0,01) |
|---|---|---|---|
| nota-de-triagem | 6/6 ✅ | 6/6 ✅ | 6/6 ✅ |
| triagem-de-pods | 6/6 ✅ | 0/6 ❌ | 5/6 ✅ (1 estourou) |
| networkpolicy-sentinel | 2/2 ✅ | 0/2 ❌ | 2/2 ✅ |

**Nenhuma reprovação de conteúdo em nenhum dos três prompts** — todo assert de `contains`,
`regex`, `contains-any`, `not-contains` e `javascript` passou em toda execução registrada. As
únicas reprovações são de latência (e uma de custo), e cada uma tem uma explicação verificável
no README do prompt correspondente — não são falhas do prompt, são o teto de 5s/US$0,01 batendo
contra o comprimento de saída inerente à tarefa.

## Curadoria — decisões que atravessam os três configs

1. **`thinkingConfig.thinkingBudget: 0` no provider do Gemini, não no prompt.** A primeira
   rodada de `nota-de-triagem` reprovava os 3 casos do Gemini só em latência/custo (7–12s,
   até US$0,03) apesar do conteúdo estar certo — o modelo gastava tokens de "thinking" numa
   tarefa de formatação fixa, sem ganho de qualidade. Desligar o thinking no `providers.config`
   resolveu para `nota-de-triagem` (6/6) e ajudou (mas não resolveu sozinho) `triagem-de-pods`
   e `networkpolicy-sentinel`, cuja saída é intrinsecamente mais longa.
2. **`triagem-de-pods` e `networkpolicy-sentinel` reprovam o teto de latência mesmo com
   conteúdo perfeito — e isso não foi "consertado" encolhendo o prompt.** Encurtar a saída de
   `triagem-de-pods` (relatório multi-seção) ou remover os passos de CoT de
   `networkpolicy-sentinel` (o mesmo raciocínio que o CP06 provou ser necessário para não
   gerar um `namespaceSelector` faltando) trocaria qualidade por métrica de teste. A decisão
   registrada é: o teto de 5s/US$0,01, fixado igual para os três, só é operacionalmente
   realista para prompts de saída curta e determinística (nota de 5 campos, YAML de duas
   políticas pequenas) — não para um relatório de triagem completo nem para geração de um
   artefato de segurança que depende de raciocínio explícito. Isso é exatamente o trade-off
   latência/custo × qualidade que o checkpoint pede para pesar, não um bug a esconder.
3. **Um ajuste de teste, não de prompt:** o assert `contains: "Problemáticos: 0"` de
   `triagem-de-pods` reprovava a Entrada 3 (cluster saudável) porque a saída real usa markdown
   (`**Problemáticos:** 0`) — o `**` quebra a correspondência literal. Trocado para
   `regex: "Problemáticos:\*{0,2}\s*0"`. O prompt estava certo; o teste que assumia formato
   sem negrito é que precisava ser corrigido — engenharia reversa da saída real, não suposição.
4. **`prompt-geracao.js` em vez de duplicar texto.** `networkpolicy-sentinel/prompt.md` guarda
   dois prompts encadeados (geração + verificação, CP06). O CP08 só pede asserts sobre a
   NetworkPolicy *gerada*, então o `promptfooconfig.yaml` precisa rodar só o Prompt 1. Em vez
   de copiar esse texto para um arquivo separado (criando duas fontes de verdade que
   divergiriam na próxima edição), o "prompt" do config é uma função JS que lê `prompt.md` em
   tempo de execução e extrai o bloco certo. `prompt.md` continua sendo a única fonte do texto.
5. **`google:gemini-3.5-flash` teve um erro transitório 503 ("high demand")** numa das
   execuções de `triagem-de-pods` — não é falha do config nem do prompt, é sobrecarga momentânea
   da API do provider durante o teste; registrado como tal, não mascarado como pass.

## Uma observação sobre a chave usada

A execução usou uma chave de API da Anthropic temporária, fornecida pelo Tales diretamente no
chat para este checkpoint. Ela foi salva só em `.env` local (fora do controle de versão —
`.gitignore` do playbook cobre `.env` e `**/.env`) e nunca aparece em nenhum arquivo commitado.
