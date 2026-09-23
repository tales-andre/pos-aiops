# Curadoria

Onde a especificação precisou ser corrigida durante a implementação, o que eu entendi diferente do
que estava escrito, e os erros que cometi e corrigi no caminho.

A regra do ticket era clara: as decisões D1 a D5 não são negociáveis, e divergência se registra
aqui em vez de ser feita em silêncio. **Nenhuma das cinco decisões foi mudada.** O que segue é
outra coisa — lacunas, ambiguidades e um defeito de biblioteca que a spec não tinha como prever.

---

## 1. O defeito que quase falsificou a evidência do critério 7

**O que a spec dizia.** D2 escolhe o cliente oficial `kubernetes` para Python, e justifica:
"resolve o kubeconfig inteiro, incluindo a parte chata — certificado de cliente, `current-context`,
e principalmente os plugins de credencial por `exec`".

**O que aconteceu.** No cliente `kubernetes` 36.0.0, `load_kube_config()` grava o token do
kubeconfig em `Configuration.api_key["authorization"]`, enquanto
`Configuration.auth_settings()` — o método que monta o cabeçalho enviado — procura por
`api_key["BearerToken"]`. As duas chaves não conversam. O resultado é que **nenhum cabeçalho
`Authorization` é enviado** e o apiserver responde como `system:anonymous`.

**Por que isso é pior do que parece.** A falha não se apresenta como "credencial não enviada". Ela
se apresenta como **`403 Forbidden`** — exatamente a categoria `permissao_negada` que este
dashboard existe para distinguir das outras. Na primeira captura de evidência, o critério 7
"passou" com os cinco painéis negados, e eu quase registrei isso como comportamento correto de
degradação parcial. Não era degradação parcial: era o dashboard inteiro autenticando como anônimo.
O `kubectl` com o mesmo kubeconfig lia os pods sem problema — foi essa divergência que denunciou.

**O que fiz.** Não mudei D2. O cliente oficial continua sendo a escolha, e as razões de D2 seguem
válidas (o argumento do plugin `exec` para o EKS é forte e não tem substituto barato). Remendei
dentro do ponto único de passagem, em `src/acesso.py`, copiando a chave quando só a antiga existe,
com o comentário explicando o porquê. Ficou contido em cinco linhas num lugar auditável.

**A lição que vale além deste ticket.** D2 diz que o cliente oficial "perde" por ser "uma
dependência pesada, que costuma atrasar em relação à versão do cluster". O custo real que apareceu
foi outro e mais perverso: uma incoerência interna da biblioteca que **se disfarça de resposta
legítima do cluster**. Se eu fosse reescrever a seção "Perde" de D2, acrescentaria essa frase.

---

## 2. A spec trata os cinco painéis como iguais, e eles não são

**O que a spec dizia.** `01-comportamento.md` lista cinco painéis numa tabela e define, na seção de
ambiente hostil: "Permissão negada para **um** tipo de recurso → os painéis acessíveis continuam
funcionando; o painel negado mostra 'sem permissão para ler <recurso>'."

**O que estava faltando.** O painel de Namespaces não é par dos outros quatro — ele é
**pré-condição** deles. A própria spec diz isso duas linhas acima, na tabela: "serve de filtro para
todos os outros painéis". Mas a regra de degradação parcial foi escrita como se os cinco fossem
independentes.

**O que aconteceu na implementação.** Minha primeira versão escolhia o namespace a partir da lista
de namespaces. Quando essa leitura falhava, eu não tinha namespace, e os outros quatro painéis
recebiam um envelope inventado: `"nenhum namespace selecionado"`, categoria `falha_desconhecida`.
Duas consequências, ambas violando a spec:

- Com o **cluster fora do ar**, a tela dizia "nenhum namespace selecionado" em quatro dos cinco
  painéis. A causa real — cluster inalcançável, com o endereço tentado — aparecia só no painel de
  namespaces. A spec exige que o cenário 6 "mostre o erro em linguagem clara, com o endereço
  tentado"; eu estava escondendo a causa atrás de um sintoma. Pior: minha faixa global em `app.js`
  só aparece quando *todos* os envelopes trazem a mesma categoria grave, então ela não aparecia, e
  a tela ficava sem explicação nenhuma no topo.
- Com **403 em namespaces**, um único recurso negado derrubava quatro painéis — o "comportamento
  ingênuo" que a spec nomeia e proíbe explicitamente.

**Como resolvi, e a regra nova que isso cria.** Duas correções em `src/coleta.py`:

1. Quando não se consegue *listar* namespaces, cai para o namespace declarado no contexto corrente
   do kubeconfig. Uma credencial restrita quase sempre enxerga o próprio namespace e nenhum outro —
   é justamente o formato do contexto `platform-ro` que o brainstorm descreve. Sem essa queda, a
   ferramenta fica inútil exatamente para a credencial que ela mais precisa atender.
2. Quando não há namespace nenhum para ler, os quatro painéis repetem a **falha real** da listagem
   de namespaces, em vez de inventar uma mensagem própria.

**Se eu fosse corrigir a spec**, acrescentaria uma linha à tabela de ambiente hostil: *"quando o
recurso negado é o próprio painel de Namespaces, o dashboard usa o namespace declarado no contexto
do kubeconfig; se não houver, os demais painéis reportam a causa real da falha, nunca uma mensagem
derivada."*

---

## 3. "O motivo vem de X **ou** Y" — li como "e", de propósito

**O que a spec dizia.** Na tabela de painéis: "o motivo vem de `state.waiting.reason` ou
`lastState.terminated.reason`, nunca de `phase`".

**Como entendi diferente.** Lido ao pé da letra, "ou" autoriza parar no primeiro campo que tiver
valor. Para o caso central deste ticket, isso perderia a informação que resolve a triagem. Num pod
em `CrashLoopBackOff` por OOM:

- `state.waiting.reason` = `CrashLoopBackOff` — diz **o que** está acontecendo
- `lastState.terminated.reason` = `OOMKilled` — diz **por que**

São informações diferentes, e só a segunda diz o que fazer. `CrashLoopBackOff` sozinho manda a
pessoa abrir o terminal — que é precisamente o que o dashboard existe para evitar. Mostro os dois:
o estado é `CrashLoopBackOff` e o motivo é `OOMKilled / exit 137`.

Não considero isso uma correção da spec, e sim uma leitura que o texto permite mas não obriga. Fica
registrado porque quem ler o código e a spec lado a lado vai notar a diferença.

---

## 4. Ambiguidades que resolvi sozinho

Nenhuma delas estava na spec, e todas exigiram decisão.

**Service `ExternalName` nunca tem endpoint.** A regra literal — "sem endpoint quando não há
endereço" — marcaria todo `ExternalName` como falho, que é alarme falso: esse tipo de Service
resolve por DNS e não tem endpoints por construção. Excluí `ExternalName` da marcação. A spec não
menciona tipos de Service.

**O intervalo de atualização.** D3 escolhe "consulta em intervalo fixo" e não diz qual. Adotei 15
segundos, declarado no rodapé da tela. Curto o bastante para um chamado em movimento, longo o
bastante para não pesar no apiserver com várias pessoas olhando.

**Endpoints "não prontos".** Uma `EndpointSlice` pode listar endereços com `conditions.ready:
false` — um pod que existe mas não passa no readiness. Conto apenas os prontos, porque "tem
endpoint?" na triagem significa "o Service entrega tráfego?", e endereço não pronto não recebe
tráfego. É uma interpretação; a spec só diz "se tem endereço".

**Métodos HTTP.** A spec exige que o invariante de somente-leitura seja verificável, mas fala do
acesso ao apiserver, não da superfície HTTP local. Implementei apenas `do_GET`, de modo que
`POST`, `PUT`, `PATCH` e `DELETE` recebem `501` do próprio `BaseHTTPRequestHandler`, e incluí isso
na evidência do critério 9. É reforço, não exigência.

**Ordenação dentro dos painéis.** Objetos em falha aparecem primeiro. A spec só determina ordem
para eventos (`Warning` primeiro). Estendi o mesmo princípio aos demais painéis — numa triagem,
rolar a lista atrás do que está quebrado não é funcionalidade.

---

## 5. Uma adição de escopo que preciso declarar

Acrescentei os parâmetros de URL `?ns=` e `?q=`, que abrem a tela já num namespace e com a busca
preenchida. Não estavam pedidos.

**Por que não viola o corte de escopo.** O brainstorm é enfático: nada de seletor de cluster na
tela, porque "um seletor de cluster na tela é um botão que, num momento de pressa, aponta a pessoa
para produção achando que está em staging". O parâmetro que adicionei é de **namespace**, não de
cluster nem de contexto. O destino continua sendo exclusivamente o `current-context` do kubeconfig,
e não há caminho na interface que o mude. O risco que a decisão original queria evitar não existe
aqui — pelo contrário, colar um link do namespace certo no chamado é o uso que a ferramenta pede.

**Por que está aqui mesmo assim.** Foi decisão minha, tomada durante a implementação, sobre um
ponto que a spec fechou deliberadamente. Mesmo convencido de que não conflita, registrar é mais
barato do que alguém descobrir sozinho daqui a um ano.

---

## 6. Erros meus, corrigidos no caminho

**Código morto em `contexto_corrente()`.** Deixei um bloco `try/except` que construía um
`KubeConfigLoader` com um argumento placeholder e jogava fora o resultado com `del`. Não fazia
nada; era resíduo de uma tentativa abandonada de extrair o endereço do servidor pela biblioteca.
Removi e substituí pelo caminho que de fato funciona: reler o YAML do kubeconfig. Esse caminho tem
uma virtude que o outro não teria — não depende de chamada de rede, então o cabeçalho tem o que
mostrar mesmo com o cluster fora do ar, que é o critério 6.

**Mensagens de falha malformadas.** Minha primeira versão de `texto_da_categoria()` concatenava o
nome do recurso ao texto da categoria, produzindo `"a credencial não foi aceita namespaces"`. Só
apareceu quando li a evidência capturada, não quando escrevi o código. Troquei por um modelo com
`{r}` por categoria, e as categorias de ambiente (cluster fora do ar, credencial inválida) deixaram
de receber o nome do recurso — a causa não é do recurso, e repetir o nome ali só confunde.

**`__import__('acesso')` dentro de `dashboard.py`.** Escrevi isso para exibir os verbos permitidos
na subida sem "sujar" os imports do topo. É feio e esconde uma dependência de quem lê o arquivo.
Troquei por um `import` normal com comentário. O teste do invariante checa importação do cliente
`kubernetes`, não de `acesso`, então nunca teria pegado isso — foi revisão, não ferramenta.

---

## 7. O que ficou como dívida assumida

- **`list` sem paginação.** O snapshot lê o namespace inteiro de uma vez. Num namespace com
  milhares de pods isso pesa. Está registrado em `design.md`, na seção de riscos, e aceito para
  esta fatia.
- **`http.server` é single-thread.** Duas abas abertas no mesmo dashboard se enfileiram. Aceito por
  D1 (`localhost`, uma pessoa), mitigado pelo timeout curto que impede um cluster fora do ar de
  prender o servidor.
- **O remendo do cliente é um remendo.** Se uma versão futura do `kubernetes` corrigir a
  incoerência, a condição `if "authorization" in ... and "BearerToken" not in ...` simplesmente
  para de disparar e nada quebra. Mas continua sendo código que existe por causa de um defeito de
  terceiro, e merece ser revisitado quando a dependência subir de versão.
- **O aviso do `openspec archive`.** A mudança arquivou com um alerta não-bloqueante: "Consider
  splitting changes with more than 10 deltas" — foram 14 requirements em três capacidades. Não
  dividi porque as três capacidades nascem juntas e não fazem sentido em separado nesta fatia, mas
  o alerta está certo em princípio: se houvesse uma segunda fatia, ela viria como mudança própria.
