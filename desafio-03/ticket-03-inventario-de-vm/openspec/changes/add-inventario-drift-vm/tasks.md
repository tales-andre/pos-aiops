# Tasks

## 1. Esqueleto e leitura do baseline

- [ ] 1.1 Criar a estrutura `src/inventario/` com `__init__.py`, `__main__.py` e o executável
      `src/inventario.py`, e verificar que `python3 src/inventario.py --help` imprime a
      invocação da spec (`--host`, `--usuario`, `--chave`, `--baseline`, `--formato`, `--saida`)
- [ ] 1.2 Implementar o carregamento do baseline com `yaml.safe_load`, expondo `esperado`,
      `severidade` e `versao`, e verificar que baseline ausente, ilegível ou YAML inválido termina
      com código `4` e mensagem que nomeia o arquivo
- [ ] 1.3 Implementar o índice invertido regra → severidade (design D8) e verificar com uma regra
      classificada e uma regra deliberadamente ausente da seção `severidade`
- [ ] 1.4 Implementar a validação de argumentos (formato fora do conjunto, chave inexistente,
      binário `ssh` ausente no PATH) e verificar que cada caso termina com `4` sem abrir conexão

## 2. Transporte SSH

- [ ] 2.1 Implementar a abertura da sessão mestre multiplexada (`ControlMaster`, socket em
      `mkdtemp` modo `0700`) com as opções fixas de D1 (`BatchMode=yes`, `ConnectTimeout=10`,
      `StrictHostKeyChecking=accept-new`, `IdentitiesOnly=yes`) e verificar conectando ao host de
      teste que uma única sessão atende várias execuções de comando
- [ ] 2.2 Implementar o encerramento da sessão e a remoção do diretório temporário em qualquer
      caminho de saída, e verificar que após a execução não resta socket de controle no disco
- [ ] 2.3 Implementar a classificação do erro de handshake (credencial recusada, conexão recusada,
      nome não resolve, timeout, chave de host mudada, genérico) e verificar que cada um termina
      com código `3` e mensagem sem stack trace
- [ ] 2.4 Implementar a execução de comando remoto sobre a sessão existente, devolvendo código,
      `stdout` e `stderr`, com `LC_ALL=C` e sem `SSH_AUTH_SOCK` herdado (design D10), e verificar
      com um comando que falha que a exceção não escapa

## 3. Catálogo de sondas e coleta

- [ ] 3.1 Definir o registro de sonda (identificador, comando remoto literal, parser, motivo de
      falha) e o laço do coletor que percorre o catálogo, e verificar que uma sonda que falha não
      interrompe as seguintes
- [ ] 3.2 Implementar as sondas de identificação, SO e kernel (`hostname`, `cat /etc/os-release`,
      `uname -r`) e verificar contra o host de teste que distribuição, versão e versão do kernel
      chegam preenchidas
- [ ] 3.3 Implementar a sonda de serviços com `systemctl list-units --type=service --type=socket`
      e verificar que a saída distingue `tipo: "service"` de `tipo: "socket"`
- [ ] 3.4 Implementar as sondas de swap (`cat /proc/swaps`) e NTP
      (`timedatectl show -p NTPSynchronized -p NTP`) e verificar que swap traz `habilitado` e
      `tamanho`, e NTP traz `sincronizado` e `mecanismo`
- [ ] 3.5 Implementar a sonda de portas (`ss -H -ltnp`) com extração de porta, endereço de bind e
      processo, e verificar que uma porta sem processo visível vem com processo `null` em vez de
      falhar
- [ ] 3.6 Implementar a sonda de chaves SSH autorizadas e verificar que devolve a identificação
      (comentário) de cada chave e **nunca** o material da chave
- [ ] 3.7 Implementar a sonda de configuração efetiva de SSH (`sshd -T`) e verificar contra o host
      de teste, com usuário sem privilégio, que ela devolve `None` com o motivo do catálogo em vez
      de exceção
- [ ] 3.8 Implementar a ordenação estável de todas as listas do inventário (design D9) e verificar
      que duas coletas seguidas produzem listas na mesma ordem

## 4. Avaliação de conformidade

- [ ] 4.1 Implementar a comparação de versão por tupla numérica (design D5) e verificar os casos
      `6.6.87.2-microsoft-standard-WSL2` ≥ `6.5`, `5.15` < `6.5` e uma versão não numérica que
      vira `nao_verificado`
- [ ] 4.2 Implementar a classificação do endereço de bind em `publica`/`interna`/`local`
      (design D6) e verificar `0.0.0.0`, `*`, `::`, `127.0.0.1`, `10.255.255.254` e `[::]`
- [ ] 4.3 Implementar as regras de SO, kernel e NTP e verificar cada uma contra o host de teste
- [ ] 4.4 Implementar as regras de serviços (`ativos` e `proibidos`) e verificar que serviço
      ausente e serviço proibido ativo produzem `desvio` com a severidade do baseline
- [ ] 4.5 Implementar as regras de porta (`publicas_permitidas` e `somente_rede_interna`, com a
      semântica de escopo de D7) e verificar que porta em escuta fora da lista de públicas gera
      desvio e que a ausência de 9100 não gera desvio na regra de escopo
- [ ] 4.6 Implementar as regras de swap e de chaves SSH e verificar que swap ativo e chave de
      emissor diferente do declarado produzem desvio `critico`
- [ ] 4.7 Implementar a regra `ssh.login_de_root` e verificar que dado ausente produz
      `veredito: "nao_verificado"` com `motivo`, nunca `conforme`
- [ ] 4.8 Implementar o resumo (contagem dos três vereditos e distribuição por severidade) e
      verificar que a soma das três contagens é igual ao número de regras avaliadas

## 5. Renderizadores

- [ ] 5.1 Implementar o renderizador JSON sobre o modelo em memória, com chaves de topo `host`,
      `inventario`, `conformidade` e `resumo`, e verificar que a saída é um único documento JSON
      válido e determinístico
- [ ] 5.2 Implementar o renderizador Markdown com cabeçalho, seção de desvios ordenada por
      severidade, seção própria de não verificados com motivo, e linha de conformes, e verificar
      que um relatório com os três vereditos mostra os três em lugares distintos
- [ ] 5.3 Implementar `--formato ambos` e `--saida <dir>` gravando os dois arquivos, e verificar
      que sem `--saida` o relatório sai na saída padrão

## 6. Código de saída e sigilo da chave

- [ ] 6.1 Implementar o cálculo do código de saída (`0`/`1`/`2` conforme a severidade dos desvios)
      e verificar que `nao_verificado` sozinho não promove o código acima de `0`
- [ ] 6.2 Implementar a camada de saneamento de mensagens (design D10) e verificar que nenhum
      caminho de erro imprime material de chave

## 7. Validação contra o host real e evidência

- [ ] 7.1 Executar contra o host SSH real e gravar em `execucoes/` a saída JSON e a saída Markdown
      de uma execução, com o código de retorno registrado (critérios de aceite 2 e 3)
- [ ] 7.2 Produzir a evidência do critério 1 (host sem desvio, código `0`) e do código `2` (apenas
      desvios médios) executando contra baselines cujo padrão declarado o host satisfaz, e
      registrar os códigos de retorno
- [ ] 7.3 Produzir a evidência do critério 4 com endereço inalcançável e com chave recusada, e
      verificar código `3`, mensagem em linguagem de operação e ausência de stack trace
- [ ] 7.4 Produzir a evidência do critério 5 com duas execuções consecutivas e o `diff` entre os
      dois JSON, mostrando que só `host.coletado_em` mudou
- [ ] 7.5 Produzir a evidência do critério 6 varrendo todas as saídas e mensagens de erro à
      procura do conteúdo da chave privada, e registrar o resultado da varredura
- [ ] 7.6 Registrar em `curadoria.md` na raiz onde a spec precisou ser corrigida ou foi ambígua,
      o que foi decidido e por quê
