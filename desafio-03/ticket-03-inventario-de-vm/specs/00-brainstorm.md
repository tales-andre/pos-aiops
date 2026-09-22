# Brainstorm — substituição do Roster manual

Documento de maturação de escopo. Escrito antes de qualquer linha de código, que é a regra do
desafio: código que aparece antes da spec é vibe coding com outro nome.

## O problema, na linguagem de quem sofre com ele

O Roster é uma página que o Mouse mantém à mão desde quando o parque tinha trinta hosts. Nasceu
correta e envelheceu: host que mudou de papel, agente instalado numa madrugada de incidente e
nunca registrado, chave SSH que entrou para desbloquear alguém e ficou.

Quando o Seraph pergunta quantas VMs estão fora do padrão, a resposta honesta é "não sei". Quando
a Niobe pergunta quanto o parque custa a mais por estar assim, é a mesma resposta.

Duas perguntas diferentes, uma causa comum: **não existe retrato confiável do estado real dos
hosts**.

## O que este primeiro pedaço é, e o que não é

| É | Não é |
|---|---|
| Uma ferramenta que roda na máquina de quem opera | Um agente instalado no host auditado |
| Um retrato de **um** host por execução | Um varredor de parque inteiro |
| Coleta somente-leitura | Ferramenta de remediação |
| Comparação contra um baseline versionado | Fonte da verdade do que o baseline deveria ser |
| Saída consumível por máquina e por humano | Interface gráfica ou dashboard |

A restrição que define o desenho: **não existe agente instalado nas VMs do parque e ninguém vai
instalar um só para isso**. O que existe em toda VM é acesso por chave. Então a ferramenta entra
por SSH, com o que já está lá, e não deixa nada para trás.

## Perguntas que precisaram de resposta antes de especificar

**1. O que fazer quando um dado não pode ser coletado?**

A coleta entra com um usuário comum, e parte do que o baseline pede só se lê com privilégio. Três
saídas possíveis:

- reportar como conforme — **mentira**, e a pior das três, porque produz falso negativo de
  auditoria
- abortar a execução inteira — inútil, joga fora os oito dados que deram certo por causa do nono
- reportar como não verificado — honesto, e obriga o veredito a ter três valores, não dois

Escolhido o terceiro. É a decisão que mais molda o formato de saída.

**2. Qual é a unidade de confiança: o host ou a regra?**

Se fosse o host, bastaria "conforme/não conforme". Mas o plantão às três da manhã não quer saber
se o host está bem — quer saber **o que** está errado e **se importa agora**. Então a unidade é a
regra, cada uma com seu veredito e sua severidade.

**3. Quem decide a severidade?**

O baseline, não a ferramenta. Severidade é política da casa e muda sem que o código precise mudar.
A ferramenta lê a seção `severidade` do baseline e obedece.

**4. O que significa "efetiva" em `ssh.login_de_root`?**

O baseline pede a configuração que vale, não a que está escrita no arquivo. `sshd_config` tem
`Include`, tem `Match`, tem precedência por primeira ocorrência — ler o arquivo com `grep` dá a
resposta errada com frequência. A configuração efetiva se obtém pedindo ao próprio `sshd`, o que
exige privilégio. Daí a importância da resposta da pergunta 1.

**5. Como provar que a ferramenta só lê?**

Não basta afirmar. Duas execuções seguidas contra o mesmo host precisam devolver o mesmo veredito
para cada regra, mudando entre elas apenas o instante da coleta. Isso vira critério de aceite
testável, e não promessa.

## Riscos identificados

| Risco | Mitigação escolhida |
|---|---|
| A chave privada vazar em log, saída ou mensagem de erro | nunca carregar o conteúdo da chave em memória; passar o **caminho** ao cliente SSH e deixar o material fora do processo |
| Confundir host inalcançável com host conforme | caminhos de saída distintos, com código de retorno próprio |
| Distro diferente quebrar a coleta | comandos escolhidos entre os mais portáveis possíveis, e falha de comando vira `nao_verificado`, não exceção |
| Saída divergir entre os dois formatos | um único modelo de dados em memória, dois renderizadores sobre ele |

## O que fica de fora desta fatia

- Varredura de parque inteiro, paralelismo e inventário agregado
- Persistência, histórico e comparação entre execuções ao longo do tempo
- Qualquer escrita no host auditado
- Integração com o Roster — ele consumirá o JSON quando existir, e é só isso que ele precisa
