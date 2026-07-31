# Elo 3 — Plano executável e reversível (Fase 1)

**Modelo:** Claude Sonnet 5 via claude.ai · thinking level Medium.

## Entrada

- `{{OUTPUT_ELO_2}}`: a estratégia completa do [Elo 2](./elo-2-estrategia.md) (encadeamento).
- `{{FASE_ALVO}}`: `Fase 1 — Ingestão Contínua em Sombra`.
- `{{RESTRICOES_OPERACIONAIS}}`:

```text
Restrições operacionais do time:
- cutover e mudanças de roteamento só podem ocorrer fora do horário comercial (00h–06h UTC)
- os relatórios de billing da Pepper rodam de madrugada e não podem ser interrompidos nem ter a fonte de dados alterada durante a janela deles
- toda mudança precisa ser reversível em menos de 10 minutos
- perda de telemetria é inaceitável, mesmo durante a transição
- o time opera sobre Kubernetes; mudanças de deploy passam por pipeline com revisão
```

## Saída do modelo (plano executável da Fase 1)

**Pré-condições**

Corresponde exatamente às dependências declaradas na seção 4 da estratégia para a Fase 1, mais o pré-requisito universal da Fase 0 (seção 2, "antes de qualquer fase"):

- Infraestrutura que permita rodar o caminho batch atual e um caminho novo em paralelo sem interferência mútua (pré-requisito 1, Fase 0) — condição geral para qualquer fase, incluindo esta.
- Telemetria comparável entre os dois caminhos já implantada e coletando dados (pré-requisito 2, Fase 0).
- Mecanismo de detecção de divergência entre as duas saídas, com limiar objetivo já definido (pré-requisito 3, Fase 0) — o valor numérico do limiar e da janela de sustentação mínima é output desta fase da estratégia, não é fixado aqui; onde for necessário referenciá-los abaixo, uso os placeholders `<LIMIAR_DIVERGENCIA>` e `<JANELA_MIN_SUSTENTACAO>`.
- Design do mecanismo de idempotência/replay para o novo caminho já definido (pré-requisito 6, Fase 0), mesmo que a implementação específica do consumidor da Fase 1 ainda esteja pendente (é isso que os passos 3–4 abaixo entregam).

Se qualquer um destes quatro itens não estiver satisfeito, esta fase não pode iniciar — reporte como bloqueio de pré-condição, não como bloqueio de fase (a fase em si não está NÃO PRONTA).

**Suposição declarada:** não há, no estado atual do Forge ou nas restrições operacionais, menção a um mecanismo de feature flag/config toggle. Os passos abaixo assumem que existe algum mecanismo de habilitação/desabilitação controlada por configuração (não por deploy/undeploy) para ligar e desligar o consumo do novo consumidor — se isso não existir, os passos 3, 4 e 6 e a reversão associada precisam ser refeitos como deploy/undeploy via pipeline, o que muda o tempo de reversão e deve ser revalidado contra a restrição de reversão em <10min.

---

**Passos de execução**

1. **Provisionar o armazenamento intermediário isolado.**
   Ação: criar via pipeline com revisão (Kubernetes) o recurso de armazenamento próprio do caminho em sombra, separado das tabelas particionadas por hora, sem nenhum consumidor apontando para ele.
   Critério de sucesso: recurso existe, está acessível apenas pelo novo consumidor (ainda não implantado), e nenhum job de leitura (Sentinel, Cerebro, Pepper, transformação) tem permissão ou rota de acesso a ele.
   Verificar antes do próximo passo: confirmar, por inspeção de IAM/rede/config, que nenhum caminho de leitura existente consegue alcançar esse armazenamento.

2. **Implantar o novo consumidor contínuo do Relay, desligado.**
   Ação: deploy via pipeline com revisão do consumidor contínuo, com o mecanismo de habilitação (suposição acima) em estado desligado — processo sobe, mas não consome do Relay.
   Critério de sucesso: pod/processo saudável, sem consumo de mensagens, cron `forge-batch-ingest` seguindo inalterado.
   Verificar antes do próximo passo: telemetria comparável (pré-condição) já está reportando dados do caminho batch normalmente e não detecta atividade do caminho novo (baseline zero).

3. **Ligar o consumo em pequenos blocos, escrevendo apenas no armazenamento intermediário.**
   Ação: habilitar o mecanismo de consumo (config toggle), com escrita restrita ao armazenamento do passo 1; cron continua sendo o único caminho autoritativo, inalterado.
   Critério de sucesso: consumidor lendo blocos do Relay em taxa > 0, sem erros de escrita, sem qualquer consumidor real apontando para o dado gerado.
   Verificar antes do próximo passo: telemetria comparável está capturando volume/latência de ambos os caminhos simultaneamente.

4. **Validar idempotência/replay por bloco (implementação específica desta fase).**
   Ação: injetar falha controlada em um bloco (ex.: interromper o processo durante o processamento de um bloco específico) e disparar o replay apenas daquele bloco, usando o design de idempotência da Fase 0.
   Critério de sucesso: o bloco reprocessado aparece exatamente uma vez no armazenamento intermediário (sem duplicação, sem perda), e os blocos seguintes não acumulam atraso nem reprocessam dados de blocos anteriores.
   Verificar antes do próximo passo: nenhum efeito colateral no cron ou no armazenamento intermediário além do bloco testado.

5. **Deixar os dois caminhos rodando em paralelo, sem intervenção, até acumular dados suficientes.**
   Ação: nenhuma ação de mudança — apenas observação via telemetria comparável e mecanismo de divergência.
   Critério de sucesso: série temporal de divergência de volume e latência disponível, com dados suficientes para avaliar tendência (não é ainda o cutover, é o acúmulo de evidência).
   Verificar antes do próximo passo: nenhuma alteração foi feita no cron ou em qualquer consumidor real durante essa observação (checagem de que a fase permanece não intrusiva).

6. **Avaliar a condição de saída da fase (ver "Verificação de cutover" abaixo).**
   Ação: comparar a série de divergência contra `<LIMIAR_DIVERGENCIA>` pelo período `<JANELA_MIN_SUSTENTACAO>`.
   Critério de sucesso: limiar satisfeito de forma sustentada pela janela mínima definida na Fase 0.
   Se não satisfeito: manter o caminho em sombra rodando (passo 5) e não avançar; isso não é falha, é a fase ainda em observação.

**Checagem de restrição operacional para os passos acima:** nenhum dos passos 1–6 promove o caminho novo a autoritativo, altera roteamento de consumo real, nem toca na fonte de dados usada pela Pepper — logo, a restrição de "cutover só 00h–06h UTC" e "fonte de dados da Pepper intocável durante a janela dela" não se aplicam a nenhum destes passos, pois não há cutover nesta fase. **Ressalva não é conflito, é atenção:** se o novo consumidor compartilha capacidade de leitura do Relay com o cron, os passos 2–3 (início real de consumo) podem, em tese, competir por throughput com o cron nos horários em que a Pepper depende de um corte fechado. Isso não está declarado como dependência real no diagnóstico (Relay não é mencionado como recurso com contenção), então não bloqueio o passo — apenas registro como algo a monitorar via telemetria comparável, não como suposição embutida silenciosamente.

---

**Verificação de cutover**

A Fase 1 não promove nenhum caminho a autoritativo — não há "cutover" no sentido de virada de tráfego. A condição de saída da fase é a seguinte, traduzida em métrica mensurável:

- **Métrica:** divergência de volume (contagem de eventos captados) e divergência de latência (tempo entre geração do evento e captação) entre o caminho contínuo (sombra) e o caminho cron, medidas para a mesma janela de tempo de origem.
- **Fonte:** mecanismo de telemetria comparável e mecanismo de detecção de divergência definidos na Fase 0 (pré-requisitos 2 e 3) — não uma fonte nova criada nesta fase.
- **Limiar:** `<LIMIAR_DIVERGENCIA>`, valor objetivo definido na Fase 0. Não invento um número aqui porque a estratégia atribui essa decisão explicitamente à Fase 0, não à Fase 1.
- **Janela de sustentação mínima:** `<JANELA_MIN_SUSTENTACAO>`, também definida na Fase 0, correspondendo ao período mínimo observado via telemetria comparável antes de considerar a divergência estável (não um pico isolado).

Só quando a divergência ficar abaixo de `<LIMIAR_DIVERGENCIA>` de forma contínua por `<JANELA_MIN_SUSTENTACAO>` é que a fase é considerada encerrada. Nenhum passo desta fase pode interromper o caminho batch atual antes dessa condição ser satisfeita (restrição operacional explícita atendida: o cron nunca é parado nesta fase).

---

**Procedimento sob falha parcial**

Comportamento já definido na estratégia: falha no consumo de um bloco deve gerar replay apenas daquele bloco, sem acumular no próximo. Operacionalizando:

1. **Detecção:** o consumidor marca um bloco como falho quando o processamento daquele bloco não é confirmado (ack) dentro do procedimento normal — isso deve gerar um evento de alerta específico por identificador de bloco, sem interromper o processamento dos blocos seguintes.
2. **Isolamento:** o bloco falho é colocado em estado de "pendente de replay" — os blocos subsequentes continuam sendo processados normalmente; nenhum backlog se forma no fluxo principal.
3. **Replay:** dispara-se o replay apenas do bloco marcado, usando o mecanismo de idempotência da Fase 0 (chave de deduplicação por bloco), escrevendo novamente apenas no armazenamento intermediário isolado.
4. **Verificação pós-replay:** confirmar, via consulta ao armazenamento intermediário, que o bloco aparece exatamente uma vez (nem ausente, nem duplicado).
5. **Escalonamento se a taxa de falha de blocos ultrapassar um patamar observável (ex.: falhas recorrentes e crescentes):** desligar o consumo (mecanismo de habilitação do passo 3 dos passos de execução) sem tocar no cron — isso é seguro porque nenhum consumidor real depende do caminho em sombra. Essa ação é reversível em minutos (desligar o toggle), atendendo à restrição de reversão em <10 minutos.
6. Em nenhum momento este procedimento aciona o cron, altera a fonte de dado da Pepper, ou requer ação fora da janela 00h–06h UTC, porque nenhuma etapa aqui é cutover ou mudança de roteamento real.

---

**Reversão**

Como nenhum consumidor real aponta para o caminho em sombra, a reversão nunca tem efeito colateral em produção — isso é uma propriedade da fase, não uma suposição minha.

1. Desligar o mecanismo de habilitação do consumidor contínuo (config toggle) — para imediatamente o consumo do Relay pelo caminho novo. Tempo estimado: segundos a poucos minutos, dentro da restrição de <10 minutos.
2. Opcionalmente, remover o deployment do consumidor via pipeline com revisão (não obrigatório para considerar a reversão completa, já que o passo 1 já elimina qualquer atividade).
3. **Dados já processados pelo caminho novo durante a fase:** como o armazenamento intermediário é isolado e nenhum consumidor real o lê, os dados ali podem ser mantidos (para análise posterior de divergência) ou descartados — nenhuma das duas opções afeta produção. Recomenda-se manter até a conclusão da análise de divergência que motivou a reversão, e só então decidir descarte, via pipeline com revisão.
4. O caminho batch (cron `forge-batch-ingest`) nunca foi parado nesta fase — não há necessidade de "devolver" autoridade a ele, pois ele nunca deixou de ser autoritativo. Isso satisfaz diretamente a restrição de não parar o caminho batch antes da verificação de cutover.
5. Confirmar, após reversão, que a telemetria comparável do caminho batch continua intacta (restrição de telemetria nunca pode ser perdida) — a reversão desliga apenas o caminho novo, nunca a telemetria do caminho existente.

---

**Critério de encerramento da fase**

A Fase 1 é considerada concluída quando, simultaneamente:

- A condição de cutover (divergência de volume e latência abaixo de `<LIMIAR_DIVERGENCIA>` sustentada por `<JANELA_MIN_SUSTENTACAO>`) for satisfeita; e
- O caminho em sombra tiver acumulado tempo de operação suficiente para gerar dados de sombra estáveis o bastante para servir de base de teste à lógica de transformação da Fase 2 (dependência explícita da Fase 2 sobre a Fase 1, seção 4 da estratégia) — este segundo ponto não tem métrica numérica fornecida no diagnóstico; deve ser tratado como critério a refinar quando a investigação de código/DAG da Fase 0 (que bloqueia a Fase 2) estiver concluída, não decidido aqui.

Encerrar a fase libera apenas o início da Fase 2, e mesmo essa liberação depende também da investigação do código/DAG das 14 etapas (Fase 0), que é bloqueio independente desta fase.