"""Os dois renderizadores.

Um unico modelo de dados em memoria, dois renderizadores sobre ele: e assim que as duas
saidas nao podem divergir. JSON porque o Roster vai consumir automaticamente; Markdown
porque o plantao le no terminal as tres da manha.
"""

import json

from .conformidade import CONFORME, DESVIO, NAO_VERIFICADO

# O baseline usa chaves sem acento; o relatorio para humano leva acento.
_ROTULO_DE_SEVERIDADE = {
    "critico": "crítico",
    "alto": "alto",
    "medio": "médio",
    "baixo": "baixo",
}


def renderizar_json(relatorio):
    # sort_keys=True faz parte do determinismo exigido pelo invariante I1.
    return json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def _celula(valor):
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (list, tuple)):
        if not valor:
            return "—"
        return ", ".join(_celula(item) for item in valor)
    return str(valor).replace("|", "\\|")


def _encontrado_legivel(entrada, inventario):
    """Enriquece a coluna `Encontrado` com o que o inventario ja sabe.

    O caso que motiva isto e o swap: `true` sozinho diz menos que `true (2G)`, e o
    tamanho ja esta no inventario -- nao ha coleta extra nem dado novo.
    """
    valor = entrada.get("encontrado")
    if entrada["regra"] == "swap.habilitado" and valor is True:
        tamanho = (inventario.get("swap") or {}).get("tamanho")
        if tamanho:
            return "true (%s)" % tamanho
    return _celula(valor)


def _ordem_das_severidades(entradas, ordem_do_baseline):
    vistas = []
    for nome in ordem_do_baseline:
        if any(e.get("severidade") == nome for e in entradas):
            vistas.append(nome)
    for entrada in entradas:
        severidade = entrada.get("severidade")
        if severidade and severidade not in vistas:
            vistas.append(severidade)
    if any(not e.get("severidade") for e in entradas):
        vistas.append(None)
    return vistas


def renderizar_markdown(relatorio, versao_do_baseline=None, ordem_de_severidade=()):
    host = relatorio["host"]
    inventario = relatorio.get("inventario") or {}
    entradas = relatorio["conformidade"]
    resumo = relatorio["resumo"]

    titulo_host = host.get("hostname") or host["endereco"]
    instante = (host.get("coletado_em") or "").replace("T", " ").replace("Z", " UTC")
    linha_baseline = (" · baseline v%s" % versao_do_baseline) if versao_do_baseline else ""

    linhas = [
        "# Inventário — %s (%s)" % (titulo_host, host["endereco"]),
        "Coletado em %s%s" % (instante, linha_baseline),
        "",
        "Resumo: **%d conforme · %d desvio · %d não verificado**"
        % (resumo[CONFORME], resumo[DESVIO], resumo[NAO_VERIFICADO]),
        "",
    ]

    desvios = [e for e in entradas if e["veredito"] == DESVIO]
    linhas.append("## Desvios")
    linhas.append("")
    if not desvios:
        linhas.append("Nenhum desvio.")
    else:
        linhas.append("| Severidade | Regra | Esperado | Encontrado |")
        linhas.append("|---|---|---|---|")
        for severidade in _ordem_das_severidades(desvios, ordem_de_severidade):
            for entrada in desvios:
                if entrada.get("severidade") != severidade:
                    continue
                rotulo = _ROTULO_DE_SEVERIDADE.get(severidade, severidade or "sem severidade")
                linhas.append("| %s | %s | %s | %s |" % (
                    rotulo,
                    entrada["regra"],
                    _celula(entrada["esperado"]),
                    _encontrado_legivel(entrada, inventario),
                ))
    linhas.append("")

    nao_verificados = [e for e in entradas if e["veredito"] == NAO_VERIFICADO]
    linhas.append("## Não verificado")
    linhas.append("")
    if not nao_verificados:
        linhas.append("Nada ficou sem verificação.")
    else:
        linhas.append("| Regra | Motivo |")
        linhas.append("|---|---|")
        for entrada in nao_verificados:
            linhas.append("| %s | %s |" % (entrada["regra"], _celula(entrada.get("motivo"))))
    linhas.append("")

    conformes = [e["regra"] for e in entradas if e["veredito"] == CONFORME]
    linhas.append("## Conforme")
    linhas.append("")
    linhas.append(" · ".join(conformes) if conformes else "Nenhuma regra conforme.")
    linhas.append("")

    return "\n".join(linhas)
