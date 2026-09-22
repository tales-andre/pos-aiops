"""Linha de comando e orquestracao.

    inventario --host <endereco> --usuario <user> --chave <caminho>
               --baseline <caminho> [--formato json|markdown|ambos] [--saida <dir>]

Roda na maquina de quem opera. Nada e instalado, copiado ou executado com escrita no
host alvo.
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone

from . import baseline as mod_baseline
from . import sondas
from .conformidade import avaliar, codigo_de_saida, resumir
from .erros import ErroDeConexao, ErroDeUso, sanear
from .render import renderizar_json, renderizar_markdown
from .transporte import Sessao

FORMATOS = ("json", "markdown", "ambos")

CODIGO_ERRO_DE_USO = 4
CODIGO_INALCANCAVEL = 3


class _Parser(argparse.ArgumentParser):
    """argparse sai com 2 por conta propria; o contrato desta ferramenta diz 4."""

    def error(self, mensagem):
        raise ErroDeUso(mensagem)


def _construir_parser():
    parser = _Parser(
        prog="inventario",
        description="Coleta o inventario de um host Linux por SSH e o compara "
                    "contra um baseline declarado. Somente leitura.",
    )
    parser.add_argument("--host", required=True, metavar="<endereco>",
                        help="endereco do host a inventariar")
    parser.add_argument("--usuario", required=True, metavar="<user>",
                        help="usuario da coleta (comum, sem privilegio)")
    parser.add_argument("--chave", required=True, metavar="<caminho>",
                        help="CAMINHO da chave privada; o conteudo nunca e lido por esta ferramenta")
    parser.add_argument("--baseline", required=True, metavar="<caminho>",
                        help="caminho do baseline.yaml com o padrao esperado do parque")
    parser.add_argument("--formato", default="json", metavar="json|markdown|ambos",
                        help="formato da saida (padrao: json)")
    parser.add_argument("--saida", default=None, metavar="<dir>",
                        help="diretorio onde gravar o relatorio; sem ele, sai na saida padrao")
    return parser


def _validar(argumentos):
    if argumentos.formato not in FORMATOS:
        raise ErroDeUso("formato invalido: '%s' (use json, markdown ou ambos)"
                        % argumentos.formato)
    if argumentos.formato == "ambos" and not argumentos.saida:
        raise ErroDeUso("--formato ambos exige --saida: dois relatorios nao cabem "
                        "na mesma saida padrao sem quebrar o JSON")
    if not os.path.isfile(argumentos.chave):
        raise ErroDeUso("chave privada nao encontrada: %s" % argumentos.chave)
    if argumentos.saida and not os.path.isdir(argumentos.saida):
        raise ErroDeUso("diretorio de saida nao existe: %s" % argumentos.saida)


# ---------------------------------------------------------------------------
# Montagem do modelo
# ---------------------------------------------------------------------------


def _ou_nulo(resultado, chaves):
    """Dict do inventario: os valores coletados, ou as mesmas chaves com None."""
    if resultado.ok:
        return {chave: resultado.valor.get(chave) for chave in chaves}
    return {chave: None for chave in chaves}


def montar_inventario(resultados):
    ntp = _ou_nulo(resultados["ntp"], ["sincronizado"])
    ntp["mecanismo"] = sondas.mecanismo_de_tempo(resultados["servicos"])
    return {
        "so": _ou_nulo(resultados["so"], ["distribuicao", "versao"]),
        "kernel": _ou_nulo(resultados["kernel"], ["versao"]),
        "servicos": resultados["servicos"].valor if resultados["servicos"].ok else None,
        "swap": _ou_nulo(resultados["swap"], ["habilitado", "tamanho"]),
        "portas_em_escuta": (resultados["portas_em_escuta"].valor
                             if resultados["portas_em_escuta"].ok else None),
        "chaves_ssh": resultados["chaves_ssh"].valor if resultados["chaves_ssh"].ok else None,
        "ssh": _ou_nulo(resultados["ssh"], ["login_de_root"]),
        "ntp": ntp,
    }


def _agora_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def montar_relatorio(endereco, resultados, baseline):
    entradas = avaliar(resultados, baseline)
    return {
        "host": {
            "endereco": endereco,
            "hostname": resultados["hostname"].valor if resultados["hostname"].ok else None,
            "coletado_em": _agora_utc(),
        },
        "inventario": montar_inventario(resultados),
        "conformidade": entradas,
        "resumo": resumir(entradas),
    }


# ---------------------------------------------------------------------------
# Emissao
# ---------------------------------------------------------------------------


def _nome_de_arquivo(endereco, extensao):
    limpo = re.sub(r"[^A-Za-z0-9._-]", "_", endereco)
    return "inventario-%s.%s" % (limpo, extensao)


def emitir(relatorio, baseline, formato, diretorio):
    saidas = {}
    if formato in ("json", "ambos"):
        saidas["json"] = renderizar_json(relatorio)
    if formato in ("markdown", "ambos"):
        saidas["md"] = renderizar_markdown(
            relatorio,
            versao_do_baseline=baseline.versao,
            ordem_de_severidade=baseline.ordem_de_severidade,
        )

    if not diretorio:
        sys.stdout.write(saidas["json"] if "json" in saidas else saidas["md"])
        return []

    escritos = []
    for extensao, conteudo in sorted(saidas.items()):
        caminho = os.path.join(diretorio, _nome_de_arquivo(relatorio["host"]["endereco"], extensao))
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(conteudo)
        escritos.append(caminho)
    return escritos


def _erro(mensagem):
    # Toda escrita em stderr passa pelo saneamento (design D10).
    sys.stderr.write(sanear(mensagem).rstrip() + "\n")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def main(argv=None):
    argumentos = None
    try:
        argumentos = _construir_parser().parse_args(argv)
        _validar(argumentos)
        baseline = mod_baseline.carregar(argumentos.baseline)

        with Sessao(argumentos.host, argumentos.usuario, argumentos.chave) as sessao:
            resultados = sondas.coletar(sessao)

        relatorio = montar_relatorio(argumentos.host, resultados, baseline)
        escritos = emitir(relatorio, baseline, argumentos.formato, argumentos.saida)
        for caminho in escritos:
            sys.stderr.write("relatorio gravado em %s\n" % caminho)
        return codigo_de_saida(relatorio["conformidade"])

    except ErroDeUso as erro:
        _erro("erro de uso: %s" % erro)
        return CODIGO_ERRO_DE_USO
    except ErroDeConexao as erro:
        # Nao ha relatorio nesta saida, de proposito: pipeline que trata "nao
        # consegui olhar" como "esta tudo bem" e pior que pipeline nenhum.
        alvo = argumentos.host if argumentos else "o host"
        _erro("nao foi possivel inventariar %s: %s" % (alvo, erro.causa))
        return CODIGO_INALCANCAVEL
    except KeyboardInterrupt:
        _erro("execucao interrompida antes de produzir relatorio")
        return CODIGO_ERRO_DE_USO
    except Exception as erro:  # noqa: BLE001 - nenhum stack trace cru chega ao operador
        _erro("erro interno da ferramenta (%s: %s); nenhum relatorio foi produzido"
              % (type(erro).__name__, erro))
        return CODIGO_ERRO_DE_USO
