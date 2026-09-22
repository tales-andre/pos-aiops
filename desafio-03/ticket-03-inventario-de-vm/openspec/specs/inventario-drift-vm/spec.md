# inventario-drift-vm Specification

## Purpose
Produzir, sob demanda e sem instalar nada no host auditado, um retrato confiável do estado real de
uma VM Linux do parque e o veredito de conformidade de cada regra do baseline declarado, em um
formato que uma máquina consome e um humano de plantão lê.

## Requirements

### Requirement: Invocação da ferramenta

A ferramenta SHALL ser invocada como comando de linha na máquina de quem opera, recebendo
endereço do host, usuário, caminho da chave privada e caminho do baseline, e MAY receber o formato
de saída (`json`, `markdown` ou `ambos`) e um diretório de saída. Quando o formato não for
informado, a ferramenta SHALL usar `json`. Quando o diretório de saída não for informado, a
ferramenta SHALL escrever o resultado na saída padrão.

#### Scenario: Invocação mínima válida

- **WHEN** a ferramenta é invocada com `--host`, `--usuario`, `--chave` e `--baseline` válidos
- **THEN** ela executa a coleta e emite o relatório em JSON na saída padrão

#### Scenario: Argumento obrigatório ausente

- **WHEN** a ferramenta é invocada sem `--baseline`
- **THEN** ela SHALL recusar a execução com mensagem de uso e terminar com código `4`, sem abrir
  nenhuma conexão SSH

#### Scenario: Baseline inexistente ou ilegível

- **WHEN** o caminho passado em `--baseline` não existe ou não é YAML válido
- **THEN** a ferramenta SHALL terminar com código `4` e mensagem que identifica o arquivo e o
  problema

#### Scenario: Formato inválido

- **WHEN** `--formato` recebe um valor fora de `json`, `markdown` e `ambos`
- **THEN** a ferramenta SHALL terminar com código `4` sem abrir conexão

### Requirement: Coleta estritamente somente-leitura

A ferramenta SHALL executar no host alvo apenas comandos de leitura. Ela MUST NOT instalar,
escrever, copiar ou remediar qualquer coisa do outro lado da conexão. Duas execuções consecutivas
contra o mesmo host, com o mesmo baseline e sem mudança no host, SHALL produzir relatórios JSON
idênticos, exceto pelo campo `host.coletado_em`.

#### Scenario: Duas execuções seguidas devolvem o mesmo retrato

- **WHEN** a ferramenta é executada duas vezes seguidas contra o mesmo host com o mesmo baseline
- **THEN** o diff entre os dois JSON SHALL conter exclusivamente a linha de `host.coletado_em`

#### Scenario: Nenhum artefato deixado no host

- **WHEN** uma execução termina, com sucesso ou com falha
- **THEN** o host auditado SHALL permanecer sem arquivo, pacote, serviço ou configuração criada
  pela ferramenta

### Requirement: Sigilo da chave privada

A chave privada SHALL circular apenas como **caminho de arquivo**. O conteúdo do material
criptográfico MUST NOT ser lido pelo processo, MUST NOT aparecer em qualquer das saídas, em log,
ou em mensagem de erro, nem quando a autenticação falha.

#### Scenario: Chave não aparece na saída de uma execução bem-sucedida

- **WHEN** uma execução conclui e emite JSON e Markdown
- **THEN** nenhuma das saídas SHALL conter o conteúdo da chave privada nem qualquer marcador de
  material de chave (por exemplo, `BEGIN OPENSSH PRIVATE KEY`)

#### Scenario: Chave não aparece quando a autenticação é recusada

- **WHEN** o host recusa a credencial apresentada
- **THEN** a mensagem de erro SHALL descrever a recusa sem reproduzir o conteúdo da chave, podendo
  citar apenas o caminho informado

### Requirement: Campos do inventário

Uma execução SHALL coletar os grupos abaixo, e cada campo que não puder ser coletado SHALL virar
`null` no inventário, nunca um valor presumido:

| Grupo | Campos |
|---|---|
| identificação | endereço usado na conexão, hostname reportado pelo host, instante da coleta em UTC |
| sistema operacional | distribuição, versão |
| kernel | versão em execução |
| serviços | nome, tipo e estado de cada unidade, distinguindo `service` de `socket` |
| swap | habilitado, e o tamanho quando houver |
| portas em escuta | número, endereço de bind e processo dono |
| chaves SSH autorizadas | quantidade e a identificação de cada uma |
| ssh | configuração **efetiva** de login de root |
| ntp | se o relógio está sincronizado e por qual mecanismo |

O tipo de unidade de serviço SHALL distinguir `service` de `socket`, porque o baseline proíbe duas
unidades que são `socket`. O endereço de bind de cada porta SHALL ser registrado, porque
"9100 em `0.0.0.0`" e "9100 em endereço interno" são conformidades diferentes. A configuração de
login de root SHALL ser a efetiva — a que vale em tempo de execução —, não a que está escrita no
arquivo de configuração.

#### Scenario: Campo coletável é preenchido

- **WHEN** o host responde ao comando de coleta do kernel
- **THEN** `inventario.kernel.versao` SHALL conter a versão em execução

#### Scenario: Campo não coletável vira null

- **WHEN** o comando de coleta de um campo falha, retorna vazio ou exige privilégio que o usuário
  da coleta não tem
- **THEN** o campo correspondente SHALL ser `null` no inventário e a execução SHALL prosseguir com
  as demais coletas

### Requirement: Conformidade com três vereditos

A ferramenta SHALL emitir uma entrada de conformidade por regra do baseline, contendo qual regra,
o que o baseline esperava, o que foi encontrado no host e o veredito. O veredito SHALL assumir
exatamente um de três valores:

| Veredito | Quando | Campo extra obrigatório |
|---|---|---|
| `conforme` | o encontrado satisfaz o esperado | — |
| `desvio` | o encontrado contraria o esperado | `severidade` |
| `nao_verificado` | o dado não pôde ser coletado | `motivo` |

A ferramenta MUST NOT reportar como `conforme` uma regra cujo dado não pôde ser coletado, nem
assumir o valor do baseline como encontrado.

#### Scenario: Regra satisfeita

- **WHEN** o valor encontrado satisfaz o esperado pelo baseline
- **THEN** a entrada SHALL trazer `veredito: "conforme"` e nenhum campo `severidade` ou `motivo`

#### Scenario: Regra contrariada

- **WHEN** o valor encontrado contraria o esperado pelo baseline
- **THEN** a entrada SHALL trazer `veredito: "desvio"` e o campo `severidade`

#### Scenario: Regra não verificável

- **WHEN** o dado necessário para avaliar a regra não pôde ser coletado
- **THEN** a entrada SHALL trazer `encontrado: null`, `veredito: "nao_verificado"` e um `motivo`
  que explique por que não foi possível verificar

### Requirement: Severidade determinada pelo baseline

A severidade de um desvio SHALL ser lida da seção `severidade` do arquivo de baseline. A
ferramenta MUST NOT embutir no código a severidade de nenhuma regra. Alterar a política de
severidade da casa SHALL ser possível editando somente o baseline.

#### Scenario: Severidade obedece ao baseline

- **WHEN** o baseline classifica `kernel.versao_minima` como `medio` e o host viola essa regra
- **THEN** a entrada de conformidade correspondente SHALL trazer `severidade: "medio"`

#### Scenario: Severidade reclassificada no baseline

- **WHEN** a mesma regra é movida no baseline de `medio` para `critico` e a execução se repete
- **THEN** o relatório SHALL trazer `severidade: "critico"` para aquela regra, sem alteração de
  código

### Requirement: Resumo quantitativo da execução

O relatório SHALL conter um resumo com a contagem de regras em cada um dos três vereditos e a
contagem de desvios por severidade, de modo que uma quantidade alta de `nao_verificado` seja
visível de imediato.

#### Scenario: Resumo reflete as entradas

- **WHEN** o relatório contém 4 regras conformes, 4 desvios e 1 não verificada
- **THEN** `resumo` SHALL trazer `{"conforme": 4, "desvio": 4, "nao_verificado": 1}` e a
  distribuição dos 4 desvios em `por_severidade`

### Requirement: Saída em JSON

A ferramenta SHALL renderizar o relatório em JSON com as chaves de topo `host`, `inventario`,
`conformidade` e `resumo`. O JSON SHALL ser válido e determinístico: a ordem das regras em
`conformidade` e a ordem das listas coletadas SHALL ser estável entre execuções.

#### Scenario: JSON consumível por máquina

- **WHEN** o formato `json` é solicitado
- **THEN** a saída SHALL ser um único documento JSON válido, sem texto avulso antes ou depois

### Requirement: Saída em Markdown

A ferramenta SHALL renderizar o mesmo relatório em Markdown, com cabeçalho identificando hostname,
endereço, instante da coleta e versão do baseline, e com os desvios, os não verificados e os
conformes em seções visualmente distintas. Os desvios SHALL aparecer ordenados por severidade,
do mais grave para o menos grave.

#### Scenario: Não verificado é visualmente distinto de conforme

- **WHEN** o relatório contém ao menos uma regra `nao_verificado`
- **THEN** o Markdown SHALL apresentá-la em seção própria, com o motivo, separada da seção de
  regras conformes

#### Scenario: Os dois formatos descrevem o mesmo estado

- **WHEN** a mesma execução é renderizada em JSON e em Markdown
- **THEN** o conjunto de regras e vereditos SHALL ser o mesmo nos dois formatos

### Requirement: Código de saída do processo

A ferramenta SHALL terminar com um código de saída que distingue os casos que exigem ação
diferente num pipeline:

| Código | Significado |
|---|---|
| `0` | host conforme — nenhum desvio |
| `1` | há desvio de severidade `critico` ou `alto` |
| `2` | há desvio apenas de severidade `medio` |
| `3` | host inalcançável, credencial recusada ou SSH fora do ar |
| `4` | erro de uso — baseline ausente, argumento inválido |

Regras `nao_verificado` MUST NOT, por si sós, alterar o código de saída: um host sem desvios e com
regras não verificadas termina com `0`.

#### Scenario: Host sem desvios

- **WHEN** nenhuma regra recebe veredito `desvio`
- **THEN** o processo SHALL terminar com código `0`

#### Scenario: Desvio grave presente

- **WHEN** há ao menos um desvio de severidade `critico` ou `alto`
- **THEN** o processo SHALL terminar com código `1`, mesmo havendo também desvios `medio`

#### Scenario: Apenas desvios médios

- **WHEN** todos os desvios têm severidade `medio`
- **THEN** o processo SHALL terminar com código `2`

### Requirement: Host inalcançável nunca é confundido com host conforme

Quando o host não responde, a credencial é recusada ou o serviço SSH está fora do ar, a ferramenta
SHALL terminar com código `3` e mensagem que diga o que aconteceu, em linguagem de operação. Ela
MUST NOT emitir relatório de conformidade nessa situação, MUST NOT terminar com `0`, e MUST NOT
imprimir stack trace cru.

#### Scenario: Endereço inexistente

- **WHEN** o endereço informado não resolve ou não aceita conexão
- **THEN** a ferramenta SHALL terminar com código `3` e mensagem que nomeia o host e a natureza da
  falha, sem stack trace

#### Scenario: Credencial recusada

- **WHEN** o host recusa a chave apresentada
- **THEN** a ferramenta SHALL terminar com código `3` e mensagem que indica recusa de credencial,
  sem stack trace e sem o conteúdo da chave

#### Scenario: Falha de conexão não vira relatório verde

- **WHEN** a conexão falha por qualquer dos motivos acima
- **THEN** nenhum relatório de conformidade SHALL ser emitido e o código de saída SHALL ser `3`
