# Design

## Context

A motivação está em `proposal.md — Why`; os requisitos observáveis estão em
`specs/inventario-drift-vm/spec.md`. Este documento cobre só o **como**.

Quatro decisões já estavam registradas antes de existir código, em `specs/02-decisoes.md` da raiz
do ticket (D1 a D4). Elas são entrada deste design, não saída: o que segue as adota e detalha o
que elas deixam em aberto.

Restrições que moldam a arquitetura:

- **Não existe agente no host auditado**, e ninguém vai instalar um. O que existe em toda VM é
  acesso por chave. A ferramenta entra por SSH com o que já está lá e não deixa nada para trás.
- **A coleta entra com usuário comum.** Parte do que o baseline pede (a configuração efetiva do
  `sshd`) só se lê com privilégio. Isso não é exceção: é o caminho normal.
- **O baseline é dado, não código.** A lista de regras e a política de severidade vêm do YAML.

## Goals / Non-Goals

**Goals:**

- Uma única sessão SSH por execução, para não pagar nove handshakes no host auditado.
- Falha de coleta isolada por sonda: uma sonda que falha não derruba as outras oito.
- Um modelo de dados em memória e dois renderizadores sobre ele, para que JSON e Markdown não
  possam divergir.
- O material da chave privada nunca entra no espaço de endereçamento do processo.
- Acrescentar um dado ao inventário deve ser acrescentar uma entrada no catálogo, não mexer no
  fluxo de coleta.

**Non-Goals:**

- Paralelismo entre sondas. O ganho é irrelevante numa sessão multiplexada e o custo é
  não-determinismo na ordem de saída, que brigaria com o requisito de execução repetida.
- Abstrair o transporte para trocar SSH por outra coisa depois. Não há segundo transporte à vista;
  a indireção seria custo sem comprador.
- Cache de resultado entre execuções. Um retrato precisa ser tirado na hora.

## Decisions

### D1 (herdada) — Cliente `ssh` do sistema como subprocesso, com sessão multiplexada

Adotada como está em `specs/02-decisoes.md`. Detalhamento deste design:

- A sessão é aberta uma vez com `-M -N -f` sobre um socket de controle em diretório temporário
  criado com `mkdtemp` e modo `0700`, removido no encerramento. As sondas seguintes reutilizam a
  sessão com `-o ControlPath=<socket>`.
- Opções fixas, exatamente as de D1: `BatchMode=yes`, `ConnectTimeout=10`,
  `StrictHostKeyChecking=accept-new`, `IdentitiesOnly=yes`. Acrescento uma só, que D1 não cita:
  `ControlPersist` com o tempo de vida da sessão mestre, sem o qual a multiplexação não se
  sustenta entre invocações do subprocesso.
- **Distinguir "não alcancei" de "alcancei e o comando falhou"** é o ponto que decide entre código
  de saída `3` e veredito `nao_verificado`. Feito no *handshake*: se a abertura da sessão mestre
  falha, é `3`, e o processo termina ali. Depois que a sessão está de pé, nenhuma falha de comando
  individual pode voltar a ser `3` — vira `nao_verificado`.
- O diagnóstico do handshake é classificado por reconhecimento de texto no `stderr` do `ssh`
  (`Permission denied`/`publickey` → credencial recusada; `Connection refused` → SSH fora do ar;
  `Name or service not known` → endereço não resolve; `Connection timed out` → host inalcançável;
  `HOST KEY ... CHANGED` → chave do host mudou). Parsing por texto é frágil, e é o preço de D1;
  há um caso de borda genérico para o que não casar, que reporta a causa bruta do `ssh` — já
  saneada — em vez de inventar uma explicação.

### D2 (herdada) — Cada sonda falha sozinha

Adotada. Detalhamento: o resultado de uma sonda é um registro com `valor` e `motivo`. Ou há valor
e `motivo` é vazio, ou o valor é `None` e o `motivo` é uma frase em linguagem de operação. Não
existe terceira forma. O avaliador de conformidade recebe esse registro, e é a presença de
`motivo` — não uma checagem de `None` espalhada — que produz `nao_verificado`. Assim o tratamento
de falha existe em um lugar só.

O `motivo` é escrito no catálogo, por sonda, e não derivado do `stderr` do comando. Razão: `stderr`
de comando remoto é ruído para quem lê o relatório às três da manhã, e pode carregar conteúdo
imprevisível. Para `sshd -T` o motivo é literalmente
"exige privilegio que o usuario da coleta nao tem", porque essa é a causa real e conhecida.

### D3 (herdada) — Python 3, biblioteca padrão mais PyYAML

Adotada. `yaml.safe_load` para o baseline — nunca `yaml.load` —, porque o baseline é um arquivo
que alguém edita à mão e um dia vai vir de um repositório que não é o nosso.

### D4 (herdada) — Catálogo declarativo de sondas

Adotada. Cada entrada do catálogo carrega: identificador, **o comando remoto literal**, a função
de parsing e o motivo a usar quando falhar. O comando fica à vista na própria entrada, que é o que
permite a alguém auditar em trinta segundos o que a ferramenta executou na máquina alheia.

Comandos escolhidos, e por que estes:

| Sonda | Comando remoto | Por quê |
|---|---|---|
| `hostname` | `hostname` | presente em toda distro; `hostnamectl` depende de systemd |
| `os_release` | `cat /etc/os-release` | padrão freedesktop, não exige privilégio |
| `kernel` | `uname -r` | POSIX |
| `servicos` | `systemctl list-units --type=service --type=socket --all --plain --no-legend --no-pager` | é a única fonte que **distingue `service` de `socket`**, exigência explícita da spec |
| `swap` | `cat /proc/swaps` | leitura de `procfs`, sem privilégio; `swapon --show` pede mais |
| `portas` | `ss -H -ltnp` | traz porta, endereço de bind e processo; sem privilégio o campo de processo vem vazio para processos alheios, e vazio é honesto |
| `chaves_ssh` | `cat ~/.ssh/authorized_keys` | as chaves do usuário da coleta; as de outros usuários exigiriam privilégio |
| `ssh_login_root` | `sshd -T` | a configuração **efetiva**, não a escrita. Falha esperada sem privilégio |
| `ntp` | `timedatectl show -p NTPSynchronized -p NTP` | resposta estável e parseável; `timedatectl status` é texto para humano |

Nenhum comando escreve, e nenhum usa `sudo`. Pedir `sudo` transformaria uma ferramenta de leitura
numa que exige privilégio no parque inteiro, o que é caro e desnecessário para nove dados dos
quais oito se leem sem ele.

### D5 (nova) — Comparação de versão por tupla numérica, não por string

`5.15` contra `6.5` não é comparação de string, e `6.6.87.2-microsoft-standard-WSL2` tem sufixo
que não é número. A comparação extrai os componentes numéricos iniciais, compara como tupla de
inteiros e descarta o sufixo. Alternativa descartada: `packaging.version`, que resolveria melhor
e acrescentaria uma dependência que D3 não autorizou. Limitação aceita: versão sem componente
numérico inicial não é comparável, e vira `nao_verificado` em vez de falso veredito.

### D6 (nova) — Classificação do endereço de bind em três faixas

O baseline separa `publicas_permitidas` de `somente_rede_interna`, o que só faz sentido se o
endereço de bind for classificado. Adotado:

| Faixa | Endereços | Significado |
|---|---|---|
| `publica` | `0.0.0.0`, `::`, `*` e qualquer endereço roteável globalmente | exposta para fora |
| `interna` | RFC1918 (`10/8`, `172.16/12`, `192.168/16`) e link-local | alcançável só de dentro |
| `local` | `127/8`, `::1` | não sai da máquina |

Consequências: uma porta em `127.0.0.1` não viola `publicas_permitidas`, porque não está pública;
uma porta em curinga viola, porque está. Alternativa descartada: tratar todo bind como público, o
que é simples e produz uma enxurrada de falsos desvios em qualquer host com serviço local.

### D7 (nova) — Regra de escopo avalia quem está presente, não quem falta

`portas_em_escuta.somente_rede_interna: [9100]` é uma restrição de **escopo** de uma porta, e não
uma exigência de que ela exista. Se 9100 não está em escuta, a regra não tem o que reprovar e sai
`conforme`; a ausência do serviço já é capturada por `servicos.ativos`, que é onde ela pertence.
Alternativa descartada: reprovar a ausência aqui também, o que contaria o mesmo problema duas
vezes, em duas severidades diferentes, e inflaria o resumo.

### D8 (nova) — Severidade resolvida por índice invertido do baseline

A seção `severidade` do baseline é um mapa de severidade para lista de regras. O avaliador monta
o índice invertido (regra → severidade) ao carregar. Uma regra que o baseline não classificar
recebe `null` na severidade e **não** promove o código de saída para `1`; ela conta como desvio,
aparece no relatório, e o fato de não ter severidade fica visível. Alternativa descartada: adotar
um padrão embutido, que reintroduziria no código a política que a spec manda tirar dele.

### D9 (nova) — Ordenação estável em tudo que é lista

O requisito de execução repetida se quebra por qualquer ordem que dependa de iteração de
dicionário ou de ordem de chegada. Adotado: regras de conformidade emitidas na ordem fixa do
catálogo de regras; serviços ordenados por nome; portas por `(porta, bind)`; chaves por
identificação; `json.dumps` com `sort_keys=True`. A única fonte de variação que sobra é o próprio
host — uma porta efêmera que subiu entre as duas execuções —, e essa é variação real, que a
ferramenta deve reportar em vez de esconder.

### D10 (nova) — Saneamento de mensagem como camada, não como cuidado

O invariante I2 é fácil de sustentar no caminho feliz e fácil de furar num `except` esquecido.
Adotado: toda escrita em `stderr` passa por uma função única que remove qualquer bloco PEM
(`-----BEGIN ... -----END`) e qualquer linha que se pareça com material de chave. Não é substituto
de nunca ler a chave — é a segunda camada, para o dia em que alguém acrescentar um `print` sem
pensar. Além dela, o processo filho herda um ambiente onde `SSH_AUTH_SOCK` é removido, coerente
com `IdentitiesOnly=yes`: sem isso, o agente do operador pode autenticar com outra credencial e o
resultado deixa de ser reproduzível.

## Risks / Trade-offs

- **Dependência de binário externo (`ssh`), ausente em imagem mínima** → aceito por D1; a
  ferramenta detecta a ausência no início e termina com código `4` (erro de uso), não `3`, porque
  o problema é da máquina de quem opera, não do host alvo.
- **Parsing de erro do `ssh` é por texto e quebra com mudança de versão ou locale** → o processo
  filho roda com `LC_ALL=C` para fixar o idioma das mensagens, e há caso de borda genérico para o
  que não casar.
- **Host com porta efêmera pode fazer duas execuções diferirem** → não é defeito da ferramenta e
  não será mascarado; o critério de aceite é verificado com duas execuções consecutivas, e
  qualquer diferença além de `coletado_em` é diferença real do host, a ser registrada como tal.
- **Um host onde quase tudo falhou devolve relatório de aparência normal** → risco herdado de D2;
  mitigado pelo resumo, que conta os três vereditos, e pela seção própria de `nao_verificado` no
  Markdown.
- **`ss` pode não existir em distro antiga (só `netstat`)** → a sonda de portas falha e vira
  `nao_verificado` nas duas regras de porta, com motivo explícito. Não há fallback silencioso:
  cair para `netstat` sem dizer mudaria o que foi executado no host alheio sem registro.
- **Classificação de faixa de IP (D6) é heurística por prefixo, não consulta de rota** → um parque
  com endereçamento público em rede fechada seria classificado errado. Aceito nesta fatia; o
  caminho correto seria o baseline declarar os blocos internos, e isso é mudança de baseline,
  fora do escopo.

## Migration Plan

Não há migração: a ferramenta é nova, não substitui código existente e não escreve em lugar
nenhum. A adoção é copiar `src/` e invocar. O rollback é parar de invocar.
