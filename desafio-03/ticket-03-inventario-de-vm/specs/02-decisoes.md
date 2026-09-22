# Decisões técnicas

As decisões que a ferramenta não carrega sozinha, registradas antes da implementação. Cada uma
traz o que foi descartado e o que se perde com a escolha — quem pegar este código daqui a um ano
vai perguntar por quê, e o commit não responde.

---

## D1 — Como a ferramenta conversa com o host remoto

**Escolhido:** o cliente `ssh` do sistema, invocado como subprocesso, com uma única sessão
multiplexada (`ControlMaster`) reaproveitada por todas as coletas.

**Descartado — biblioteca SSH em processo (Paramiko/asyncssh).** Traz dependência nativa, uma
segunda implementação de SSH para manter, e — decisivo — tende a exigir a chave privada carregada
em memória ou desembrulhada pelo próprio código. O invariante I2 fica mais fácil de sustentar
quando o material da chave nunca entra no processo: passamos o **caminho** para o `ssh`, e o
manuseio fica com quem já faz isso bem.

**Descartado — uma conexão SSH por comando coletado.** Simples de escrever e insuportável de usar:
nove handshakes por host, cada um com custo de rede e de CPU do lado auditado. Com
`ControlMaster`, o custo do handshake é pago uma vez.

**O que se perde:** dependência de um binário externo, ausente em imagem mínima e diferente no
Windows fora do WSL. E o parsing de erro do `ssh` é por texto, o que é mais frágil que uma
exceção tipada.

**Configuração adotada e por quê:**

| Opção | Motivo |
|---|---|
| `BatchMode=yes` | nunca pedir senha interativamente; falhar rápido é o comportamento correto num coletor |
| `ConnectTimeout=10` | host inalcançável precisa virar código de saída, não pendurar o pipeline |
| `StrictHostKeyChecking=accept-new` | aceitar host novo sem exigir intervenção, mas **recusar** se a chave mudou — chave que muda é sinal de coisa ruim, não de conveniência |
| `IdentitiesOnly=yes` | usar só a chave informada; sem isso o agente SSH do operador pode autenticar com outra credencial e o resultado deixa de ser reproduzível |

---

## D2 — O que acontece quando um dado não pode ser coletado

**Escolhido:** cada coleta é independente e falha sozinha. Um comando que retorna código diferente
de zero, ou saída vazia onde se esperava conteúdo, produz `null` no inventário e
`veredito: nao_verificado` com `motivo` na conformidade. A execução segue.

**Descartado — abortar a execução inteira.** Joga fora oito coletas boas por causa da nona. Pior:
o caso mais comum de falha é justamente o esperado — a configuração efetiva do SSH exige
privilégio que o usuário da coleta não tem. Abortar transformaria o caso normal em erro.

**Descartado — assumir o valor do baseline quando não dá para verificar.** Produz falso negativo
de auditoria, que é o pior defeito possível numa ferramenta de compliance: o relatório fica verde
e a auditoria passa sem que ninguém tenha olhado.

**O que se perde:** um host onde quase tudo falhou ainda assim devolve um relatório de aparência
normal, cheio de `nao_verificado`. Mitigação: o resumo conta os três vereditos, então uma contagem
alta de `nao_verificado` é visível de imediato nos dois formatos.

**Corolário sobre `ssh.login_de_root`:** o baseline pede a configuração **efetiva**, não a escrita
no arquivo. `sshd_config` tem `Include` e blocos `Match`, e a precedência é por primeira ocorrência
— ler com `grep` dá a resposta errada com frequência. A configuração efetiva se obtém com
`sshd -T`, que exige privilégio. Sem privilégio, a regra vira `nao_verificado`, e é exatamente o
comportamento correto: melhor não saber e dizer que não sabe.

---

## D3 — Em que linguagem, e por quê

**Escolhido:** Python 3, biblioteca padrão mais PyYAML.

**Descartado — shell script.** A ferramenta é majoritariamente orquestração de comandos remotos, o
que favorece shell. Mas ela também precisa montar JSON aninhado com três tipos de veredito,
comparar versões semanticamente (`5.15` contra `6.5` não é comparação de string) e renderizar dois
formatos a partir de um modelo. Em shell isso vira `jq`, `sort -V` e `printf` colados com fita —
frágil de testar e difícil de ler depois.

**Descartado — Go.** Entrega binário único sem dependência no lado de quem opera, o que é
genuinamente melhor para distribuição. Descartado porque quem vai manter isso é um time de
infraestrutura: Python já está em toda máquina do parque, é a linguagem dos desafios da casa, e o
custo de alguém do plantão abrir e ajustar uma regra é muito menor. Distribuição é problema de
hoje; manutenção é problema de todo dia.

**O que se perde:** duas dependências no lado de quem opera (Python 3.9+ e PyYAML) e nenhum binário
único. Se a distribuição virar um problema real, o caminho é empacotar com `pipx` ou `shiv`, não
reescrever.

---

## D4 — Como a coleta é organizada por dentro

**Escolhido:** um catálogo declarativo de sondas. Cada sonda é um registro com nome, comando
remoto e função de parsing; o coletor apenas percorre o catálogo. Acrescentar um dado ao
inventário é acrescentar uma entrada, não mexer no fluxo.

**Descartado — uma função por dado, chamadas em sequência no corpo principal.** Mais direto de
escrever e pior de manter: o tratamento de falha se repete em nove lugares, e cada repetição é uma
chance de alguém esquecer o `nao_verificado`.

**Descartado — descoberta automática por introspecção de módulo.** Elegante e opaca. Num coletor
de auditoria, saber exatamente o que foi executado no host alheio vale mais que economia de
digitação.

**O que se perde:** uma camada de indireção entre ler o código e saber qual comando roda. Mitigado
por manter o comando literal dentro da própria entrada do catálogo, à vista.
