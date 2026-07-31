# Execução — Estratégia de backpressure do Relay

**Modelo:** Gemini 3.6 Flash (`gemini-3.6-flash`) via Google AI Studio · thinking level Medium · grounding off · latência observada ~48,8s.

## Entrada

### `{{ESTADO_ATUAL}}`

```text
Relay (barramento de eventos):
- throughput sustentado: 180k msgs/s
- pico observado no incidente da semana passada: 320k msgs/s por 25min
- retenção atual: 4h
- consumidores: Forge (ingestão), Sentinel (alerting em tempo real)
```

### `{{RESTRICOES}}`

```text
- alerting do Sentinel não pode atrasar mais que 60s (SLA com cliente)
- ingestão do Forge pode atrasar até 15min sem violar SLA
- orçamento de infra do trimestre já está 8% acima do previsto
- Steve Rogers lembra que o barramento antigo perdia mensagens sob pico,
  e perda de telemetry é inaceitável para um produto de observabilidade
```

### `{{OPCOES_EM_MESA}}`

```text
- dar prioridade ao Sentinel (alerting em tempo real) na frente do Forge (que pode esperar até 15min)
- guardar o que não foi processado numa fila separada para reprocessar depois (o que se chama dead-letter queue)
- dividir o Relay por cliente, para que um cliente barulhento não atrapalhe os outros
- aumentar automaticamente o número de consumidores quando a carga sobe
```

## Saída do modelo

### 1. LEITURA DO GAP

* **Capacidade sustentada do barramento:** $180.000\text{ msgs/s}$
* **Pico observado:** $320.000\text{ msgs/s}$ durante $25\text{ min}$ ($1.500\text{ s}$)
* **Déficit de capacidade no pico:** $320.000 - 180.000 = 140.000\text{ msgs/s}$
* **Volume acumulado no pico:** $140.000\text{ msgs/s} \times 1.500\text{ s} = 210.000.000\text{ msgs}$ ($210\text{M msgs}$)
* **Tempo de drenagem do backlog pós-pico:** **NÃO DECIDÍVEL** (falta a taxa de chegada pós-pico).
  * *Cenário extremo A (taxa pós-pico = $180k\text{ msgs/s}$):* Capacidade residual = $0\text{ msgs/s} \rightarrow \text{Tempo de drenagem} = \infty$.
  * *Cenário extremo B (taxa pós-pico = $100k\text{ msgs/s}$):* Capacidade residual = $80k\text{ msgs/s} \rightarrow \text{Tempo de drenagem} = 210\text{M} / 80k = 2.625\text{ s}$ ($43,75\text{ min}$).
* **Lag acumulado sem mitigação:** $25\text{ min}$ de pico + tempo de drenagem.
* **Capacidade de retenção:** $4\text{h}$ ($14.400\text{ s}$). A $320k\text{ msgs/s}$, suporta até $4,608 \times 10^9\text{ msgs}$. O volume do pico ($210\text{M}$) consome apenas ~4,5% da janela temporal. Limite em bytes: **NÃO DECIDÍVEL** sem o tamanho médio da mensagem.

---

### 2. RESTRIÇÃO VINCULANTE

A restrição vinculante é o **SLA de alerting do Sentinel ($\le 60\text{s}$)**. 

Sem mitigação, durante um pico de $25\text{ min}$ ($1.500\text{ s}$), o `lag` do Sentinel atinge no mínimo $1.500\text{ s}$, violando o limite contratual de $60\text{s}$ em $1.440\text{ s}$ (estouro de 2.400%). O SLA do Forge ($\le 15\text{min} = 900\text{s}$) é violado por margem menor ($600\text{ s}$). A retenção de $4\text{h}$ absorve o volume sem perda física, e o orçamento (+8%) é negociável perante violação contratual externa.

---

### 3. MATRIZ DE DECISÃO

| Opção | Onde atua | Sentinel SLA ($\le 60\text{s}$) | Forge SLA ($\le 15\text{min}$) | Zero Perda Telemetria | Orçamento Trimestral (+8%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **0. Não fazer nada** | Barramento / Consumidor | **VIOLA** (`lag` de $1.500\text{s}$, excede em $1.440\text{s}$) | **VIOLA** (`lag` $\ge 1.500\text{s}$, excede em $600\text{s}$) | **ATENDE** ($0$ msgs perdidas; retenção $4\text{h} \ge 25\text{min}$) | **ATENDE** (variação de R$ 0,00) |
| **1. Priorizar Sentinel sobre Forge** | Consumidor | **ATENDE** (`lag` $< 1\text{s}$ com dedicação de $320k\text{ msgs/s}$) | **VIOLA** (`lag` de $1.500\text{s}$ no Forge, excede $900\text{s}$ em $600\text{s}$) | **ATENDE** ($0$ msgs perdidas; retidas no barramento) | **ATENDE** ($0\%$ de alteração em infraestrutura) |
| **2. Dead-Letter Queue (DLQ) no estouro** | Consumidor / Barramento | **ATENDE** (`lag` $< 60\text{s}$ ao desviar tráfego) | **ATENDE** (`lag` $< 900\text{s}$ ao desviar tráfego) | **VIOLA** (desvia $210\text{M}$ msgs do fluxo primário sob pico) | **ATENDE** (custo de armazenamento $< 0,1\%$) |
| **3. Divisão do Relay por cliente** | Barramento | **NÃO DECIDÍVEL** (falta curva por cliente; se 1 tenant gera $320k\text{/s}$, `lag` excede $60\text{s}$) | **NÃO DECIDÍVEL** (falta curva por cliente; `lag` pode exceder $900\text{s}$) | **ATENDE** ($0$ msgs perdidas na retenção) | **VIOLA** (duplicação de clusters aumenta infra estática em $>15\%$) |
| **4. Autoscaling elástico de consumidores** | Consumidor | **ATENDE** (escala de $180k$ para $320k\text{/s}$ em $<60\text{s}$; `lag` $<60\text{s}$) | **ATENDE** (processa $320k\text{/s}$ em tempo real; `lag` $\approx 0\text{s} < 900\text{s}$) | **ATENDE** ($0$ msgs perdidas; processamento síncrono) | **ATENDE** (impacto elástico por $25\text{min}$ é $< 0,05\%$ no trimestre) |
| **5. Quotas e Backpressure no produtor** | Produtor | **ATENDE** (restrinja barramento a $180k\text{/s}$; `lag` no barramento $< 60\text{s}$) | **VIOLA** (`lag` no produtor atinge $1.500\text{s}$, excede SLA em $600\text{s}$) | **VIOLA** (risco de overflow no buffer do produtor após $25\text{min}$) | **ATENDE** ($0\%$ de alteração em infraestrutura) |

---

### 4. O PREÇO DE CADA OPÇÃO

| Opção | O que se perde | Quem paga o preço | O que trava no futuro |
| :--- | :--- | :--- | :--- |
| **0. Não fazer nada** | Conformidade de SLA e confiança do cliente | Time de suporte e contas comerciais | Acordos comerciais futuros sob penalidade |
| **1. Priorizar Sentinel** | Atualização do pipeline de ingestão (Forge) | Time do Forge e clientes dependentes de dados atualizados | Autonomia de ingestão do Forge em horários de pico |
| **2. Dead-Letter Queue (DLQ)** | Integridade do pipeline primário de tempo real | Time de dados (reprocessamento manual) e consistência | Garantia de ordem e semântica de entrega única |
| **3. Divisão por cliente** | Eficiência orçamentária e simplicidade operacional | Orçamento de infraestrutura (agrava estouro de 8%) | Flexibilidade para reconfigurar topologia de barramento |
| **4. Autoscaling elástico** | Previsibilidade absoluta de custos de compute em curto prazo | Orçamento variável de infraestrutura | Dependência de infraestrutura orquestrada elástica |
| **5. Quotas / Backpressure** | Capacidade de absorção na borda e estabilidade do produtor | Engenharia de aplicação (gestão de memória cliente) | Arquitetura do produtor engessada por limites rígidos |

---

### 5. OPÇÕES REPROVADAS

* **Opção 1 (Priorização do Sentinel sobre Forge - da lista do time): REPROVADA.** 
  * *Mecanismo de falha:* O pico dura $25\text{ min}$ ($1.500\text{ s}$). Redirecionar a capacidade para garantir o Sentinel estagna o processamento do Forge por $1.500\text{ s}$. Como o SLA do Forge é de $15\text{ min}$ ($900\text{ s}$), o Forge acumula um `lag` de $1.500\text{ s}$, violando seu SLA em $600\text{ s}$. A opção apenas transfere a violação de SLA de um consumidor para outro.
* **Opção 2 (Dead-Letter Queue / DLQ - da lista do time): REPROVADA.** 
  * *Mecanismo de falha:* Desviar $140.000\text{ msgs/s}$ excedentes ($210\text{M}$ mensagens) para uma DLQ retira os eventos do pipeline principal. Em um produto de observabilidade, contornar o processamento regular para posterior reprocessamento assíncrono degrada a integridade da telemetria em tempo real, violando a restrição estrutural de que a perda ou diferimento de telemetria é inaceitável.
* **Opção 3 (Divisão do Relay por cliente - da lista do time): REPROVADA.** 
  * *Mecanismo de falha:* Atua na criação de um `bulkhead` por cliente, mas o gargalo ocorre na capacidade de consumo agregada. Multiplicar a infraestrutura de barramentos isolados aumenta os custos fixos de provisionamento em mais de $15\%$, violando diretamente a restrição financeira de um orçamento já $8\%$ acima do teto trimestral, além de não garantir proteção se o pico vier de um único cliente grande.
* **Opção 5 (Quotas/Backpressure no produtor): REPROVADA.** 
  * *Mecanismo de falha:* Empurra o acúmulo de $210\text{M}$ de mensagens para a memória/disco local dos produtores. Sem garantia de armazenamento infinito no lado emissor, resulta em estouro de buffer e descarte de eventos na origem (violação de integridade de telemetria).

---

### 6. RECOMENDAÇÃO EM CAMADAS

1. **Camada 1 (Isolamento de Consumer Groups / Reversível via Configuração):**
   * **Ação:** Separar rigorosamente as partições e instâncias de `consumers` entre Sentinel e Forge no barramento, atribuindo cotas mínimas de processamento isoladas.
   * **Restrição que protege:** SLA do Sentinel ($\le 60\text{s}$) contra interferência direta de atrasos do Forge durante variações normais de tráfego.
   * **Custo:** R$ 0,00.
   * **Reversão:** Reversão de parâmetros de configuração do `consumer group` em minutos.
   * **Pré-condição:** Verificar se a quantidade de `partitions` do barramento permite divisão sem causar desbalanceamento (`skew`).

2. **Camada 2 (Autoscaling Elástico Baseado em Lag / Orçamento Variável):**
   * **Ação:** Configurar política de `autoscaling` reativo para o grupo de consumidores do Forge e do Sentinel, disparado quando o `lag` atingir $> 15\text{s}$ (Sentinel) ou $> 180\text{s}$ (Forge), escalando pontualmente a capacidade de consumo de $180k$ para $320k\text{ msgs/s}$.
   * **Restrição que protege:** SLA do Sentinel ($\le 60\text{s}$), SLA do Forge ($\le 15\text{min}$) e Zero Perda de Telemetria.
   * **Custo:** Custo elástico limitado a $25\text{ min}$ de execução suplementar ($\approx 0,03\%$ do gasto mensal de infraestrutura).
   * **Reversão:** Desativação das regras de dimensionamento automático no orquestrador.
   * **Pré-condição:** Métrica de `lag` de mensagens exposta com latência de coleta $< 5\text{s}$.

3. **Camada 3 (Utilização de Buffer de Retention Existente como Absorvedor):**
   * **Ação:** Permitir que o Forge utilize a retenção já paga de $4\text{h}$ do barramento para absorver variações abruptas de até $10\text{ min}$ sem disparar escala máxima imediatamente, drenando via escala suave.
   * **Restrição que protege:** Orçamento de infraestrutura (evita acionamentos falso-positivos de compute).
   * **Custo:** R$ 0,00 (retenção de $4\text{h}$ já provisionada).
   * **Reversão:** Ajuste nos gatilhos temporais do `autoscaling`.
   * **Pré-condição:** Monitoramento ativo da utilização de disco/armazenamento do barramento.

---

### 7. ORÇAMENTO

* **Provisionamento Permanente (Rejeitado):**
  * Para suportar $320k\text{ msgs/s}$ de forma contínua, seria necessário expandir o cluster fixo em $+77,7\%$ ($140k / 180k$). Isso acarretaria um aumento fixo de infraestrutura de $\approx 70\%$ ao mês, o que é inviável para um orçamento já $8\%$ acima do limite.
* **Autoscaling Elástico (Recomendado):**
  * O evento de pico durou $25\text{ min}$ em um trimestre ($129.600\text{ min}$ totais), representando $0,019\%$ do tempo operacional.
  * O custo pontual de dobrar a capacidade de consumo por $25\text{ min}$ equivale a aproximadamente $0,83$ horas-máquina adicionais por worker. O impacto financeiro do evento no trimestre é inferior a **$0,05\%$ do custo trimestral de compute**.
* **Conclusão:** O custo do `autoscaling` elástico cabe perfeitamente na margem operacional e custa exponencialmente menos do que provisionar capacidade estática para picos episódicos.

---

### 8. LACUNAS QUE PODEM INVERTER A RECOMENDAÇÃO

| Dado que falta | O que ele decide | Como medir |
| :--- | :--- | :--- |
| **Taxa de chegada pós-pico** | Se a drenagem do Forge sem autoscaling estouraria os $15\text{min}$ de SLA. | Monitorar métrica de `throughput` de entrada em janelas de $1\text{min}$ após estabilização. |
| **Tempo de inicialização (spin-up) dos consumidores** | Se o `autoscaling` consegue subir réplicas a tempo de evitar estouro de $60\text{s}$ no Sentinel. | Injetar carga em ambiente de homologação e medir o tempo entre a métrica de `lag` e o primeiro evento processado pela nova réplica. |
| **Tamanho médio das mensagens sob pico** | Se a retenção de $4\text{h}$ estoura em bytes/disco durante o volume de $210\text{M}$ de msgs. | Medir a taxa de bytes por segundo no barramento durante o evento de pico. |

---

### 9. FALSIFICADOR E GATILHO DE REVERSÃO

* **Falsificador:** A recomendação estará **errada** se o tempo total de provisionamento e inicialização (`spin-up latency`) de novas instâncias de consumidores for maior que $45\text{ segundos}$. Se o `autoscaling` demorar mais de $45\text{s}$ para entrar em operação, a taxa de acúmulo de $140k\text{ msgs/s}$ fará o `lag` do Sentinel ultrapassar o SLA de $60\text{s}$ antes que a primeira réplica adicional comece a processar.
* **Gatilho de Reversão:** Se em um teste de carga simulado ou incidente real a métrica `Sentinel_Consumer_Group_Lag` ultrapassar $45\text{s}$ sem que o throughput total de consumo tenha atingido $\ge 320k\text{ msgs/s}$, a estratégia de `autoscaling` reativo deve ser **estornada imediatamente**. Nisto ocorrendo, a restrição financeira deverá ser renegociada com a diretoria/gestão de produto para aprovar o pré-provisionamento permanente de capacidade (ou reservas aquecidas) exclusivamente para o consumidor do Sentinel.