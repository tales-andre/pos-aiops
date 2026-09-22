# Curadoria da implementação

Registro do que a especificação não resolvia, do que resolvi sozinho, e do que errei de
primeira. A regra do ticket é que as decisões de `specs/02-decisoes.md` não são
negociáveis: nenhuma delas foi alterada. O que está aqui é o que a spec **não dizia** e
o que ela dizia de forma que não fechava.

Nenhum item abaixo mudou comportamento que a spec descreve. Onde a spec era explícita,
segui a spec mesmo quando eu preferiria outra coisa — e os casos em que preferiria estão
marcados como **recomendação**, para uma próxima versão do documento, não como mudança.

---

## Parte 1 — Onde a spec precisou ser corrigida ou completada

### C1 — O executável não podia ter o nome que eu mesmo planejei

Não é falha da spec, é minha: no `tasks.md` escrevi "criar `src/inventario.py` ao lado do
pacote `src/inventario/`". Isso não existe em Python — um módulo e um pacote com o mesmo
nome no mesmo diretório colidem no `import`. Corrigido para o executável ficar na raiz do
ticket (`./inventario`), que aliás casa melhor com a invocação que a spec mostra
(`inventario --host ...`, sem caminho). O `tasks.md` foi corrigido com a nota.

### C2 — `--formato ambos` sem `--saida` não tinha comportamento definido

A spec declara `[--saida <dir>]` como opcional e exige que o JSON seja "um único documento
JSON válido, sem texto avulso antes ou depois". Os dois juntos não fecham: com
`--formato ambos` e sem diretório, os dois relatórios teriam de sair pela mesma saída
padrão, e o Markdown viraria exatamente o "texto avulso" que quebra o JSON para o Roster.

**Decidi:** `--formato ambos` exige `--saida`; sem ele, erro de uso e código `4`, com
mensagem que diz o porquê. Sem `--saida`, `json` e `markdown` saem na saída padrão
normalmente.

**Recomendação:** a spec deveria dizer isso explicitamente, ou definir um separador
que o Roster saiba ignorar. Escolhi recusar em vez de inventar um separador, porque
separador inventado é contrato implícito.

### C3 — "somente_rede_interna" é restrição de escopo ou exigência de presença?

`baseline.yaml` declara `somente_rede_interna: [9100]`. O exemplo de Markdown da spec
mostra o desvio como `9100 na rede interna` / `9100 em 0.0.0.0` — ou seja, a porta
**existe** e está no lugar errado. A spec não diz o que acontece quando 9100 **não está
em escuta**, que é o caso do host de teste.

**Decidi (design D7):** é restrição de escopo. Porta ausente não tem o que reprovar aqui,
e sai `conforme`. A ausência do serviço já é capturada por `servicos.ativos`, que lista
`node_exporter`. Reprovar nos dois lugares contaria o mesmo problema duas vezes, em duas
severidades diferentes, e inflaria o resumo.

**O que se perde, e é real:** num parque onde alguém tire `node_exporter` de
`servicos.ativos` mas mantenha `9100` em `somente_rede_interna`, a ausência do exporter
passa despercebida. As duas regras ficaram acopladas por uma suposição que o baseline não
declara.

**Recomendação:** o baseline deveria separar `porta_obrigatoria` de `escopo_da_porta`, ou
a spec dizer qual das duas leituras vale.

### C4 — A spec exige distinguir "aberta para o mundo" de "só no endereço interno", mas não define a fronteira

Esta é a lacuna mais consequente. A spec diz, na tabela do inventário, que
`"9100 aberta para o mundo" e "9100 só no endereço interno" são conformidades diferentes`,
e o baseline separa `publicas_permitidas` de `somente_rede_interna`. Nenhum dos dois diz
o que faz um endereço ser público.

**Decidi (design D6):** três faixas — `publica` (curinga `0.0.0.0`/`::`/`*` e qualquer
endereço roteável globalmente), `interna` (RFC1918 e link-local) e `local` (loopback).

**Por que importa tanto:** sem essa classificação, a leitura ingênua seria "toda porta em
escuta é pública". No host de teste isso produziria seis desvios críticos falsos, todos de
portas em `127.0.0.1` que não saem da máquina. Com a classificação, sobra um desvio
verdadeiro (`4369 em *`). A diferença entre um relatório útil e um relatório que ninguém
lê estava inteira nesta decisão que a spec não tomou.

**Limitação assumida:** é heurística por prefixo, não consulta de tabela de rotas. Um
parque com endereçamento público em rede fechada seria classificado errado. O caminho
correto é o baseline declarar os blocos internos da casa — mudança de baseline, fora
desta fatia.

### C5 — A versão do baseline está no Markdown e não existe no JSON

O exemplo de Markdown da spec traz `Coletado em ... · baseline v1`. O exemplo de JSON tem
quatro chaves de topo (`host`, `inventario`, `conformidade`, `resumo`) e nenhuma delas
carrega a versão do baseline.

**Não mudei o JSON.** Segui o exemplo da spec e passei a versão ao renderizador de
Markdown como argumento.

**Recomendação, e acho que é um defeito de verdade:** o Roster vai consumir o JSON para
saber quantas VMs estão fora do padrão. Sem a versão do baseline no JSON, ele não
consegue dizer *de qual padrão*. Um veredito guardado hoje e relido daqui a seis meses
não é interpretável. Sugiro acrescentar `"baseline": {"versao": ...}` ao topo do JSON na
próxima versão da spec.

### C6 — Não há código de saída para "a ferramenta quebrou"

A tabela cobre `0` a `4`: conforme, desvio grave, desvio médio, host inalcançável, erro de
uso. Não há linha para um defeito da própria ferramenta.

**Decidi:** exceção inesperada vira mensagem saneada, sem stack trace, e código `4`.
Raciocínio pela negativa: `0` é a mentira perigosa (o pipeline segue achando que está tudo
bem); `3` mentiria sobre o host, culpando uma máquina que talvez esteja íntegra; `4` ao
menos diz "não confie nesta execução" e é o balde menos errado. Está errado assim mesmo —
a spec deveria ter um `5`.

### C7 — `ssh.login_de_root` é booleano na spec, mas `sshd -T` responde quatro coisas

`permitrootlogin` tem quatro valores efetivos: `yes`, `no`, `prohibit-password` e
`forced-commands-only`. A spec modela o campo como booleano.

**Decidi:** tudo que não é `no` vira `true`. É o lado seguro — `prohibit-password` é login
de root, com restrição, mas é.

**O que se perde:** "root entra com senha" e "root entra só com chave" viram o mesmo
desvio, com a mesma severidade, e são problemas de gravidade muito diferente numa
madrugada. **Recomendação:** o campo deveria guardar o valor efetivo como texto, e a
regra decidir sobre ele.

### C8 — O exemplo de Markdown não tem resumo, mas a decisão D2 exige um

O exemplo de Markdown da spec vai direto de "Desvios" para "Não verificado" e "Conforme".
Mas `02-decisoes.md`, em D2, diz que a mitigação para "host onde quase tudo falhou" é que
`o resumo conta os três vereditos, então uma contagem alta de nao_verificado é visível de
imediato nos dois formatos`. O exemplo e a justificativa se contradizem.

**Decidi:** fiquei com D2 e acrescentei ao Markdown uma linha de resumo logo abaixo do
cabeçalho. O exemplo da spec é ilustrativo; a decisão é normativa, e era a decisão que
tinha um "porquê" escrito.

### C9 — `ntp.mecanismo` não tem sonda própria

A spec pede, no inventário de NTP, "se o relógio está sincronizado **e por qual
mecanismo**". `timedatectl show -p NTPSynchronized -p NTP` responde a primeira metade e
não a segunda.

**Decidi:** derivar o mecanismo da lista de serviços **já coletada**, procurando qual dos
daemons de tempo conhecidos está `active`. Não gasta um décimo comando na máquina alheia,
e num coletor de auditoria cada comando a menos no host de outra pessoa é uma virtude.

**O que se perde:** se a sonda de serviços falhar, o mecanismo vem `null` mesmo com o
sincronismo conhecido, e há um acoplamento entre duas sondas que o catálogo declarativo
de D4 preferiria não ter. Está comentado no código, no lugar onde a derivação acontece.

### C10 — D1 não menciona `ControlPersist`, e sem ele a multiplexação não funciona

D1 fixa quatro opções (`BatchMode`, `ConnectTimeout`, `StrictHostKeyChecking`,
`IdentitiesOnly`) e manda usar `ControlMaster`. Acrescentei `ControlPersist`, que D1 não
cita: sem ele a sessão mestre não sobrevive entre as invocações de subprocesso e cada
sonda voltaria a pagar o handshake — exatamente o que D1 quer evitar. É complemento
necessário de D1, não alternativa a ela, e está registrado no `design.md`.

### C11 — Regra que o baseline não classifica

O `baseline.yaml` classifica as onze regras, mas nada garante isso num baseline futuro.
A spec não diz o que fazer com um desvio sem severidade.

**Decidi (design D8):** severidade `null`, a regra conta como desvio e aparece no
relatório, e **não** promove o código de saída a `1` — cai em `2`. Alternativa descartada:
adotar um padrão embutido no código, que reintroduziria justamente a política que a spec
manda tirar de lá.

---

## Parte 2 — O que entendi diferente, e onde errei

### E1 — O exemplo da spec puxa para "uma entrada por serviço"; o texto normativo diz outra coisa

O exemplo de Markdown da spec mostra a linha `alto | servicos.ativos | chrony ativo |
ausente`, no singular, como se cada serviço faltante virasse uma linha própria. Só que o
texto normativo diz "uma entrada por regra do baseline", e `servicos.ativos` é **uma**
regra, com quatro serviços dentro. Os dois não podem valer ao mesmo tempo, e o exemplo é
que está simplificado — se cada serviço virasse entrada, `resumo.desvio` contaria quatro
onde o baseline tem uma regra, e o total de entradas deixaria de bater com o total de
regras.

Ficou: uma entrada, com `esperado` sendo a lista inteira e `encontrado` sendo o estado de
cada um (`ssh: active, containerd: active, node_exporter: ausente, chrony: ausente`). É
mais verboso na tabela e é o que o Roster consegue consumir sem adivinhar.

### E2 — A evidência do critério 5 passou sem provar nada, e eu quase aceitei

Primeira rodada de evidências: as duas execuções consecutivas caíram no mesmo segundo, o
`diff` saiu **completamente vazio**, e a tabela de resumo marcou o critério como atendido.

Parecia ótimo e não provava nada. O critério é "dois JSON consecutivos são idênticos
**exceto por** `host.coletado_em`" — um diff vazio mostra que nada mudou, não que só o
instante mudou. Se `coletado_em` estivesse quebrado e sempre devolvesse o mesmo valor, o
teste passaria igual.

Corrigido com dois segundos entre as execuções. A evidência agora mostra as duas linhas do
diff, as duas em `coletado_em`, e o script conta as linhas alteradas e quantas delas são
do campo de tempo — se algum dia divergirem, o arquivo diz isso em vez de dizer "ok".

### E3 — A varredura do critério 6 acusou vazamento em si mesma

A busca por `PRIVATE KEY` varria `execucoes/` inteiro, e o próprio script gerador contém
essa string — porque é ele quem faz a busca. O relatório saiu dizendo "encontrado
'PRIVATE KEY' — inspecionar", apontando para as linhas do próprio grep.

Falso positivo, mas do tipo que corrói confiança num relatório de auditoria: quem lê não
sabe distinguir. Corrigido restringindo o escopo aos relatórios gerados e ao código-fonte,
com o escopo declarado no próprio arquivo de evidência.

### E4 — Não dá para provar o critério 1 contra este host sem trocar o baseline

O critério 1 pede "host conforme sai sem desvio e com código `0`". O host disponível é o
próprio WSL, que viola quatro regras do baseline do parque. Não existe execução contra ele
que dê `0` com `baseline.yaml`.

Pensei em fabricar um JSON de exemplo. Seria evidência falsa. Em vez disso escrevi
`execucoes/baselines/baseline-conforme.yaml`: **o padrão declarado muda, a coleta é a
mesma**. É legítimo porque a ferramenta existe justamente para comparar um host contra um
padrão — trocar o padrão é uso normal, não truque de teste.

O efeito colateral foi bom: `kernel.versao_minima` sai `conforme` num baseline e `desvio
medio` no outro, no mesmo host, sem uma linha de código mudar entre as duas execuções.
Isso prova "a severidade vem do baseline, não do código" melhor do que qualquer coisa que
eu tivesse planejado provar.

### E5 — O critério 1 esconde uma armadilha que só vi ao montar o baseline

Ao escrever `baseline-conforme.yaml` fiquei tentado a tirar `ssh.login_de_root`, já que
ele nunca é verificável com usuário comum e "sujaria" o relatório conforme.

Deixei de propósito. Ele sai `nao_verificado` e a execução termina com `0` mesmo assim —
que é a prova de que `nao_verificado` sozinho não promove o código de saída. A spec diz
isso no texto ("o `3` é separado de propósito", a tabela dos três vereditos), mas não tem
critério de aceite que teste. Agora tem evidência.

### E6 — O invariante I1 não é propriedade só da ferramenta, e a evidência precisa dizer isso

"Duas execuções devolvem o mesmo retrato" é verificável de fora, como a spec promete. Mas
o host de teste tem portas efêmeras de processos `node` que podem subir e descer entre as
duas execuções. Se uma delas mudar, o diff acusa, e não é defeito da ferramenta — é
mudança real do host.

Não mascarei isso filtrando portas efêmeras, que seria esconder inventário verdadeiro. O
arquivo de evidência do critério 5 distingue os dois casos no próprio veredito: se a
diferença estiver só em `coletado_em`, afirma o invariante; se houver outra, manda olhar o
diff e diz que mudança do host não é defeito do coletor. Nas execuções registradas, a
diferença foi só o instante da coleta.

### E7 — "Configuração efetiva" é a parte da spec que mais fácil se implementa errado

`grep PermitRootLogin /etc/ssh/sshd_config` funciona, roda sem privilégio, devolve um
valor e dá a resposta errada com frequência — `Include`, blocos `Match` e precedência por
primeira ocorrência. É a tentação óbvia, porque produz `conforme` em vez de
`nao_verificado` e deixa o relatório mais bonito.

A spec já tinha antecipado isso (pergunta 4 do brainstorm, corolário de D2), e é a parte
em que ter a spec escrita antes mais se pagou: o `grep` passaria no host de teste sem
reclamar e produziria falso negativo de auditoria em produção, que é o defeito mais caro
que uma ferramenta de compliance pode ter. Ficou `sshd -T`, que falha com usuário comum —
e falhar é o comportamento correto.

---

## Parte 3 — O que não foi feito

- **Testes automatizados de unidade.** As funções que mais pediriam teste isolado são
  `_versao_atende` e `faixa_do_bind`, ambas puras. Foram exercitadas só indiretamente, pela
  execução real. É a dívida mais óbvia desta entrega.
- **"SSH fora do ar" sem mexer no host.** O único jeito de produzir um "connection refused"
  verdadeiro a partir desta máquina foi parar e religar o `sshd` local, porque ele escuta
  em `0.0.0.0` e qualquer endereço local alcança. Está no script de evidência, é o único
  ponto que usa `sudo`, e a religação é verificada logo em seguida. Não há nenhum `sudo`
  na ferramenta.
- **Distro que não seja systemd.** As sondas de serviços e de NTP dependem de `systemctl` e
  `timedatectl`. Em host sem systemd elas viram `nao_verificado` com motivo, que é
  degradação honesta, mas não é cobertura.
