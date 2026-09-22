"""Leitura do baseline declarado.

O baseline e dado, nao codigo. A ferramenta le `esperado` (o que o parque deveria ser)
e `severidade` (a politica da casa). Design D8: a severidade de cada regra vem do indice
invertido construido aqui; nenhuma severidade e embutida no codigo.
"""

import os

import yaml

from .erros import ErroDeUso


class Baseline:
    def __init__(self, versao, esperado, severidade_por_regra, ordem_de_severidade):
        self.versao = versao
        self.esperado = esperado
        self._severidade_por_regra = severidade_por_regra
        self.ordem_de_severidade = ordem_de_severidade

    def severidade(self, regra):
        """Severidade declarada para a regra, ou None quando o baseline nao classifica.

        None nao e erro: a regra continua sendo desvio e aparece no relatorio. O que
        ela nao faz e promover o codigo de saida, porque a ferramenta nao tem opiniao
        sobre gravidade -- essa opiniao e do baseline.
        """
        return self._severidade_por_regra.get(regra)

    def tem(self, caminho):
        """Diz se o baseline declara a regra `grupo.campo`."""
        grupo, _, campo = caminho.partition(".")
        secao = self.esperado.get(grupo)
        return isinstance(secao, dict) and campo in secao

    def valor(self, caminho):
        grupo, _, campo = caminho.partition(".")
        return self.esperado.get(grupo, {}).get(campo)


def carregar(caminho):
    if not caminho:
        raise ErroDeUso("caminho do baseline nao informado")
    if not os.path.isfile(caminho):
        raise ErroDeUso("baseline nao encontrado: %s" % caminho)
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = yaml.safe_load(arquivo)
    except yaml.YAMLError as erro:
        raise ErroDeUso("baseline %s nao e YAML valido: %s" % (caminho, erro))
    except OSError as erro:
        raise ErroDeUso("baseline %s nao pode ser lido: %s" % (caminho, erro.strerror))

    if not isinstance(dados, dict):
        raise ErroDeUso("baseline %s nao contem um mapeamento no topo" % caminho)

    esperado = dados.get("esperado")
    if not isinstance(esperado, dict) or not esperado:
        raise ErroDeUso("baseline %s nao declara a secao 'esperado'" % caminho)

    severidade_declarada = dados.get("severidade") or {}
    if not isinstance(severidade_declarada, dict):
        raise ErroDeUso("baseline %s tem a secao 'severidade' em formato invalido" % caminho)

    # Indice invertido: severidade -> [regras] vira regra -> severidade.
    por_regra = {}
    for nome_severidade, regras in severidade_declarada.items():
        for regra in regras or []:
            por_regra[regra] = nome_severidade

    return Baseline(
        versao=dados.get("versao"),
        esperado=esperado,
        severidade_por_regra=por_regra,
        # A ordem de declaracao no YAML e a ordem de exibicao no Markdown.
        ordem_de_severidade=list(severidade_declarada.keys()),
    )
