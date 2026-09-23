#!/usr/bin/env bash
# Captura a evidência dos 9 critérios de aceite de specs/01-comportamento.md.
#
# Cada arquivo gerado em execucoes/ começa com o comando exato que o produziu,
# para que a evidência seja reproduzível e não apenas afirmada.
#
# Uso:  bash execucoes/capturar-evidencias.sh
set -u

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAIDA="$RAIZ/execucoes"
KUBE_LAB="$HOME/.kube/metacortex-lab.yaml"
KUBE_MORTO="$RAIZ/ambiente/kubeconfig-cluster-morto.yaml"
KUBE_RESTRITO="$RAIZ/ambiente/kubeconfig-leitura-restrita.yaml"
KUBE_CRED="$RAIZ/ambiente/kubeconfig-credencial-invalida.yaml"

PID=""

subir() {  # subir <kubeconfig> <porta>
  KUBECONFIG="$1" python3 "$RAIZ/src/dashboard.py" --porta "$2" \
    >"$SAIDA/.servidor.log" 2>&1 &
  PID=$!
  for _ in $(seq 1 40); do
    curl -fsS "http://127.0.0.1:$2/healthz" >/dev/null 2>&1 && return 0
    sleep 0.25
  done
  return 1
}

derrubar() {
  [ -n "$PID" ] && kill "$PID" 2>/dev/null
  wait "$PID" 2>/dev/null
  PID=""
}

# cabeca <arquivo> <titulo> <comando-que-gerou>
cabeca() {
  {
    echo "=============================================================="
    echo "$2"
    echo "=============================================================="
    echo "gerado em : $(date -Is)"
    echo "comando   : $3"
    echo "--------------------------------------------------------------"
    echo
  } >"$1"
}

jqs() { python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))'; }

trap derrubar EXIT

# =====================================================================
echo ">> cenário saudável (kubeconfig de laboratório, porta 8700)"
subir "$KUBE_LAB" 8700 || { echo "servidor não subiu"; cat "$SAIDA/.servidor.log"; exit 1; }

# --- Critério 1 -------------------------------------------------------
A="$SAIDA/criterio-01-contexto-corrente.txt"
cabeca "$A" "CRITÉRIO 1 — sobe contra o contexto corrente e mostra qual é, sem argumento de cluster" \
  "KUBECONFIG=~/.kube/metacortex-lab.yaml python3 src/dashboard.py --porta 8700 ; curl -s localhost:8700/api/contexto"
{
  echo "### saída do processo ao subir (stderr) — note: nenhum argumento de cluster/contexto"
  cat "$SAIDA/.servidor.log"
  echo
  echo "### confirmação independente: kubectl config current-context"
  KUBECONFIG="$KUBE_LAB" kubectl config current-context
  echo
  echo "### GET /api/contexto"
  curl -s http://127.0.0.1:8700/api/contexto | jqs
  echo
  echo "### a única flag aceita é --porta"
  python3 "$RAIZ/src/dashboard.py" --help
  echo
  echo "### o cabeçalho fixo da tela carrega contexto e servidor do /api/contexto:"
  grep -n 'ctx-nome\|ctx-servidor\|somente-leitura' "$RAIZ/src/ui/index.html"
} >>"$A" 2>&1

# --- Critério 2 -------------------------------------------------------
A="$SAIDA/criterio-02-namespaces-filtram.txt"
cabeca "$A" "CRITÉRIO 2 — lista namespaces, e selecionar um filtra os demais painéis" \
  "curl -s 'localhost:8700/api/snapshot?ns=<N>' para N em helio-prod e orion-stg"
{
  echo "### namespaces listados"
  curl -s "http://127.0.0.1:8700/api/snapshot?ns=helio-prod" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps(d["namespaces"], ensure_ascii=False, indent=2))'
  echo
  for ns in helio-prod orion-stg; do
    echo "### ns=$ns -> pods e services devolvidos (repare que mudam com o namespace)"
    curl -s "http://127.0.0.1:8700/api/snapshot?ns=$ns" | python3 -c '
import json,sys
d=json.load(sys.stdin)
print("  namespace no snapshot:", d["namespace"])
print("  pods    :", [i["nome"] for i in d["pods"]["itens"]])
print("  services:", [i["nome"] for i in d["services"]["itens"]])
print("  deploys :", [i["nome"] for i in d["deployments"]["itens"]])'
    echo
  done
} >>"$A" 2>&1

# --- Critério 3 -------------------------------------------------------
A="$SAIDA/criterio-03-deployment-zero-de-n.txt"
cabeca "$A" "CRITÉRIO 3 — Deployment sem réplica pronta aparece como 0/N, não em branco" \
  "curl -s 'localhost:8700/api/snapshot?ns=nyx-prod' | .deployments"
{
  echo "### a API OMITE readyReplicas quando é zero — prova direta:"
  KUBECONFIG="$KUBE_LAB" kubectl get deployment nyx-api -n nyx-prod -o jsonpath='{.status}' | jqs
  echo
  echo "### o campo readyReplicas existe? (vazio = ausente, não zero)"
  echo -n "  valor bruto: '"
  KUBECONFIG="$KUBE_LAB" kubectl get deployment nyx-api -n nyx-prod -o jsonpath='{.status.readyReplicas}'
  echo "'"
  echo
  echo "### o que o dashboard serve:"
  curl -s "http://127.0.0.1:8700/api/snapshot?ns=nyx-prod" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps(d["deployments"], ensure_ascii=False, indent=2))'
} >>"$A" 2>&1

# --- Critério 4 -------------------------------------------------------
A="$SAIDA/criterio-04-crashloop-com-motivo.txt"
cabeca "$A" "CRITÉRIO 4 — pod em CrashLoopBackOff aparece com o motivo, não como Running" \
  "curl -s 'localhost:8700/api/snapshot?ns=nyx-prod' | .pods"
{
  echo "### a armadilha: a API reporta phase=Running para um pod em CrashLoopBackOff"
  KUBECONFIG="$KUBE_LAB" kubectl get pods -n nyx-prod -o custom-columns='NOME:.metadata.name,PHASE:.status.phase,WAITING:.status.containerStatuses[0].state.waiting.reason,LAST:.status.containerStatuses[0].lastState.terminated.reason'
  echo
  echo "### o que o dashboard serve (estado vem do container, motivo do lastState):"
  curl -s "http://127.0.0.1:8700/api/snapshot?ns=nyx-prod" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps(d["pods"], ensure_ascii=False, indent=2))'
  echo
  echo "### ImagePullBackOff em orion-stg, mesmo tratamento:"
  curl -s "http://127.0.0.1:8700/api/snapshot?ns=orion-stg" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps([{k:i[k] for k in ("nome","estado","motivo","fase_api")} for i in d["pods"]["itens"]], ensure_ascii=False, indent=2))'
} >>"$A" 2>&1

# --- Critério 5 -------------------------------------------------------
A="$SAIDA/criterio-05-service-sem-endpoint.txt"
cabeca "$A" "CRITÉRIO 5 — Service sem endpoint é marcado como tal, distinto de erro de leitura" \
  "curl -s 'localhost:8700/api/snapshot?ns=nyx-stg' | .services"
{
  echo "### nyx-stg: selector divergente, Service sem endpoint"
  KUBECONFIG="$KUBE_LAB" kubectl get endpoints nyx-api -n nyx-stg -o yaml | grep -v 'managedFields' | head -20
  echo
  echo "### o campo de endereços NÃO vem vazio — ele não vem (EndpointSlice):"
  KUBECONFIG="$KUBE_LAB" kubectl get endpointslice -n nyx-stg -l kubernetes.io/service-name=nyx-api -o jsonpath='{.items[0].endpoints}'
  echo "   <- vazio acima significa campo AUSENTE"
  echo
  echo "### o que o dashboard serve em nyx-stg (ok:true + sem_endpoint:true):"
  curl -s "http://127.0.0.1:8700/api/snapshot?ns=nyx-stg" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps(d["services"], ensure_ascii=False, indent=2))'
  echo
  echo "### contraste — helio-prod, Service COM endpoint:"
  curl -s "http://127.0.0.1:8700/api/snapshot?ns=helio-prod" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps([{k:i[k] for k in ("nome","endpoints","sem_endpoint")} for i in d["services"]["itens"]], ensure_ascii=False, indent=2))'
  echo
  echo "NOTA: ok=true com sem_endpoint=true é DIFERENTE de ok=false (erro de leitura)."
  echo "      Ver critério 7 para a forma que o envelope assume quando a leitura falha."
} >>"$A" 2>&1

# --- Critério 8 -------------------------------------------------------
A="$SAIDA/criterio-08-busca-e-filtro.txt"
cabeca "$A" "CRITÉRIO 8 — busca por nome e filtro por namespace funcionam sobre os painéis" \
  "curl -s 'localhost:8700/api/snapshot?ns=<N>' + filtro de busca aplicado no navegador (src/ui/app.js)"
{
  echo "### filtro por namespace: o parâmetro ns muda o conjunto devolvido"
  for ns in helio-prod nyx-prod nyx-stg orion-stg; do
    curl -s "http://127.0.0.1:8700/api/snapshot?ns=$ns" | python3 -c '
import json,sys
d=json.load(sys.stdin)
print("  ns=%-12s deployments=%-2d pods=%-2d services=%d" % (d["namespace"], len(d["deployments"]["itens"]), len(d["pods"]["itens"]), len(d["services"]["itens"])))'
  done
  echo
  echo "### busca por nome: aplicada no cliente sobre deployments, pods e services."
  echo "### Simulação da mesma função de filtro de src/ui/app.js sobre o dado servido:"
  for termo in postgres api nyx inexistente-xyz; do
    curl -s "http://127.0.0.1:8700/api/snapshot?ns=nyx-prod" | python3 -c "
import json,sys
d=json.load(sys.stdin); t='$termo'.lower()
for painel in ('deployments','pods','services'):
    todos=d[painel]['itens']
    achados=[i['nome'] for i in todos if t in i['nome'].lower()]
    if not todos:            estado='nenhum objeto neste namespace'
    elif not achados:        estado='nenhum %s casa com \"%s\" (mensagem distinta de vazio/erro)' % (painel[:-1], t)
    else:                    estado='%d de %d -> %s' % (len(achados), len(todos), achados)
    print('  busca=%-16s %-12s %s' % (repr(t), painel, estado))
print()"
  done
  echo "### o código que implementa (app.js):"
  grep -n 'filtrados\|SEM_BUSCA\|estado.busca' "$RAIZ/src/ui/app.js" | head -12
} >>"$A" 2>&1

# --- HTML servido (prova de que a tela é servida e não é branca) ------
curl -s http://127.0.0.1:8700/ >"$SAIDA/pagina-servida.html"
curl -s "http://127.0.0.1:8700/api/snapshot?ns=nyx-prod" | jqs >"$SAIDA/snapshot-nyx-prod.json"
curl -s "http://127.0.0.1:8700/api/snapshot?ns=helio-prod" | jqs >"$SAIDA/snapshot-helio-prod.json"
curl -s "http://127.0.0.1:8700/api/snapshot?ns=nyx-stg" | jqs >"$SAIDA/snapshot-nyx-stg.json"
curl -s "http://127.0.0.1:8700/api/snapshot?ns=orion-stg" | jqs >"$SAIDA/snapshot-orion-stg.json"

derrubar

# =====================================================================
echo ">> cenário 6: cluster fora do ar (porta 8701)"
subir "$KUBE_MORTO" 8701
A="$SAIDA/criterio-06-cluster-fora-do-ar.txt"
cabeca "$A" "CRITÉRIO 6 — com o cluster fora do ar, a tela carrega e explica; não fica em branco" \
  "KUBECONFIG=ambiente/kubeconfig-cluster-morto.yaml python3 src/dashboard.py --porta 8701"
{
  echo "### o kubeconfig fabricado aponta para um endereço que não responde:"
  grep -n 'server:' "$KUBE_MORTO"
  echo
  echo "### o servidor SOBE mesmo assim (stderr):"
  cat "$SAIDA/.servidor.log"
  echo
  echo "### a página é servida normalmente — HTTP e tamanho:"
  curl -s -o /dev/null -w '  GET /            -> HTTP %{http_code}, %{size_download} bytes\n' http://127.0.0.1:8701/
  curl -s -o /dev/null -w '  GET /api/contexto-> HTTP %{http_code}\n' http://127.0.0.1:8701/api/contexto
  echo
  echo "### /api/contexto responde MESMO sem cluster (o cabeçalho tem o que mostrar):"
  curl -s http://127.0.0.1:8701/api/contexto | jqs
  echo
  echo "### /api/snapshot: envelope de falha classificado, com o endereço tentado"
  curl -s http://127.0.0.1:8701/api/snapshot | jqs
  echo
  echo "### não há stack trace no que é servido ao navegador:"
  if curl -s http://127.0.0.1:8701/api/snapshot | grep -qi 'traceback\|File \"'; then
    echo "  FALHA: há rastro de pilha na resposta"
  else
    echo "  OK: nenhum 'Traceback' na resposta servida"
  fi
  echo
  echo "### a interface oferece nova tentativa (app.js):"
  grep -n 'btn-retentar\|tentar de novo' "$RAIZ/src/ui/app.js"
} >>"$A" 2>&1
curl -s http://127.0.0.1:8701/api/snapshot | jqs >"$SAIDA/snapshot-cluster-fora-do-ar.json"
derrubar

# =====================================================================
echo ">> cenário 7: permissão negada para um recurso (porta 8702)"
subir "$KUBE_RESTRITO" 8702
A="$SAIDA/criterio-07-permissao-negada.txt"
cabeca "$A" "CRITÉRIO 7 — com permissão negada para um recurso, os outros painéis continuam funcionando" \
  "KUBECONFIG=ambiente/kubeconfig-leitura-restrita.yaml python3 src/dashboard.py --porta 8702"
{
  echo "### a credencial restrita (SA dashboard-leitura-restrita): pode pods, não pode services"
  for r in namespaces pods deployments events services endpointslices.discovery.k8s.io; do
    printf '  can-i list %-34s ' "$r"
    KUBECONFIG="$KUBE_LAB" kubectl auth can-i list "$r" -n nyx-prod \
      --as=system:serviceaccount:nyx-prod:dashboard-leitura-restrita
  done
  echo
  echo "### o que o dashboard serve com essa credencial — painel a painel:"
  curl -s "http://127.0.0.1:8702/api/snapshot?ns=nyx-prod" | python3 -c '
import json,sys
d=json.load(sys.stdin)
for k in ("namespaces","deployments","pods","services","eventos"):
    e=d[k]
    if e["ok"]:
        print("  %-12s OK        %d itens" % (k, len(e["itens"])))
    else:
        print("  %-12s FALHA     categoria=%s  titulo=%r" % (k, e["categoria"], e["titulo"]))'
  echo
  echo "### resposta completa (repare: pods populado E services negado, no MESMO snapshot):"
  curl -s "http://127.0.0.1:8702/api/snapshot?ns=nyx-prod" | jqs
} >>"$A" 2>&1
curl -s "http://127.0.0.1:8702/api/snapshot?ns=nyx-prod" | jqs >"$SAIDA/snapshot-permissao-negada.json"
derrubar

# =====================================================================
echo ">> extra: credencial inválida, distinta de cluster fora do ar (porta 8704)"
subir "$KUBE_CRED" 8704
A="$SAIDA/extra-credencial-invalida.txt"
cabeca "$A" "EXTRA (01-comportamento.md) — credencial inválida tem mensagem DISTINTA de cluster fora do ar" \
  "KUBECONFIG=ambiente/kubeconfig-credencial-invalida.yaml python3 src/dashboard.py --porta 8704"
{
  echo "### o cluster RESPONDE (é o mesmo endereço do cenário saudável); o token é que não presta"
  grep -n 'server:\|token:' "$KUBE_CRED" | sed 's/token: .*/token: <token invalido fabricado>/'
  echo
  echo "### o que o dashboard serve:"
  curl -s "http://127.0.0.1:8704/api/snapshot?ns=nyx-prod" | python3 -c '
import json,sys
d=json.load(sys.stdin)
for k in ("namespaces","deployments","pods","services","eventos"):
    e=d[k]
    print("  %-12s %s" % (k, "OK" if e["ok"] else "%s -> %r" % (e["categoria"], e["titulo"])))'
  echo
  echo "### as duas mensagens lado a lado — a ação de quem lê é diferente em cada uma:"
  echo -n "  cluster fora do ar  : "
  python3 -c 'import json;d=json.load(open("'"$SAIDA"'/snapshot-cluster-fora-do-ar.json"));print(d["pods"]["categoria"],"|",d["pods"]["titulo"],"|",d["pods"]["mensagem"])'
  echo -n "  credencial inválida : "
  curl -s "http://127.0.0.1:8704/api/snapshot?ns=nyx-prod" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["pods"]["categoria"],"|",d["pods"]["titulo"],"|",d["pods"]["mensagem"])'
} >>"$A" 2>&1
derrubar

# =====================================================================
echo ">> critério 9: invariante de somente-leitura"
A="$SAIDA/criterio-09-invariante-somente-leitura.txt"
cabeca "$A" "CRITÉRIO 9 — nenhum caminho de código alcança verbo de escrita, verificável em um único ponto" \
  "python3 testes/test_invariante.py"
{
  echo "### O PONTO ÚNICO — src/acesso.py:"
  grep -n 'VERBOS_PERMITIDOS = \|def ler(' "$RAIZ/src/acesso.py"
  echo
  sed -n '/^VERBOS_PERMITIDOS/,/^TIMEOUT/p' "$RAIZ/src/acesso.py"
  echo
  echo "### verificação mecânica:"
  python3 "$RAIZ/testes/test_invariante.py"
  echo "  (código de saída: $?)"
  echo
  echo "### o servidor HTTP recusa qualquer método que não seja GET:"
  echo "  (subindo em 8703 só para esta prova)"
} >>"$A" 2>&1

subir "$KUBE_LAB" 8703
{
  for m in POST PUT PATCH DELETE; do
    curl -s -o /dev/null -X "$m" -w "  $m  /  -> HTTP %{http_code}\n" http://127.0.0.1:8703/
  done
  curl -s -o /dev/null -w '  GET   /  -> HTTP %{http_code}\n' http://127.0.0.1:8703/
} >>"$A" 2>&1
derrubar

rm -f "$SAIDA/.servidor.log"
echo ">> pronto. arquivos em execucoes/:"
ls -1 "$SAIDA"
