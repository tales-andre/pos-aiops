# Marketing pessoal

O enunciado oferece três temas como direções, não roteiros: *"Cada um é uma tese que você pode
defender do seu jeito, com o recorte, o formato e os exemplos que quiser. O que os tickets te
deram é a prova; a opinião é sua."*

Este arquivo reúne a **prova** que os quatro tickets produziram para cada tese, com ponteiro para
o artefato. O texto do post não está aqui de propósito — a opinião é de quem vai assinar.

---

## Tema 1 — O que muda quando a especificação vem antes do código

**A tese:** com agente, o que separa entrega boa de entrega descartável não é o modelo, é o que
existe escrito antes do primeiro prompt.

**A prova mais forte é uma divergência registrada.** No Ticket 01, a skill carrega uma receita
para "migração de banco no start": extrair para um Job e sobrescrever `command`. Quando um agente
em sessão limpa aplicou isso ao `encontros-tech`, ele **não seguiu a receita** — percebeu que ali
o `create_all` roda no *import* do módulo, não num entrypoint, então sobrescrever o comando não
resolve nada. O Job reduz a corrida; não elimina.

O agente só conseguiu discordar porque o corpo da skill explica **o porquê** de cada regra, e não
só o que fazer. Uma instrução escrita como receita teria produzido um manifesto errado com cara de
certo.

| Evidência | Onde |
|---|---|
| A divergência, em detalhe | `ticket-01-padrao-de-manifests/origem-da-skill.md` |
| O documento de decisões escrito antes do código | `ticket-03-inventario-de-vm/specs/02-decisoes.md` |
| O que o agente entendeu diferente do que estava escrito | `ticket-03-.../curadoria.md` e `ticket-04-.../curadoria.md` |

**O contraste que dá para defender:** os tickets 01 e 02 nasceram de fluxo rodado à mão; os
tickets 03 e 04 nasceram de spec escrita antes. São dois caminhos diferentes para o mesmo fim, e
os dois documentam a divergência entre o que foi escrito e o que foi entendido.

---

## Tema 2 — Automatizar é decidir o que fica de fora

**A tese:** o valor de uma automação está tanto no que ela cobre quanto no que ela recusa cobrir.

**A prova é numérica.** O padrão da Metacortex tem 21 itens conferíveis. A skill do Ticket 01
cobre 9 por script e 5 por instrução. Os outros 7 foram deliberadamente deixados de fora:

- **3 porque o Trivy já faz melhor** — e reimplementar seria manter duas verdades sobre a mesma
  regra, que é como um padrão começa a divergir de si mesmo
- **o Bloco 4 inteiro**, um glossário de Kubernetes, porque empacotá-lo gastaria contexto
  ensinando ao agente o que ele já sabe

E a recusa mais interessante não é de regra, é de **capacidade**: a skill confere e relata, mas
não corrige. Parte dos desvios não tem conserto no YAML — credencial já comitada precisa de
rotação, `create_all` no import precisa de mudança no código. Uma skill que "arruma" esses casos
produz manifesto limpo sobre problema intacto.

| Evidência | Onde |
|---|---|
| A triagem regra a regra, com os quatro destinos | `ticket-01-.../curadoria.md` |
| A fronteira com o Trivy, medida rodando | `ticket-01-.../execucoes/00-trivy-baseline.txt` |
| O que a skill de triagem fixou e o que deixou o agente decidir | `ticket-02-.../curadoria.md` |

**O gancho que ninguém espera:** a medição do Ticket 02 mostrou que a regra "identificada a causa,
a triagem acabou" tem custo — o agente **sem** skill foi mais fundo e mediu o consumo real de
memória, que a versão com skill não mediu. Decidir o que fica de fora inclui aceitar o que se
perde ao fazê-lo.

---

## Tema 3 — Dar acesso não é dar método

**A tese:** ferramenta resolve alcance, não resolve critério.

**A prova está numa flag que promete mais do que entrega.** O enunciado diz que o
`mcp-server-kubernetes` "fica em modo não-destrutivo: a triagem lê o cluster, nunca escreve nele".
Levantado por handshake MCP direto, com e sem a flag: `ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS=true`
remove **5 das 24 ferramentas**. Continuam expostas `kubectl_apply`, `kubectl_create`,
`kubectl_patch`, `kubectl_scale`, `kubectl_rollout` e `exec_in_pod`.

**Não-destrutivo não é somente-leitura.** Quem confia na flag como garantia está protegido contra
`delete` e desprotegido contra tudo o mais.

E o melhor argumento não é esse — é o experimento que aconteceu sem ser planejado. No baseline
**sem** skill do chamado 1, o agente usou `kubectl exec` dentro de um container para ler o cgroup e
medir a memória. Usou com responsabilidade, em staging, e obteve um dado melhor por causa disso.
Mas nada no ambiente o impedia de fazer o mesmo em produção. Os três agentes **com** skill não
tocaram em nenhum verbo de escrita. A diferença entre eles não foi a permissão disponível — foi a
instrução.

| Evidência | Onde |
|---|---|
| As 24 ferramentas, com e sem a flag | `ticket-02-.../execucoes/00-mcp-ferramentas.md` |
| As três camadas que sustentam o somente-leitura | `ticket-02-.../curadoria.md` |
| O contraste com e sem skill, medido | `ticket-02-.../execucoes/comparacao-com-e-sem-skill.md` |

**O número que fecha o argumento:** com skill, a triagem foi 23% e 36% mais rápida — mas achou a
mesma causa que o agente sem skill. A skill não comprou capacidade de diagnóstico. Comprou método
repetível, tempo, e um limite de escrita que não depende da boa vontade de quem está rodando.
