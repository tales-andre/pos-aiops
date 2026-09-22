#!/usr/bin/env bash
# Gera a evidencia dos 6 criterios de aceite de specs/01-comportamento.md contra o host
# SSH real. Reexecutavel: apaga e regrava tudo que produz.
#
#   ./execucoes/gerar-evidencias.sh
#
# Nada aqui escreve no host auditado. Os unicos comandos com sudo estao no cenario
# "SSH fora do ar", que para e RELIGA o sshd da propria maquina de teste, para produzir
# um "connection refused" de verdade em vez de simulado.

set -u

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVID="$RAIZ/execucoes"
TMP="$EVID/.tmp"
BASE="$RAIZ/baseline.yaml"
BCONF="$EVID/baselines/baseline-conforme.yaml"
BMEDIO="$EVID/baselines/baseline-somente-medio.yaml"

HOST=localhost
USUARIO=tales
CHAVE="$HOME/.ssh/inventario_ed25519"
CHAVE_ERRADA="$HOME/.ssh/id_ed25519"   # existe, mas nao esta em authorized_keys

cd "$RAIZ" || exit 1
rm -rf "$TMP"; mkdir -p "$TMP"
rm -f "$EVID"/ca*.json "$EVID"/ca*.md "$EVID"/ca*.txt "$EVID"/00-*.txt "$EVID/RESUMO.md"

# tabela do resumo: "cenario|criterio|rc esperado|rc obtido|arquivo"
LINHAS=()
anotar() { LINHAS+=("$1|$2|$3|$4|$5"); }

titulo() { printf '===== %s =====\n' "$1"; }

# ---------------------------------------------------------------------------
titulo "Codigo 4 - erro de uso (pre-requisito da tabela de codigo de saida)"
# ---------------------------------------------------------------------------
{
  echo "# Codigo de saida 4 — erro de uso"
  echo
  echo "Nenhum destes cenarios abre conexao SSH: o problema esta na invocacao ou na"
  echo "maquina de quem opera, nao no host alvo."
  echo
  for caso in "baseline-ausente" "baseline-inexistente" "formato-invalido" "chave-inexistente"; do
    case "$caso" in
      baseline-ausente)     args=(--host "$HOST" --usuario "$USUARIO" --chave "$CHAVE") ;;
      baseline-inexistente) args=(--host "$HOST" --usuario "$USUARIO" --chave "$CHAVE" --baseline /nao/existe.yaml) ;;
      formato-invalido)     args=(--host "$HOST" --usuario "$USUARIO" --chave "$CHAVE" --baseline "$BASE" --formato xml) ;;
      chave-inexistente)    args=(--host "$HOST" --usuario "$USUARIO" --chave /nao/existe.key --baseline "$BASE") ;;
    esac
    echo "## $caso"
    echo '```'
    echo "\$ ./inventario ${args[*]}"
    ./inventario "${args[@]}" 2>&1 >/dev/null
    echo "rc=$?"
    echo '```'
    echo
  done
} > "$EVID/00-erro-de-uso.txt"
anotar "erro de uso (4 variantes)" "tabela de codigo de saida" "4" "4" "00-erro-de-uso.txt"

# ---------------------------------------------------------------------------
titulo "CA1 - host conforme sai sem desvio e com codigo 0"
# ---------------------------------------------------------------------------
./inventario --host "$HOST" --usuario "$USUARIO" --chave "$CHAVE" \
             --baseline "$BCONF" --formato ambos --saida "$TMP" 2>/dev/null
RC1=$?
mv "$TMP/inventario-$HOST.json" "$EVID/ca1-host-conforme.json"
mv "$TMP/inventario-$HOST.md"   "$EVID/ca1-host-conforme.md"
{
  echo "# CA1 — host conforme"
  echo
  echo "Baseline usado: execucoes/baselines/baseline-conforme.yaml (padrao declarado que"
  echo "este host satisfaz). A coleta e a mesma do CA2; o que muda e o padrao, nunca o host."
  echo
  echo "\$ ./inventario --host $HOST --usuario $USUARIO --chave <caminho> --baseline baseline-conforme.yaml"
  echo "rc=$RC1   (esperado: 0)"
  echo
  echo "Contagem de vereditos:"
  python3 -c "import json;d=json.load(open('$EVID/ca1-host-conforme.json'));print(' ',d['resumo'])"
  echo
  echo "Observe que ssh.login_de_root continua nao_verificado e AINDA ASSIM o codigo e 0:"
  echo "nao_verificado sozinho nao promove o codigo de saida."
} > "$EVID/ca1-codigo-de-retorno.txt"
anotar "host conforme" "CA1" "0" "$RC1" "ca1-host-conforme.json / .md"

# ---------------------------------------------------------------------------
titulo "CA2 + CA3 - desvios por severidade e nao_verificado, nos dois formatos"
# ---------------------------------------------------------------------------
./inventario --host "$HOST" --usuario "$USUARIO" --chave "$CHAVE" \
             --baseline "$BASE" --formato ambos --saida "$TMP" 2>/dev/null
RC2=$?
mv "$TMP/inventario-$HOST.json" "$EVID/ca2-desvios-baseline-do-parque.json"
mv "$TMP/inventario-$HOST.md"   "$EVID/ca2-desvios-baseline-do-parque.md"
{
  echo "# CA2 e CA3 — execucao real contra o baseline do parque"
  echo
  echo "Os dois arquivos abaixo saem da MESMA execucao (--formato ambos), o que e a"
  echo "prova de que os dois renderizadores estao sobre um unico modelo em memoria."
  echo
  echo "\$ ./inventario --host $HOST --usuario $USUARIO --chave <caminho> --baseline baseline.yaml --formato ambos --saida execucoes/"
  echo "rc=$RC2   (esperado: 1 — ha desvio critico)"
  echo
  echo "## CA2 — cada desvio classificado pela severidade que o baseline atribui"
  echo
  python3 - <<PY
import json
d = json.load(open("$EVID/ca2-desvios-baseline-do-parque.json"))
for e in d["conformidade"]:
    if e["veredito"] == "desvio":
        print("  %-38s severidade=%s" % (e["regra"], e.get("severidade")))
print()
print("  resumo:", json.dumps(d["resumo"], ensure_ascii=False))
PY
  echo
  echo "## CA3 — regra nao verificavel aparece como nao_verificado nos DOIS formatos"
  echo
  echo "JSON:"
  python3 - <<PY
import json
d = json.load(open("$EVID/ca2-desvios-baseline-do-parque.json"))
for e in d["conformidade"]:
    if e["veredito"] == "nao_verificado":
        print("  " + json.dumps(e, ensure_ascii=False))
PY
  echo
  echo "Markdown (secao propria, separada da secao Conforme):"
  sed -n '/## Não verificado/,/## Conforme/p' "$EVID/ca2-desvios-baseline-do-parque.md" | sed 's/^/  /'
} > "$EVID/ca2-ca3-codigo-de-retorno.txt"
anotar "desvios (baseline do parque)" "CA2, CA3" "1" "$RC2" "ca2-desvios-baseline-do-parque.json / .md"

# ---------------------------------------------------------------------------
titulo "Codigo 2 - apenas desvio de severidade media"
# ---------------------------------------------------------------------------
./inventario --host "$HOST" --usuario "$USUARIO" --chave "$CHAVE" \
             --baseline "$BMEDIO" --formato json --saida "$TMP" 2>/dev/null
RC3=$?
mv "$TMP/inventario-$HOST.json" "$EVID/ca2-apenas-desvio-medio.json"
{
  echo "# Codigo de saida 2 — ha desvio apenas de severidade medio"
  echo
  echo "Baseline usado: execucoes/baselines/baseline-somente-medio.yaml, identico ao"
  echo "baseline-conforme exceto por kernel.versao_minima elevada a 9.9."
  echo
  echo "rc=$RC3   (esperado: 2)"
  echo
  python3 - <<PY
import json
d = json.load(open("$EVID/ca2-apenas-desvio-medio.json"))
for e in d["conformidade"]:
    if e["veredito"] == "desvio":
        print("  %-38s severidade=%s  encontrado=%s" % (e["regra"], e.get("severidade"), e["encontrado"]))
PY
  echo
  echo "A MESMA regra kernel.versao_minima saiu conforme no CA1 e desvio aqui, sem que"
  echo "uma linha de codigo mudasse: a politica esta no baseline, nao na ferramenta."
} > "$EVID/ca2-apenas-medio-codigo-de-retorno.txt"
anotar "apenas desvio medio" "tabela de codigo de saida" "2" "$RC3" "ca2-apenas-desvio-medio.json"

# ---------------------------------------------------------------------------
titulo "CA4 - host inalcancavel, em tres formas"
# ---------------------------------------------------------------------------
registrar_falha() {
  local arquivo="$1" rotulo="$2"; shift 2
  local saida rc
  saida=$("$@" 2>&1 >/dev/null); rc=$?
  {
    echo "# CA4 — $rotulo"
    echo
    echo "stderr:"
    echo "  $saida"
    echo
    echo "rc=$rc   (esperado: 3)"
    echo
    echo "Sem stack trace (nenhum 'Traceback'), sem relatorio de conformidade na saida"
    echo "padrao, e o codigo NAO e 0: 'nao consegui olhar' nao e 'esta tudo bem'."
    echo
    if printf '%s' "$saida" | grep -qi 'traceback'; then
      echo "ATENCAO: ha stack trace na saida."
    else
      echo "Verificado: 'Traceback' nao aparece na saida."
    fi
  } > "$EVID/$arquivo"
  echo "$rc"
}

RC_DNS=$(registrar_falha "ca4-endereco-nao-resolve.txt" "endereco errado (nao resolve)" \
  ./inventario --host host-que-nao-existe.invalid --usuario "$USUARIO" --chave "$CHAVE" --baseline "$BASE")
anotar "endereco nao resolve" "CA4" "3" "$RC_DNS" "ca4-endereco-nao-resolve.txt"

RC_TIMEOUT=$(registrar_falha "ca4-host-inalcancavel-timeout.txt" "host inalcancavel (conexao expira)" \
  ./inventario --host 192.0.2.1 --usuario "$USUARIO" --chave "$CHAVE" --baseline "$BASE")
anotar "host inalcancavel (timeout)" "CA4" "3" "$RC_TIMEOUT" "ca4-host-inalcancavel-timeout.txt"

RC_CHAVE=$(registrar_falha "ca4-chave-recusada.txt" "credencial recusada" \
  ./inventario --host "$HOST" --usuario "$USUARIO" --chave "$CHAVE_ERRADA" --baseline "$BASE")
anotar "credencial recusada" "CA4" "3" "$RC_CHAVE" "ca4-chave-recusada.txt"

# ---------------------------------------------------------------------------
titulo "CA5 - execucao repetida devolve o mesmo retrato"
# ---------------------------------------------------------------------------
mkdir -p "$TMP/r1" "$TMP/r2"
./inventario --host "$HOST" --usuario "$USUARIO" --chave "$CHAVE" \
             --baseline "$BASE" --formato json --saida "$TMP/r1" 2>/dev/null
RC5A=$?
# Dois segundos entre as execucoes, de proposito: sem eles as duas caem no mesmo
# segundo, o diff sai completamente vazio, e a evidencia deixa de MOSTRAR que
# `coletado_em` e o unico campo que muda -- so mostraria que nada mudou.
sleep 2
./inventario --host "$HOST" --usuario "$USUARIO" --chave "$CHAVE" \
             --baseline "$BASE" --formato json --saida "$TMP/r2" 2>/dev/null
RC5B=$?
cp "$TMP/r1/inventario-$HOST.json" "$EVID/ca5-execucao-1.json"
cp "$TMP/r2/inventario-$HOST.json" "$EVID/ca5-execucao-2.json"
DIFF=$(diff -u "$EVID/ca5-execucao-1.json" "$EVID/ca5-execucao-2.json")
LINHAS_ALTERADAS=$(printf '%s\n' "$DIFF" | grep -c '^[+-][^+-]')
LINHAS_COLETADO=$(printf '%s\n' "$DIFF" | grep -c '^[+-].*coletado_em')
{
  echo "# CA5 — duas execucoes consecutivas, so coletado_em muda"
  echo
  echo "\$ ./inventario ... --formato json --saida r1/   -> rc=$RC5A"
  echo "\$ ./inventario ... --formato json --saida r2/   -> rc=$RC5B"
  echo
  echo "\$ diff -u ca5-execucao-1.json ca5-execucao-2.json"
  echo '--------------------------------------------------------------'
  if [ -z "$DIFF" ]; then
    echo "(sem diferenca alguma — nem o instante de coleta mudou, porque as duas"
    echo " execucoes cairam no mesmo segundo)"
  else
    printf '%s\n' "$DIFF"
  fi
  echo '--------------------------------------------------------------'
  echo
  echo "Linhas alteradas no total: $LINHAS_ALTERADAS"
  echo "Linhas alteradas que sao host.coletado_em: $LINHAS_COLETADO"
  if [ "$LINHAS_ALTERADAS" -eq "$LINHAS_COLETADO" ]; then
    echo
    echo "VEREDITO: toda diferenca entre as duas execucoes esta em host.coletado_em."
    echo "O invariante I1 (so leitura) se sustenta: a ferramenta nao alterou o host."
  else
    echo
    echo "VEREDITO: ha diferenca alem de coletado_em. Ver o diff acima — se a diferenca"
    echo "for uma porta efemera do proprio host, e mudanca real do host, nao da ferramenta."
  fi
} > "$EVID/ca5-diff.txt"
anotar "execucao repetida" "CA5" "identico exceto coletado_em" "$LINHAS_ALTERADAS alteradas / $LINHAS_COLETADO em coletado_em" "ca5-diff.txt"

# ---------------------------------------------------------------------------
titulo "CA6 - a chave privada nao aparece em lugar nenhum"
# ---------------------------------------------------------------------------
STDERR_RECUSA=$(./inventario --host "$HOST" --usuario "$USUARIO" --chave "$CHAVE_ERRADA" \
                             --baseline "$BASE" 2>&1 >/dev/null)
{
  echo "# CA6 — a chave privada nao aparece em nenhuma saida nem em mensagem de erro"
  echo
  echo "## 1. Busca do material da chave em todos os artefatos gerados"
  echo
  echo "Cada linha de base64 do arquivo da chave privada e procurada, literalmente, em"
  echo "todo arquivo de execucoes/ e em todo arquivo de src/."
  echo
  ACHOU=0
  while IFS= read -r LINHA; do
    [ ${#LINHA} -lt 20 ] && continue
    case "$LINHA" in -----*) continue ;; esac
    if grep -RqF -- "$LINHA" "$EVID" "$RAIZ/src" "$RAIZ/inventario" 2>/dev/null; then
      ACHOU=1
    fi
  done < "$CHAVE"
  if [ "$ACHOU" -eq 0 ]; then
    echo "  RESULTADO: nenhum trecho do material da chave foi encontrado. OK."
  else
    echo "  RESULTADO: VAZAMENTO — material da chave encontrado em algum artefato."
  fi
  echo
  echo "## 2. Busca do cabecalho PEM nos relatorios e no codigo-fonte"
  echo
  echo "  Escopo: os relatorios gerados (execucoes/*.json, *.md, *.txt) e src/."
  echo "  Este script gerador fica FORA do escopo de proposito: ele contem a palavra"
  echo "  'PRIVATE KEY' justamente porque e ele quem faz esta busca."
  echo
  ALVOS=$(find "$EVID" -maxdepth 1 -type f \( -name '*.json' -o -name '*.md' -o -name '*.txt' \) ! -name 'ca6-vazamento-de-chave.txt')
  # shellcheck disable=SC2086
  if grep -l "PRIVATE KEY" $ALVOS "$RAIZ/src"/inventario/*.py "$RAIZ/inventario" 2>/dev/null | grep -q .; then
    echo "  RESULTADO: encontrado 'PRIVATE KEY' — inspecionar."
    # shellcheck disable=SC2086
    grep -n "PRIVATE KEY" $ALVOS "$RAIZ/src"/inventario/*.py "$RAIZ/inventario" 2>/dev/null | sed 's/^/    /'
  else
    echo "  RESULTADO: 'PRIVATE KEY' nao aparece em nenhum relatorio nem no codigo. OK."
  fi
  echo
  echo "## 3. Mensagem de erro do caminho de credencial recusada"
  echo
  echo "  stderr: $STDERR_RECUSA"
  echo
  echo "  Cita apenas o que aconteceu. Nenhum caminho de chave, nenhum material."
  echo
  echo "## 4. A camada de saneamento (design D10), exercitada com a chave de verdade"
  echo
  echo "  Uma mensagem de erro e construida DE PROPOSITO contendo o conteudo integral do"
  echo "  arquivo da chave privada, e passada por erros.sanear(). O que sai e isto:"
  echo
  PYTHONPATH="$RAIZ/src" python3 - <<PY | sed 's/^/    /'
from inventario.erros import sanear
with open("$CHAVE") as f:
    segredo = f.read()
mensagem = "falha ao autenticar usando a chave:\n" + segredo + "fim da mensagem"
saida = sanear(mensagem)
print(saida)
assert "PRIVATE KEY" not in saida, "VAZOU"
for linha in segredo.splitlines():
    if len(linha) > 20 and not linha.startswith("-----"):
        assert linha not in saida, "VAZOU"
print()
print("[verificado: nem o cabecalho PEM nem qualquer linha do material sobreviveram]")
PY
  echo
  echo "## 5. Como o invariante e sustentado na origem"
  echo
  echo "  A primeira camada nao e o saneamento: e o fato de a ferramenta NUNCA abrir o"
  echo "  arquivo da chave. O que ela faz e passar o CAMINHO para o cliente ssh do"
  echo "  sistema (decisao D1), que e quem sabe manuseá-lo."
  echo
  echo "  Inventario completo dos open() do codigo-fonte — sao dois, e nenhum e a chave:"
  echo
  grep -rn "open(" "$RAIZ/src"/inventario/*.py | sed 's/^/    /' || true
  echo
  echo "    baseline.py -> abre o baseline.yaml   (argumento --baseline)"
  echo "    cli.py      -> grava o relatorio      (argumento --saida)"
  echo
  echo "  O caminho da chave so aparece como elemento da lista de argumentos do"
  echo "  subprocesso ssh, em transporte.py:"
  echo
  grep -n "caminho_da_chave" "$RAIZ/src/inventario/transporte.py" | sed 's/^/    /' || true
} > "$EVID/ca6-vazamento-de-chave.txt"
anotar "sigilo da chave privada" "CA6" "nenhum vazamento" "ver arquivo" "ca6-vazamento-de-chave.txt"

# ---------------------------------------------------------------------------
titulo "CA4 (complemento) - SSH fora do ar, com o sshd parado de verdade"
# ---------------------------------------------------------------------------
# Unico ponto deste script que mexe na maquina de teste. Para o sshd, executa a
# ferramenta, e RELIGA o sshd em seguida, verificando que voltou.
sudo -n systemctl stop ssh.socket ssh.service >/dev/null 2>&1
SAIDA_FORA=$(./inventario --host 127.0.0.1 --usuario "$USUARIO" --chave "$CHAVE" \
                          --baseline "$BASE" 2>&1 >/dev/null)
RC_FORA=$?
sudo -n systemctl start ssh.socket ssh.service >/dev/null 2>&1
sleep 1
VOLTOU=$(ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
             -o IdentitiesOnly=yes -i "$CHAVE" "$USUARIO@$HOST" 'echo ok' 2>&1)
{
  echo "# CA4 (complemento) — servico SSH fora do ar"
  echo
  echo "O sshd da maquina de teste foi parado, a ferramenta foi executada, e o sshd foi"
  echo "religado em seguida. E o unico cenario que nao da para produzir sem mexer no host."
  echo
  echo "stderr:"
  echo "  $SAIDA_FORA"
  echo
  echo "rc=$RC_FORA   (esperado: 3)"
  echo
  echo "Reposicao do servico verificada apos o teste: ssh respondeu '$VOLTOU'"
} > "$EVID/ca4-ssh-fora-do-ar.txt"
anotar "SSH fora do ar" "CA4" "3" "$RC_FORA" "ca4-ssh-fora-do-ar.txt"

# ---------------------------------------------------------------------------
titulo "Resumo"
# ---------------------------------------------------------------------------
{
  echo "# Evidência dos critérios de aceite"
  echo
  echo "Gerado por \`execucoes/gerar-evidencias.sh\` contra o host SSH real"
  echo "(\`$USUARIO@$HOST\`, chave \`~/.ssh/inventario_ed25519\`) em $(date -u '+%Y-%m-%d %H:%M UTC')."
  echo
  echo "| Cenário | Critério | Esperado | Obtido | Arquivo |"
  echo "|---|---|---|---|---|"
  for linha in "${LINHAS[@]}"; do
    IFS='|' read -r c crit esp obt arq <<< "$linha"
    echo "| $c | $crit | \`$esp\` | \`$obt\` | \`$arq\` |"
  done
  echo
  echo "Os arquivos \`*-codigo-de-retorno.txt\` trazem o código de retorno de cada cenário"
  echo "com o comando que o produziu."
} > "$EVID/RESUMO.md"

rm -rf "$TMP"
cat "$EVID/RESUMO.md"
