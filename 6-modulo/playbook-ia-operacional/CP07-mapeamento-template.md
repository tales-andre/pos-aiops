# CP07 — Nota de mapeamento no template `prompt-registry`

**Repositório:** [github.com/tales-andre/pos-aiops](https://github.com/tales-andre/pos-aiops), pasta
[`6-modulo/playbook-ia-operacional/`](https://github.com/tales-andre/pos-aiops/tree/master/6-modulo/playbook-ia-operacional)
(reaproveita um repositório de pós já existente em vez de um repo novo isolado — ver "Desvios" abaixo).

**Prompt de exemplo completo** (`prompt.md` com `{{placeholders}}` + `README.md` com frontmatter):
[`devops/triagem-de-pods/`](https://github.com/tales-andre/pos-aiops/tree/master/6-modulo/playbook-ia-operacional/devops/triagem-de-pods)

## Como o playbook foi mapeado nas convenções do template

O ponto de partida foi o conteúdo do template [`fabricioveronez/prompt-registry`](https://github.com/fabricioveronez/prompt-registry)
copiado como está — mesmas 5 categorias vazias (`devops/`, `desenvolvimento/`, `produtividade/`,
`financas/`, `criacao-conteudo/`), mesmo `README.md` raiz, mesmo `CLAUDE.md` com as regras de
estrutura e frontmatter, mesmo slash command `/catalogar`. Nenhuma convenção foi reinventada.

**Categoria:** todos os seis prompts dos Checkpoints 01–06 caem em `devops/` — o cenário fictício
(Aegis, plataforma de observabilidade) é inteiramente SRE/DevOps, então nenhuma categoria nova foi
criada. Se o playbook crescesse para outros domínios (ex.: um prompt de comunicação com cliente
sobre o incidente), ele iria para `produtividade/` ou uma categoria nova — não dentro de `devops/`.

**Prompt = pasta nomeada pelo resultado:** `triagem-de-pods`, `nota-de-triagem`, `causa-raiz`,
`backpressure-relay`, `migracao-forge`, `networkpolicy-sentinel` — nenhuma pasta leva o nome da
técnica (não existe `chain-of-thought/` ou `cove/`). A técnica fica registrada na seção "Curadoria"
do `README.md`, não no nome do artefato.

**`prompt.md` + `README.md` com frontmatter idêntico:** os seis prompts seguem a regra à risca —
mesmo bloco YAML no topo dos dois arquivos, com `nome`, `descricao`, `versao` (todos nasceram em
`1.0.0`; `networkpolicy-sentinel` foi para `2.0.0` depois de uma correção de curadoria), `tags` e
`inputs`. Cada `{{placeholder}}` do corpo do prompt tem uma entrada correspondente em `inputs` — é
literalmente a mesma lista, só que documentada.

**Cadeias e loops como múltiplos prompts numa pasta só:** dois casos fogem do "um prompt por
arquivo" mais simples e o template não prescreve como resolver isso, então a decisão foi: continuam
sendo **uma pasta de resultado**, com múltiplos blocos de prompt dentro do mesmo `prompt.md`,
encadeados por `{{OUTPUT_ELO_N}}` ou `{{YAML_GERADO}}` no `inputs`.
- `migracao-forge/` — cadeia de 3 elos (diagnóstico → estratégia → plano por fase).
- `networkpolicy-sentinel/` — par geração + verificação (Chain-of-Verification), com a saída de um
  alimentando o outro.

**Commits semânticos com escopo na categoria:** todo commit de prompt seguiu
`feat(devops): adiciona prompt de <resultado> (CPxx)`, e a correção do CP06 usou
`fix(devops): corrige atribuição de técnica...`. Os índices (`README.md` raiz e `README.md` de
`devops/`) foram atualizados no mesmo commit que introduziu o prompt — nunca depois, como o
`CLAUDE.md` do template exige na seção "Manutenção da documentação".

## Desvios do template e por quê

1. **Repositório aninhado, não um repo novo.** O playbook vive em
   `6-modulo/playbook-ia-operacional/` dentro do repositório `pos-aiops` (que já reúne outros
   módulos da pós), em vez de ser um fork isolado do `prompt-registry`. Decisão para manter tudo da
   pós num único lugar em vez de espalhar repositórios; a raiz do playbook em si segue 100% a
   estrutura do template a partir desse ponto.
2. **Subpasta `execucoes/` em cada prompt** (documentada em `CLAUDE.md`, seção "Desvio consciente
   do template"). O template não prevê isso — mas o desafio pede execução real como evidência, não
   só o texto do prompt. `README.md` resume o resultado; `execucoes/` guarda o input e o output
   reais, sem edição, como prova de que o prompt foi de fato rodado (e não só escrito).

Nenhum outro campo, regra ou convenção do template foi alterado.
