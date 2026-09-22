# Proposal

## Why

O Roster é uma página mantida à mão desde quando o parque tinha trinta hosts, e envelheceu:
host que mudou de papel, agente instalado numa madrugada de incidente e nunca registrado, chave
SSH que entrou para desbloquear alguém e ficou. Quando perguntam quantas VMs estão fora do padrão
— ou quanto o parque custa a mais por estar assim — a resposta honesta hoje é "não sei", porque
**não existe retrato confiável do estado real dos hosts**. Esta mudança entrega a primeira fatia
disso: uma ferramenta de linha de comando que coleta o inventário de **um** host por SSH, compara
contra um baseline versionado e diz, regra a regra, o que está fora do padrão.

## What Changes

- Nova CLI `inventario`, que roda na máquina de quem opera e entra no host alvo por SSH com a
  chave informada. **Nada é instalado no host auditado** — a restrição que define o desenho é que
  não existe agente nas VMs do parque e ninguém vai instalar um só para isso.
- Coleta somente-leitura de 9 grupos de dados: identificação, SO, kernel, serviços (distinguindo
  `service` de `socket`), swap, portas em escuta (com endereço de bind), chaves SSH autorizadas,
  configuração **efetiva** de login de root e sincronismo de NTP.
- Modelo de conformidade com **três** vereditos — `conforme`, `desvio` e `nao_verificado` — em vez
  dos dois habituais. O terceiro existe porque a coleta entra com usuário comum e parte do que o
  baseline pede só se lê com privilégio; reportar isso como `conforme` seria falso negativo de
  auditoria.
- Severidade lida da seção `severidade` do `baseline.yaml`, nunca embutida no código: severidade é
  política da casa e precisa mudar sem que a ferramenta mude.
- Duas saídas sobre um único modelo em memória: JSON (para o Roster consumir quando existir) e
  Markdown (para o plantão ler no terminal).
- Código de saída que distingue "conforme" (`0`), "desvio grave" (`1`), "desvio médio" (`2`),
  "não consegui olhar" (`3`) e "erro de uso" (`4`). O `3` é separado de propósito: pipeline que
  trata *host inalcançável* como *host conforme* é pior que pipeline nenhum.

Não é mudança quebrante: não existe ferramenta anterior a substituir dentro deste repositório.

## Capabilities

### New Capabilities
- `inventario-drift-vm`: coleta somente-leitura do inventário de um host Linux por SSH,
  comparação contra um baseline declarado, classificação de conformidade em três vereditos com
  severidade vinda do baseline, renderização em JSON e Markdown, e contrato de código de saída.

### Modified Capabilities
<!-- Nenhuma. O projeto não tem specs publicadas em openspec/specs/ (inventário vazio,
     confirmado com `openspec list --specs`). -->

## Impact

- **Código novo**: `src/` na raiz do ticket — CLI, transporte SSH, catálogo de sondas, avaliador
  de conformidade, dois renderizadores.
- **Dependências**: Python 3.9+ e PyYAML no lado de quem opera; cliente `ssh` do sistema no PATH.
  Nenhuma dependência nova no host auditado.
- **Entradas existentes consumidas**: `baseline.yaml` na raiz do ticket (formato já definido,
  versão 1) e uma chave privada SSH, sempre por **caminho**, nunca por conteúdo.
- **Sistemas afetados**: nenhum, em escrita. A ferramenta abre uma sessão SSH e executa somente
  comandos de leitura; não escreve, não instala e não remedia.
- **Fora de escopo desta fatia**: varredura de parque inteiro, paralelismo, persistência/histórico,
  qualquer escrita no host auditado e a integração propriamente dita com o Roster (ele consumirá o
  JSON quando existir).
