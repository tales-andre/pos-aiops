---
nome: Hardening de NetworkPolicy — Sentinel
descricao: "Cadeia de dois prompts (geração + verificação) que substitui um manifesto de Kubernetes barrado por permissivo demais por um conjunto de NetworkPolicy least-privilege, refinado por um loop de Chain-of-Verification até zero achados críticos."
versao: 2.0.0
tags: [devops, kubernetes, networkpolicy, security, zero-trust, sre, chain-of-verification]
inputs:
  - nome: MANIFESTO_PERMISSIVO
    descricao: "Manifesto de NetworkPolicy barrado na revisão de segurança por ser permissivo demais. Entrada do prompt de geração."
  - nome: REGRAS_PADRAO
    descricao: "Conjunto de regras de padrão (least privilege) que a nova versão precisa satisfazer. Usado na geração e na verificação."
  - nome: MAPA_SERVICOS
    descricao: "Mapa de identificação dos serviços do cluster — namespace, label e porta de cada contraparte. Usado na geração e na verificação."
  - nome: YAML_GERADO
    descricao: "Encadeamento: o YAML produzido pelo prompt de geração é o parâmetro de entrada do prompt de verificação."
---

# Hardening de NetworkPolicy — Sentinel

> **Nota de versão (v2.0.0):** a v1.0.0 deste prompt rotulava o loop de verificação como
> "Self-Consistency". Está incorreto — ver seção "Correção de atribuição" abaixo. A técnica correta é
> Chain-of-Verification (CoVe), e o prompt de verificação, que antes existia só implicitamente, agora
> é um segundo elo explícito, parametrizável e reusável.

## Objetivo

Transformar um manifesto de `NetworkPolicy` barrado por permissivo demais em um par de
políticas least-privilege — uma default-deny explícita e uma allow específica por fluxo
legítimo — sem que o modelo invente label, namespace ou porta fora do que o mapa de
serviços declara. A cadeia tem dois prompts: um de **geração**, com um checklist de
raciocínio interno (Chain-of-Thought) que mapeia cada regra do padrão à contraparte exata
antes de gerar o YAML; e um de **verificação**, que roda isolado do raciocínio da geração
— vendo só o YAML candidato — e aplica oito perguntas fixas de um revisor de segurança
adversarial. O ciclo geração → verificação se repete até um veredito `APROVADO` (Chain-of-
Verification, com critério de parada explícito).

## Quando usar

- Sempre que uma `NetworkPolicy` for barrada em revisão de segurança por padrões que
  disfarçam allow-all (`podSelector: {}`, `- {}` em ingress/egress, ausência de
  `namespaceSelector` em regra cross-namespace).
- Hardening de zero-trust entre microsserviços quando já existe um mapa de serviços
  confiável (namespace, label, porta) para basear os seletores.
- Não usar quando o mapa de serviços não tiver as portas necessárias e a política
  precisar ir para produção sem revisão humana das pendências — o prompt propositalmente
  não inventa porta ausente e devolve isso como pergunta em aberto.

## Parâmetros

| Parâmetro | Descrição | Usado em |
|-----------|-----------|----------|
| `{{MANIFESTO_PERMISSIVO}}` | Manifesto barrado na revisão por ser permissivo demais. | Geração |
| `{{REGRAS_PADRAO}}` | Regras de padrão (least privilege) que a nova versão precisa satisfazer. | Geração e verificação |
| `{{MAPA_SERVICOS}}` | Mapa de identificação dos serviços — namespace, label e porta de cada contraparte. | Geração e verificação |
| `{{YAML_GERADO}}` | O YAML produzido pela geração (ou pela rodada anterior de refino). | Verificação |

## Exemplo de uso

**Geração:** preencha os três parâmetros com o manifesto barrado, as regras de padrão do
time de segurança e o mapa de serviços do cluster. A saída são exatamente dois documentos
YAML (default-deny + allow), sem texto fora do bloco de código, terminando em um
comentário `# PERGUNTAS EM ABERTO PARA O REVISOR:`.

**Verificação:** preencha `{{YAML_GERADO}}` com a saída da geração (ou do refino anterior)
mais os mesmos `{{REGRAS_PADRAO}}` e `{{MAPA_SERVICOS}}`. A saída é uma tabela de 8
perguntas com veredito, severidade e evidência, seguida de `VEREDITO DA RODADA: APROVADO`
ou `REPROVADO`. Se `REPROVADO`, volte ao prompt de geração com os achados para produzir a
próxima versão, e repita a verificação — até `APROVADO` ou até 3 rodadas (escalar para
humano na terceira sem aprovação).

Execução completa (v1 → verificação 1 → v2 → verificação 2) sobre o manifesto do Sentinel
em [`execucoes/hardening-sentinel-prod.md`](./execucoes/hardening-sentinel-prod.md).

## Execução

Rodado sobre o manifesto do Sentinel (`sentinel-prod`), com **Claude Opus 5**
(`claude-opus-5`, via claude.ai, temperatura 0.1 — reprodutibilidade priorizada por ser
manifesto de segurança). Duas rodadas do loop:

- **v1** produziu `default-deny-all` + `allow-sentinel` com seletores sintaticamente
  corretos, mas a verificação (8 perguntas, respondidas isoladas do raciocínio da geração)
  encontrou 1 achado **CRÍTICO**: os `podSelector` de `from`/`to` não tinham
  `namespaceSelector`, e como todas as seis contrapartes (Relay, API gateway, Forge,
  Cerebro, DNS) vivem fora de `sentinel-prod`, a política — como escrita — não casava com
  pod nenhum e se comportava como default-deny total, quebrando produção. Achado **ALTO**
  adicional: DNS só liberava UDP/53, sem TCP de fallback. **Veredito: REPROVADO.**
- **v2** combinou `namespaceSelector` + `podSelector` no mesmo item de peer (AND, não OR)
  em toda regra cross-namespace, e adicionou TCP/53 à regra de DNS. A segunda rodada de
  verificação fechou os dois achados e não encontrou nenhum CRÍTICO/ALTO novo — critério de
  parada atingido. **Veredito: APROVADO.** As duas pendências restantes (porta de ingress
  do Sentinel ausente no mapa de serviços; dependência do label automático
  `kubernetes.io/metadata.name`) ficaram registradas como perguntas em aberto, não
  corrigidas por suposição.

## Criação via meta-prompting

Prompts gerados com **Claude Opus 5** (via claude.ai) a partir do gerador de prompts por
framework (`gerador-prompts-frameworks.md`); a execução e as duas rodadas de verificação
também rodaram no Opus 5. O meta-prompt em si não é entregável.

## Curadoria

### Justificativa do framework

**R-T-F** nos dois prompts, por critério 1 da decision tree do `prompt-lab-guia.md` —
output rígido e estruturado tem prioridade máxima na ordem de escolha. Na geração, o
output é literalmente código (manifesto Kubernetes); na verificação, é uma tabela de
veredito com formato fixo por pergunta. Em ambos, o Role fixa a postura (quem gera evita
inventar dado; quem verifica assume erro até provar o contrário), o Task isola a regra
central de cada elo, e o Format é o que torna o par de prompts reusável como item de
playbook — qualquer manifesto futuro passa pela mesma forma exata.

Descartados para os dois elos:
- **C-A-R-E** — cairia bem se o objetivo fosse calibrar *estilo* de resposta com exemplos
  de I/O. Aqui a estrutura é ditada pela especificação do Kubernetes (geração) ou pela
  lista fixa de 8 perguntas (verificação), não por um padrão estilístico a aprender por
  exemplo — few-shot seria redundante.
- **R-I-S-E** — cobriria bem o *diagnóstico* de um manifesto, mas o pedido central de cada
  elo não é diagnosticar de forma aberta: é produzir o artefato corrigido (geração) ou
  responder um checklist fechado (verificação).
- **T-A-G / B-A-B** — não se aplicam: não há workflow sequencial a automatizar nem mudança
  de estado a narrar em nenhum dos dois elos.

### Justificativa da técnica complementar — e a correção de atribuição

**A técnica do loop de verificação é Chain-of-Verification (CoVe), não Self-Consistency.**
O checkpoint pede, textualmente, que "a IA critica a própria saída, levanta as perguntas de
verificação que um revisor de segurança faria, e melhora a versão a cada rodada". Isso
mapeia elo a elo nos quatro passos do CoVe de Dhuliawala et al. (2023): (i) rascunho
inicial → Prompt 1 / v1; (ii) **planejar perguntas de verificação** → as 8 perguntas fixas
do Prompt 2; (iii) **respondê-las de forma independente**, sem condicionar no raciocínio
original → o Prompt 2 recebe só o YAML candidato, não a justificativa da geração; (iv)
versão verificada → v2.

Por que **não** é Self-Consistency (Wang et al., 2022): Self-Consistency roda o mesmo
prompt N vezes em paralelo e agrega por votação majoritária sobre uma resposta fechada.
Não há crítica, não há segunda versão que corrige a primeira, e o próprio paper restringe a
técnica a problemas com resposta única e verificável. Um manifesto de NetworkPolicy não tem
"resposta majoritária"; tem uma versão que passa na verificação e versões que não passam.
Confundir os dois não é só um erro de rótulo — levaria a rodar o gerador várias vezes e
"votar", o que não pegaria o erro crítico do `namespaceSelector`, porque as execuções
cometeriam o mesmo erro sistemático em paralelo, e a votação majoritária confirmaria o
erro em vez de expô-lo.

Por que CoVe e não apenas Self-Refine (Madaan et al., 2023): Self-Refine descreve o padrão
geral gerar→feedback→refinar, e serviria. CoVe é o caso mais específico e mais adequado
aqui por dois motivos: (1) o checkpoint pede explicitamente *perguntas de verificação*, que
é o passo (ii) nomeado do CoVe; (2) o CoVe existe justamente para mitigar o viés de
auto-confirmação respondendo as perguntas **isoladas** da resposta original — há literatura
(Xu et al., 2024; Huang et al., 2024) mostrando que Self-Refine sofre de *self-bias* quando
o mesmo contexto vê o próprio raciocínio. O Prompt 2 implementa esse isolamento de
propósito, como prompt separado e não como continuação da mesma conversa.

Técnicas de apoio: **CoT** (Wei et al., 2022) nos cinco passos internos do Prompt 1 — o
erro de `podSelector` cross-namespace é sutil o bastante para escapar sem raciocínio
explícito de mapeamento regra→seletor. **Critério de Parada** — encerra o loop em
`APROVADO`, com achados MÉDIO dependentes de dado ausente virando pergunta em aberto em vez
de disparar rodada desnecessária.

### O achado que justifica o CoVe existir aqui

O valor da entrega não é o YAML final — é que a **v1, gerada pelo mesmo prompt bem
escrito, continha uma falha crítica invisível a olho nu**: sintaticamente válida,
comentário parecendo correto, mas semanticamente equivalente a um default-deny total,
porque `podSelector` sem `namespaceSelector` não atravessa namespace. Uma política que não
filtra nada e uma que bloqueia tudo têm exatamente essa aparência de "parece certo" em
revisão rápida. É precisamente o tipo de erro que o passo de verificação independente do
CoVe pega e que a votação do Self-Consistency não pegaria — porque o erro é sistemático,
não aleatório: repetir a geração o reproduz, não o dilui.

### Lacuna de catálogo identificada

Nem CoVe (Dhuliawala et al., 2023) nem Self-Refine (Madaan et al., 2023) estão
documentados em `gerador-prompts-frameworks.md` ou `prompt-lab-guia.md` — os arquivos só
listam Zero-shot, Few-shot, CoT e Self-Consistency como técnicas complementares. Todo
checkpoint com padrão "gerar → criticar → refinar" fica sem rótulo correto disponível hoje.
Recomendação registrada para uma futura revisão do guia: adicionar as duas técnicas,
deixando explícita a distinção de que Self-Consistency é agregação paralela por votação
(resposta fechada) enquanto CoVe/Self-Refine são refino sequencial por auto-crítica
(artefato aberto).

### Por que a v2 foi aceita sem v3

O Critério de Parada foi fixado antes da primeira geração, não ajustado depois — evita
baixar a régua para justificar parar cedo. As duas pendências da v2 (porta de ingress não
especificada; dependência do label automático de namespace) não são achados que o prompt
devesse resolver sozinho: dependem de dado ausente no mapa de serviços, e inventá-lo
violaria a regra central. Documentá-las como perguntas em aberto é o resultado correto, não
um resultado incompleto.

### Como validar antes de promover a item de playbook

- Rodar com um segundo manifesto onde todas as contrapartes estão no **mesmo** namespace do
  Sentinel e confirmar que o modelo NÃO adiciona `namespaceSelector` desnecessário — o
  prompt não deve generalizar demais a partir deste caso cross-namespace.
- **Teste de porta ausente:** remover 5432 do mapa e confirmar que a regra de Forge sai sem
  porta e a pendência aparece no bloco de perguntas em aberto — não que o modelo invente
  uma porta plausível.
- **Teste de isolamento do CoVe:** dar ao Prompt 2 um YAML correto acompanhado de uma
  justificativa de geração *errada* (fora do template, só para o teste), e confirmar que o
  veredito segue o YAML, não a justificativa — valida que o isolamento entre os dois
  prompts está de fato reduzindo o viés de auto-confirmação.
- **Teste de regressão do achado crítico:** validar com `kubectl --dry-run=server` ou
  simulador de NetworkPolicy que a v2 permite Relay→Sentinel e nega qualquer outra
  origem — o teste que a v1 teria reprovado.

## Limitações conhecidas

- Assume o label automático de namespace `kubernetes.io/metadata.name` (padrão desde
  Kubernetes 1.21). Se algum namespace tiver esse label alterado manualmente, a regra
  correspondente para de casar — dependência registrada como pergunta em aberto, não
  validada automaticamente pelo prompt.
- NetworkPolicy opera em L3/L4: não inspeciona payload nem impede exfiltração via DNS
  tunneling ou abuso de uma porta já liberada por um peer legítimo.
- Seletores baseados em label pressupõem que o RBAC do cluster impede um workload não
  autorizado de assumir o label de um serviço legítimo (relabel attack) — a NetworkPolicy
  sozinha não é o controle contra isso.
- Não restringe porta quando o mapa de serviços não a declara; o resultado é ingress/egress
  mais aberto que o ideal, registrado como pergunta em aberto para decisão humana, não
  corrigido por suposição do modelo.
- O critério de parada limita a 3 rodadas; um manifesto que não convergir nesse limite
  precisa de revisão humana direta, não de mais rodadas automáticas.
