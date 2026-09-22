"""Erros da ferramenta e a camada de saneamento de mensagens.

Design D10: o invariante I2 (a chave privada e credencial, nao parametro) e facil de
sustentar no caminho feliz e facil de furar num `except` esquecido. Toda mensagem que
sai por stderr passa por `sanear`, que e a segunda camada de defesa -- nao substituto
de nunca ler o conteudo da chave, que e a primeira.
"""

import re

# Bloco PEM inteiro, em qualquer das formas que uma chave privada assume.
_PEM = re.compile(
    r"-----BEGIN[^-]*-----.*?-----END[^-]*-----",
    re.DOTALL,
)
# Linha solta de base64 longa, que e o que sobra de um PEM truncado.
_BASE64_LONGA = re.compile(r"^[A-Za-z0-9+/=]{60,}$", re.MULTILINE)

_MARCADOR = "[conteudo de chave removido]"


def sanear(texto):
    """Remove de `texto` qualquer coisa que se pareca com material de chave privada."""
    if not texto:
        return texto
    limpo = _PEM.sub(_MARCADOR, texto)
    limpo = _BASE64_LONGA.sub(_MARCADOR, limpo)
    return limpo


class ErroDeUso(Exception):
    """Baseline ausente, argumento invalido, dependencia local faltando. Codigo 4."""


class ErroDeConexao(Exception):
    """Host inalcancavel, credencial recusada ou SSH fora do ar. Codigo 3.

    Carrega `causa`, que e a frase em linguagem de operacao ja classificada pelo
    transporte, e nunca o stderr bruto do ssh sem saneamento.
    """

    def __init__(self, causa):
        super().__init__(causa)
        self.causa = causa
