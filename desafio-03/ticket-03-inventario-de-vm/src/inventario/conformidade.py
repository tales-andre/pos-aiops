"""Avaliacao de conformidade: uma entrada por regra do baseline, tres vereditos.

`conforme`       -- o encontrado satisfaz o esperado
`desvio`         -- o encontrado contraria o esperado; carrega `severidade`
`nao_verificado` -- o dado nao pode ser coletado; carrega `motivo`

O terceiro existe porque a coleta entra com usuario comum e parte do que o baseline pede
so se le com privilegio. Reportar isso como `conforme` seria falso negativo de auditoria.
"""

import ipaddress
import re

CONFORME = "conforme"
DESVIO = "desvio"
NAO_VERIFICADO = "nao_verificado"

# Do contrato de codigo de saida da spec de comportamento -- nao e politica de
# severidade, e a fronteira entre "acorda alguem" e "entra na fila".
SEVERIDADES_GRAVES = ("critico", "alto")


# ---------------------------------------------------------------------------
# Comparacao de versao (design D5)
# ---------------------------------------------------------------------------

_NUMEROS = re.compile(r"(\d+(?:\.\d+)*)")


def _tupla_de_versao(texto):
    """Extrai os componentes numericos iniciais. `6.6.87.2-microsoft-...` -> (6,6,87,2)."""
    if not texto:
        return None
    achado = _NUMEROS.match(str(texto).strip())
    if not achado:
        return None
    return tuple(int(parte) for parte in achado.group(1).split("."))


def _versao_atende(encontrada, minima):
    """None quando nao da para comparar -- e nesse caso a regra vira nao_verificado."""
    a, b = _tupla_de_versao(encontrada), _tupla_de_versao(minima)
    if a is None or b is None:
        return None
    tamanho = max(len(a), len(b))
    a = a + (0,) * (tamanho - len(a))
    b = b + (0,) * (tamanho - len(b))
    return a >= b


# ---------------------------------------------------------------------------
# Classificacao do endereco de bind (design D6)
# ---------------------------------------------------------------------------

PUBLICA, INTERNA, LOCAL = "publica", "interna", "local"


def faixa_do_bind(bind):
    if bind in ("*", "", "0.0.0.0", "::", "[::]"):
        return PUBLICA  # curinga: escuta em tudo que a maquina tiver
    try:
        endereco = ipaddress.ip_address(bind)
    except ValueError:
        return PUBLICA  # desconhecido e tratado como exposto, que e o lado seguro
    if endereco.is_loopback:
        return LOCAL
    if endereco.is_private or endereco.is_link_local:
        return INTERNA
    return PUBLICA


# ---------------------------------------------------------------------------
# Entradas de conformidade
# ---------------------------------------------------------------------------


def _conforme(regra, esperado, encontrado):
    return {"regra": regra, "esperado": esperado, "encontrado": encontrado,
            "veredito": CONFORME}


def _desvio(regra, esperado, encontrado, severidade):
    return {"regra": regra, "esperado": esperado, "encontrado": encontrado,
            "veredito": DESVIO, "severidade": severidade}


def _nao_verificado(regra, esperado, motivo):
    return {"regra": regra, "esperado": esperado, "encontrado": None,
            "veredito": NAO_VERIFICADO, "motivo": motivo}


def _julgar(regra, esperado, encontrado, satisfaz, severidade):
    if satisfaz:
        return _conforme(regra, esperado, encontrado)
    return _desvio(regra, esperado, encontrado, severidade)


# ---------------------------------------------------------------------------
# Regras. A ordem desta lista e a ordem de saida (design D9).
# ---------------------------------------------------------------------------


def _estado_da_unidade(unidades, nome):
    """Casa o nome do baseline (`ssh`) com a unidade do host (`ssh.service`)."""
    candidatos = [nome] if "." in nome else [nome + ".service", nome + ".socket"]
    for candidato in candidatos:
        for unidade in unidades:
            if unidade["nome"] == candidato:
                return unidade["estado"]
    return None


def _regra_so_distribuicao(regra, esperado, inv, sev):
    dado = inv["so"]
    if not dado.ok or not dado.valor.get("distribuicao"):
        return _nao_verificado(regra, esperado, dado.motivo or
                               "a distribuicao nao consta em /etc/os-release")
    encontrado = dado.valor["distribuicao"]
    return _julgar(regra, esperado, encontrado,
                   encontrado.lower() == str(esperado).lower(), sev)


def _regra_so_versao(regra, esperado, inv, sev):
    dado = inv["so"]
    if not dado.ok or not dado.valor.get("versao"):
        return _nao_verificado(regra, esperado, dado.motivo or
                               "a versao nao consta em /etc/os-release")
    encontrado = dado.valor["versao"]
    atende = _versao_atende(encontrado, esperado)
    if atende is None:
        return _nao_verificado(regra, esperado,
                               "a versao '%s' nao e comparavel numericamente" % encontrado)
    return _julgar(regra, esperado, encontrado, atende, sev)


def _regra_kernel_versao(regra, esperado, inv, sev):
    dado = inv["kernel"]
    if not dado.ok:
        return _nao_verificado(regra, esperado, dado.motivo)
    encontrado = dado.valor["versao"]
    atende = _versao_atende(encontrado, esperado)
    if atende is None:
        return _nao_verificado(regra, esperado,
                               "a versao '%s' nao e comparavel numericamente" % encontrado)
    return _julgar(regra, esperado, encontrado, atende, sev)


def _regra_servicos_ativos(regra, esperado, inv, sev):
    dado = inv["servicos"]
    if not dado.ok:
        return _nao_verificado(regra, esperado, dado.motivo)
    encontrado, tudo_ativo = [], True
    for nome in esperado or []:
        estado = _estado_da_unidade(dado.valor, nome)
        encontrado.append("%s: %s" % (nome, estado or "ausente"))
        if estado != "active":
            tudo_ativo = False
    return _julgar(regra, esperado, encontrado, tudo_ativo, sev)


def _regra_servicos_proibidos(regra, esperado, inv, sev):
    dado = inv["servicos"]
    if not dado.ok:
        return _nao_verificado(regra, esperado, dado.motivo)
    encontrado = []
    for nome in esperado or []:
        estado = _estado_da_unidade(dado.valor, nome)
        if estado == "active":
            encontrado.append("%s: %s" % (nome, estado))
    return _julgar(regra, esperado, encontrado, not encontrado, sev)


def _regra_swap(regra, esperado, inv, sev):
    dado = inv["swap"]
    if not dado.ok:
        return _nao_verificado(regra, esperado, dado.motivo)
    encontrado = dado.valor["habilitado"]
    return _julgar(regra, esperado, encontrado, encontrado == bool(esperado), sev)


def _regra_portas_publicas(regra, esperado, inv, sev):
    dado = inv["portas_em_escuta"]
    if not dado.ok:
        return _nao_verificado(regra, esperado, dado.motivo)
    permitidas = set(esperado or [])
    encontrado = [
        "%d em %s" % (p["porta"], p["bind"])
        for p in dado.valor
        if faixa_do_bind(p["bind"]) == PUBLICA and p["porta"] not in permitidas
    ]
    return _julgar(regra, esperado, encontrado, not encontrado, sev)


def _regra_portas_internas(regra, esperado, inv, sev):
    """Design D7: restricao de ESCOPO. Porta ausente nao tem o que reprovar aqui --
    a ausencia do servico ja e capturada por `servicos.ativos`."""
    dado = inv["portas_em_escuta"]
    if not dado.ok:
        return _nao_verificado(regra, esperado, dado.motivo)
    restritas = set(esperado or [])
    encontrado = [
        "%d em %s" % (p["porta"], p["bind"])
        for p in dado.valor
        if p["porta"] in restritas and faixa_do_bind(p["bind"]) == PUBLICA
    ]
    return _julgar(regra, esperado, encontrado, not encontrado, sev)


def _regra_chaves_ssh(regra, esperado, inv, sev):
    dado = inv["chaves_ssh"]
    if not dado.ok:
        return _nao_verificado(regra, esperado, dado.motivo)
    encontrado = [c["identificacao"] or "(sem identificacao)" for c in dado.valor]
    emissor = str(esperado)
    todas_da_plataforma = all(
        c["identificacao"] and emissor in c["identificacao"] for c in dado.valor
    )
    return _julgar(regra, esperado, encontrado, todas_da_plataforma, sev)


def _regra_ssh_login_de_root(regra, esperado, inv, sev):
    dado = inv["ssh"]
    if not dado.ok:
        return _nao_verificado(regra, esperado, dado.motivo)
    encontrado = dado.valor["login_de_root"]
    return _julgar(regra, esperado, encontrado, encontrado == bool(esperado), sev)


def _regra_ntp(regra, esperado, inv, sev):
    dado = inv["ntp"]
    if not dado.ok:
        return _nao_verificado(regra, esperado, dado.motivo)
    encontrado = dado.valor["sincronizado"]
    return _julgar(regra, esperado, encontrado, encontrado == bool(esperado), sev)


REGRAS = [
    ("so.distribuicao", _regra_so_distribuicao),
    ("so.versao_minima", _regra_so_versao),
    ("kernel.versao_minima", _regra_kernel_versao),
    ("servicos.ativos", _regra_servicos_ativos),
    ("servicos.proibidos", _regra_servicos_proibidos),
    ("swap.habilitado", _regra_swap),
    ("portas_em_escuta.publicas_permitidas", _regra_portas_publicas),
    ("portas_em_escuta.somente_rede_interna", _regra_portas_internas),
    ("chaves_ssh.emitidas_por", _regra_chaves_ssh),
    ("ssh.login_de_root", _regra_ssh_login_de_root),
    ("ntp.sincronizado", _regra_ntp),
]


def avaliar(resultados, baseline):
    """Uma entrada por regra que o baseline declara. Regra nao declarada nao e avaliada."""
    entradas = []
    for regra, avaliador in REGRAS:
        if not baseline.tem(regra):
            continue
        entradas.append(
            avaliador(regra, baseline.valor(regra), resultados, baseline.severidade(regra))
        )
    return entradas


def resumir(entradas):
    resumo = {CONFORME: 0, DESVIO: 0, NAO_VERIFICADO: 0}
    por_severidade = {}
    for entrada in entradas:
        resumo[entrada["veredito"]] += 1
        if entrada["veredito"] == DESVIO:
            chave = entrada.get("severidade") or "sem_severidade"
            por_severidade[chave] = por_severidade.get(chave, 0) + 1
    resumo["por_severidade"] = por_severidade
    return resumo


def codigo_de_saida(entradas):
    """0 sem desvio, 1 com desvio grave, 2 com desvio apenas nao-grave.

    `nao_verificado` sozinho NAO promove o codigo: um host sem desvios e com regras
    nao verificadas termina com 0.
    """
    desvios = [e for e in entradas if e["veredito"] == DESVIO]
    if not desvios:
        return 0
    if any(e.get("severidade") in SEVERIDADES_GRAVES for e in desvios):
        return 1
    return 2
