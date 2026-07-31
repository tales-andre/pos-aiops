---
nome: Migração Batch para Event-Driven
descricao: "Cadeia de três prompts que conduz a migração de um pipeline de lote para orientado a eventos: diagnóstico do estado atual, estratégia de migração em fases reversíveis e plano executável por fase."
versao: 1.0.0
tags: [devops, migracao, event-driven, pipeline, prompt-chaining]
inputs:
  - nome: ESTADO_ATUAL_FORGE
    descricao: "Descrição do pipeline atual em lote (ingestão, transformação, escrita, consumidores, ponto frágil). Entrada externa do Elo 1."
  - nome: REQUISITOS_MIGRACAO
    descricao: "Garantias que a migração precisa preservar (continuidade dos consumidores, reversibilidade, nada de big-bang). Entrada externa dos Elos 1 e 2."
  - nome: OUTPUT_ELO_1
    descricao: "Encadeamento: a saída do Elo 1 (diagnóstico) é o parâmetro de entrada do Elo 2."
  - nome: OUTPUT_ELO_2
    descricao: "Encadeamento: a saída do Elo 2 (estratégia em fases) é o parâmetro de entrada do Elo 3."
  - nome: FASE_ALVO
    descricao: "Nome da fase (definida pelo Elo 2) que o Elo 3 deve detalhar. Entrada externa do Elo 3."
  - nome: RESTRICOES_OPERACIONAIS
    descricao: "Restrições de execução do time (janelas de mudança, o que não pode ser interrompido, tempo de reversão). Entrada externa do Elo 3."
---

# Cadeia de Prompts — Migração do Forge (batch → event-driven)

**Elo 1 — Framework:** R-I-S-E (diagnóstico do estado atual)
**Elo 2 — Framework:** B-A-B (desenho da estratégia de migração em fases)
**Elo 3 — Framework:** R-T-F (plano executável e reversível por fase)
**Gerador (meta-prompt):** `gerador-prompts-frameworks.md`

Cada elo recebe como entrada o output do elo anterior. Nenhum elo decide sozinho o que o próximo
vai fazer com o resultado — a saída de um é literalmente o parâmetro de entrada do seguinte.

---

## Elo 1 — Diagnóstico do estado atual

```
ROLE:
Você é Staff Engineer de plataforma de dados, especialista em migração de pipelines de batch para
arquitetura orientada a eventos. Sua função neste elo é apenas diagnosticar — você não propõe
solução, não desenha fases, não estima cronograma. Qualquer sugestão de caminho é falha de escopo.

INPUT:
<ESTADO_ATUAL>
{{ESTADO_ATUAL_FORGE}}
</ESTADO_ATUAL>

<REQUISITOS_DA_MIGRACAO>
{{REQUISITOS_MIGRACAO}}
</REQUISITOS_DA_MIGRACAO>

STEPS:
1. MAPEAR A CADEIA ATUAL. Reconstrua o pipeline como uma sequência de estágios (ingestão,
   transformação passo a passo, escrita, consumo), nomeando o mecanismo de cada um e a garantia
   que ele hoje oferece (ordem, completude, atomicidade, particionamento).
2. MAPEAR OS CONSUMIDORES. Para cada dependente listado no estado atual, determine: o que ele lê
   exatamente (tabela, partição, agregação), com que frequência espera dado novo, e que suposição
   ele faz sobre a forma do dado (hora fechada, transação completa, ordem de chegada) que deixaria
   de ser verdade num modelo contínuo.
3. LOCALIZAR ACOPLAMENTOS IMPLÍCITOS. Identifique onde o desenho atual depende do fechamento da
   hora além do agendamento — ex.: etapas que assumem lote completo antes de agregar, particionamento
   por hora usado como unidade transacional, relatórios que assumem tabela estável em um horário fixo.
4. CLASSIFICAR CADA ESTÁGIO quanto à natureza da transformação: estágio que exige a janela inteira
   para produzir resultado correto (holístico), estágio que pode processar evento a evento sem perda
   de correção (paralelizável), ou estágio que fica ambíguo com os dados disponíveis — marque como
   NÃO DECIDÍVEL e diga o que resolveria a ambiguidade.
5. IDENTIFICAR OS MODOS DE FALHA HERDADOS. A partir do ponto frágil relatado (acúmulo em dobro após
   falha), enumere os demais modos de falha que o desenho atual esconde e que uma migração precisa
   encarar de frente, mesmo que o estado atual não os relate explicitamente.
6. LISTAR PRÉ-REQUISITOS DE MIGRAÇÃO. A partir dos passos 1 a 5, produza o que precisa existir antes
   de qualquer etapa de migração começar (ex.: capacidade de rodar dois caminhos em paralelo,
   telemetria comparável entre os dois modelos, forma de detectar divergência).

REQUIREMENTS:
- Nenhuma recomendação de solução, arquitetura-alvo, tecnologia ou cronograma. Este elo termina no
  diagnóstico; a proposta de caminho pertence ao próximo elo da cadeia.
- Toda afirmação sobre o comportamento atual cita o dado do estado atual que a sustenta. Não infira
  comportamento não descrito.
- Trate "quem depende do Forge" como contrato implícito: assuma que a suposição de cada consumidor
  é uma restrição real até prova em contrário, mesmo que pareça frágil.
- Onde o estado atual não disser o suficiente para concluir, marque NÃO DECIDÍVEL e diga
  exatamente o dado que falta.
- Português brasileiro, termos técnicos em inglês preservados (batch, streaming, event-driven,
  partition, watermark, backpressure, idempotência, replay, checkpoint).
- Sem preâmbulo, sem meta-comentário, sem repetir o enunciado.

EXPECTATION:
Entregue exatamente estas seções, em markdown, nesta ordem:
1. MAPA DA CADEIA ATUAL — tabela: estágio | mecanismo | garantia hoje oferecida.
2. CONSUMIDORES E SUAS SUPOSIÇÕES — tabela: consumidor | o que lê | frequência esperada |
   suposição que quebra em modelo contínuo.
3. ACOPLAMENTOS IMPLÍCITOS — lista, cada item com o mecanismo exato do acoplamento.
4. CLASSIFICAÇÃO DOS 14 ESTÁGIOS — tabela: estágio (ou grupo de estágios) | classificação
   (holístico / paralelizável / não decidível) | justificativa.
5. MODOS DE FALHA HERDADOS — lista, cada um com o cenário que o dispara.
6. PRÉ-REQUISITOS DE MIGRAÇÃO — lista numerada, cada item com o motivo de ser bloqueante.
7. LACUNAS DE DIAGNÓSTICO — tabela: o que falta saber | por que impede concluir | como descobrir.

Esta seção 7 é o principal insumo do próximo elo da cadeia: seja específico o bastante para que
outro prompt, sem acesso a este diálogo, consiga agir só com o que está escrito aqui.
```

---

## Elo 2 — Estratégia de migração em fases

```
Você é Staff Engineer de plataforma de dados. Neste elo você recebe um diagnóstico já pronto — não
o refaça, não o questione, trate-o como verdade estabelecida. Sua função aqui é desenhar a
estratégia de migração em fases, sem ainda detalhar comandos ou cronograma de execução — isso
pertence ao próximo elo.

BEFORE — o diagnóstico do estado atual, produzido no elo anterior:
<DIAGNOSTICO>
{{OUTPUT_ELO_1}}
</DIAGNOSTICO>

AFTER — o estado desejado, expresso como as garantias que a migração precisa preservar:
<REQUISITOS_DA_MIGRACAO>
{{REQUISITOS_MIGRACAO}}
</REQUISITOS_DA_MIGRACAO>

Estas garantias não são preferências: nenhuma fase da estratégia pode violá-las, mesmo
temporariamente. Uma fase que exige quebrar uma garantia por período de transição precisa dizer
isso explicitamente e propor a mitigação, nunca omitir.

BRIDGE — o processo que liga o diagnóstico à estratégia. Execute na ordem:

1. ORDENAR PELA CLASSIFICAÇÃO DOS ESTÁGIOS. Use a classificação holístico/paralelizável/não
   decidível do diagnóstico para decidir a ordem de migração: estágios paralelizáveis migram antes
   dos holísticos, porque não dependem de redesenhar a lógica de agregação. Estágios marcados como
   não decidíveis no diagnóstico não podem ser a primeira fase.
2. DESENHAR RODANDO EM PARALELO, NÃO EM SUBSTITUIÇÃO. Cada fase deve manter o caminho batch atual
   funcionando integralmente enquanto o caminho novo é validado ao lado, nunca substituir antes de
   comparar. Diga explicitamente em cada fase qual caminho está autoritativo (de onde os
   consumidores realmente leem) e qual está em sombra (rodando para validação, sem consumidor
   apontado para ele ainda).
3. RESPEITAR OS PRÉ-REQUISITOS DO DIAGNÓSTICO. Nenhuma fase pode ser proposta antes que os
   pré-requisitos de migração listados no diagnóstico estejam satisfeitos. Se um pré-requisito for
   ele mesmo grande, ele vira a Fase 0.
4. TRATAR CADA CONSUMIDOR SEPARADAMENTE. Migre o consumo de cada dependente do Forge em fase
   própria, na ordem do mais tolerante a atraso/divergência para o mais sensível, e nunca migre um
   consumidor cuja suposição (do diagnóstico) ainda não tenha sido endereçada.
5. DEFINIR O PONTO DE VIRADA (CUTOVER) DE CADA FASE. Para cada fase, declare a condição objetiva
   que autoriza tornar o caminho novo autoritativo, e não uma data-alvo. Se a condição não puder
   ser expressa objetivamente, marque a fase como NÃO PRONTA e diga o que falta para torná-la.
6. DEFINIR REVERSÃO POR FASE. Cada fase precisa de um caminho de volta ao estado anterior que não
   dependa de as fases seguintes ainda não terem começado. Se uma fase não puder ser revertida
   isoladamente, diga isso e proponha a mitigação (ex.: janela de dupla escrita, flag de roteamento).
7. TRATAR O PONTO FRÁGIL DO DIAGNÓSTICO COMO REQUISITO TRANSVERSAL. O modo de falha em que uma
   falha dobra o volume do próximo lote não pode ser herdado silenciosamente pelo novo modelo:
   toda fase precisa declarar como ela se comporta sob falha parcial, não só sob operação normal.
8. IDENTIFICAR RISCOS ENTRE FASES. Aponte onde uma fase cria dependência oculta na seguinte (ex.:
   uma fase que só funciza se a anterior tiver sido mantida rodando em paralelo por tempo mínimo).

REGRAS INVIOLÁVEIS:
- Proibido big-bang: nenhuma fase pode propor substituir mais de um estágio ou mais de um
  consumidor de uma vez sem período de validação em paralelo.
- Proibido propor cutover por data. Cutover só é válido quando expresso como condição observável
  (ex.: divergência entre os dois caminhos abaixo de um limiar, por um período mínimo).
- Toda fase tem reversão. Fase sem reversão declarada é reprovada e deve ser subdividida até ter uma.
- Não avance a ordem das fases além do que a classificação do diagnóstico sustenta: um estágio
  holístico não pode ser movido para fase anterior a um paralelizável só por conveniência narrativa.
- Não decida o que o diagnóstico marcou como NÃO DECIDÍVEL. Onde o diagnóstico deixou uma lacuna,
  a fase correspondente deve declarar essa lacuna como bloqueio e não avançar sobre ela.
- Sem comandos de execução, sem ferramentas específicas, sem estimativa de tempo em dias/semanas —
  isso é do próximo elo da cadeia. Este elo entrega a estrutura de fases e suas condições.
- Português brasileiro, termos técnicos em inglês preservados.
- Sem preâmbulo, sem meta-comentário.

FORMATO DE ENTREGA — exatamente estas seções, em markdown, nesta ordem:
1. ORDEM DE MIGRAÇÃO E JUSTIFICATIVA — qual critério do diagnóstico define a ordem.
2. FASE 0 (se houver) — pré-requisitos que precisam virar trabalho antes da Fase 1.
3. FASES — para cada fase: nome, o que migra, caminho autoritativo vs. caminho em sombra,
   consumidor(es) afetado(s), condição de cutover, comportamento sob falha parcial, reversão.
4. DEPENDÊNCIAS ENTRE FASES — o que uma fase exige que a anterior já tenha estabelecido.
5. FASES NÃO PRONTAS — as que dependem de uma lacuna do diagnóstico, com a lacuna citada.
6. RISCOS TRANSVERSAIS — o que pode dar errado atravessando mais de uma fase.

Esta saída é o input do próximo elo, que vai detalhar o plano executável de cada fase. Nomeie as
fases de forma estável (Fase 1, Fase 2...) para que o próximo elo possa referenciá-las sem
ambiguidade.
```

---

## Elo 3 — Plano executável e reversível por fase

```
[ROLE]
Você é Tech Lead responsável por executar a migração desenhada no elo anterior. Você não
questiona a estratégia nem reordena fases — sua função é torná-las executáveis. Se encontrar uma
fase marcada como NÃO PRONTA ou dependente de lacuna do diagnóstico, você não a detalha: você
reporta o bloqueio.

[TASK]
Detalhe um plano executável e reversível para a fase indicada em {{FASE_ALVO}}, a partir da
estratégia completa abaixo, de forma que qualquer engenheiro do time — não só quem participou do
desenho — consiga executar, verificar e reverter sem depender de contexto tácito.

<ESTRATEGIA_DE_MIGRACAO>
{{OUTPUT_ELO_2}}
</ESTRATEGIA_DE_MIGRACAO>

<FASE_ALVO>
{{FASE_ALVO}}
</FASE_ALVO>

<RESTRICOES_OPERACIONAIS>
{{RESTRICOES_OPERACIONAIS}}
</RESTRICOES_OPERACIONAIS>

Processo, na ordem, antes de escrever o plano final:
1. Confirme que a fase alvo não está listada como NÃO PRONTA na estratégia. Se estiver, pare e
   produza apenas a seção de BLOQUEIO — não invente uma execução para lacuna não resolvida.
2. Traduza a condição de cutover da fase em uma verificação mensurável: a métrica exata, a fonte
   dela, o limiar e por quanto tempo o limiar precisa se sustentar antes de autorizar a virada.
3. Quebre a fase em passos pequenos o bastante para que cada um seja revertível isoladamente —
   se um passo não for revertível sozinho, funda-o com o passo de reversão correspondente antes
   de escrever o plano, não depois.
4. Para o comportamento sob falha parcial já declarado na fase, escreva o procedimento de detecção
   e resposta — não repita a frase da estratégia, opere sobre ela.
5. Verifique se algum passo contradiz alguma restrição operacional recebida; se contradizer, marque
   o passo como CONFLITO e proponha a variante compatível, em vez de ignorar a restrição.

[FORMAT]
Entregue como:

- **Pré-condições** — lista do que precisa estar verdadeiro antes do primeiro passo (deve
  corresponder às dependências entre fases da estratégia; não invente pré-condição nova).
- **Passos de execução** — lista numerada; cada passo com: ação, comando ou operação exata,
  critério objetivo de sucesso, e o que verificar antes de ir ao próximo passo.
- **Verificação de cutover** — a condição de cutover da fase, expressa como métrica, fonte, limiar
  e janela de sustentação mínima antes de tornar o caminho novo autoritativo.
- **Procedimento sob falha parcial** — passo a passo do que fazer se a fase falhar no meio, com
  base no comportamento já definido na estratégia para esta fase.
- **Reversão** — passo a passo para desfazer esta fase e devolver o caminho batch a autoritativo,
  incluindo o que fazer com dados já processados pelo caminho novo durante a fase.
- **Critério de encerramento da fase** — o que precisa ser verdade para considerar esta fase
  concluída e liberar a próxima fase da cadeia.
- **Bloqueios** (só se aplicável) — se a fase depender de lacuna não resolvida no diagnóstico ou
  estiver marcada como NÃO PRONTA, esta é a única seção que deve ser preenchida.

Restrições:
- Nenhum passo pode ser irreversível sem um passo de reversão explícito logo ao lado.
- Nenhum passo pode assumir ferramenta, plataforma ou comando que não tenha sido mencionado no
  estado atual do Forge ou nas restrições operacionais — se for necessário assumir algo, declare
  a suposição em vez de embuti-la silenciosamente no passo.
- Proibido propor parar o caminho batch atual antes que a verificação de cutover desta fase tenha
  sido satisfeita.
- Português brasileiro, termos técnicos em inglês preservados.
- Sem preâmbulo, sem meta-comentário, sem repetir o enunciado.
```
