"""Transporte SSH (decisao D1).

Uma unica sessao multiplexada (`ControlMaster`) por execucao, reaproveitada por todas as
sondas. O material da chave privada NUNCA entra neste processo: o que circula e o
caminho do arquivo, passado ao cliente `ssh` do sistema, que e quem sabe manuseá-lo.

O ponto que decide entre codigo de saida 3 e veredito `nao_verificado` esta aqui: se a
abertura da sessao mestre falha, e 3 e a execucao termina. Depois que a sessao esta de
pe, nenhuma falha de comando individual volta a ser 3 -- vira `nao_verificado`.
"""

import os
import shutil
import subprocess
import tempfile

from .erros import ErroDeConexao, ErroDeUso, sanear

# Opcoes fixas de D1, com o porque de cada uma registrado em 02-decisoes.md.
OPCOES_FIXAS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=10",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "IdentitiesOnly=yes",
]

# Classificacao do erro de handshake por reconhecimento de texto. E fragil, e e o preco
# de D1; por isso o processo filho roda com LC_ALL=C, para fixar o idioma das mensagens.
_DIAGNOSTICOS = [
    ("host key for", "a chave do host mudou desde a ultima conexao; conexao recusada por seguranca"),
    ("host identification has changed", "a chave do host mudou desde a ultima conexao; conexao recusada por seguranca"),
    ("permission denied", "credencial recusada pelo host"),
    ("too many authentication failures", "credencial recusada pelo host"),
    ("no such identity", "a chave informada nao pode ser usada pelo cliente ssh"),
    ("bad permissions", "a chave informada tem permissoes abertas demais e o cliente ssh a recusou"),
    ("connection refused", "o host respondeu, mas o servico SSH esta fora do ar (conexao recusada)"),
    ("connection timed out", "host inalcancavel: a conexao expirou"),
    ("operation timed out", "host inalcancavel: a conexao expirou"),
    ("name or service not known", "o endereco informado nao resolve"),
    ("could not resolve hostname", "o endereco informado nao resolve"),
    ("no route to host", "host inalcancavel: nao ha rota ate ele"),
    ("network is unreachable", "host inalcancavel: rede inacessivel"),
]


def _ambiente():
    """Ambiente do processo filho.

    LC_ALL=C fixa o idioma das mensagens do ssh, do qual o diagnostico depende.
    SSH_AUTH_SOCK e removido por coerencia com IdentitiesOnly=yes: sem isso o agente
    do operador pode autenticar com outra credencial e o resultado deixa de ser
    reproduzivel.
    """
    ambiente = dict(os.environ)
    ambiente.pop("SSH_AUTH_SOCK", None)
    ambiente["LC_ALL"] = "C"
    ambiente["LANG"] = "C"
    return ambiente


def _classificar(stderr):
    texto = (stderr or "").lower()
    for marcador, frase in _DIAGNOSTICOS:
        if marcador in texto:
            return frase
    bruto = " ".join(sanear(stderr or "").split())
    if bruto:
        return "falha ao abrir a sessao SSH: %s" % bruto
    return "falha ao abrir a sessao SSH, sem diagnostico do cliente ssh"


class Sessao:
    """Sessao SSH multiplexada. Use como context manager."""

    def __init__(self, host, usuario, caminho_da_chave):
        self.host = host
        self.usuario = usuario
        self.caminho_da_chave = caminho_da_chave
        self._dir_controle = None
        self._socket = None

    # -- ciclo de vida ----------------------------------------------------------

    def __enter__(self):
        self.abrir()
        return self

    def __exit__(self, *_):
        self.fechar()
        return False

    def _base(self):
        return [
            "ssh",
            *OPCOES_FIXAS,
            "-i", self.caminho_da_chave,
            "-o", "ControlPath=%s" % self._socket,
        ]

    def abrir(self):
        if shutil.which("ssh") is None:
            # Problema da maquina de quem opera, nao do host alvo: erro de uso (4).
            raise ErroDeUso("o cliente 'ssh' nao foi encontrado no PATH desta maquina")
        if not os.path.isfile(self.caminho_da_chave):
            raise ErroDeUso("chave privada nao encontrada: %s" % self.caminho_da_chave)

        self._dir_controle = tempfile.mkdtemp(prefix="inventario-ssh-")
        os.chmod(self._dir_controle, 0o700)
        self._socket = os.path.join(self._dir_controle, "controle")

        comando = [
            *self._base(),
            "-o", "ControlMaster=yes",
            "-o", "ControlPersist=60",
            "-N", "-f",
            "%s@%s" % (self.usuario, self.host),
        ]
        try:
            concluido = subprocess.run(
                comando,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env=_ambiente(),
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            self.fechar()
            raise ErroDeConexao("host inalcancavel: a abertura da sessao SSH expirou")

        if concluido.returncode != 0:
            causa = _classificar(concluido.stderr)
            self.fechar()
            raise ErroDeConexao(causa)

    def fechar(self):
        if self._socket and os.path.exists(self._socket):
            subprocess.run(
                [*self._base(), "-O", "exit", "%s@%s" % (self.usuario, self.host)],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env=_ambiente(),
            )
        if self._dir_controle and os.path.isdir(self._dir_controle):
            shutil.rmtree(self._dir_controle, ignore_errors=True)
        self._dir_controle = None
        self._socket = None

    # -- execucao ---------------------------------------------------------------

    def executar(self, comando_remoto):
        """Executa um comando de leitura no host e devolve (codigo, stdout, stderr).

        Nunca levanta excecao por falha do comando: falha de comando e insumo do
        veredito `nao_verificado` (D2), nao acidente.
        """
        try:
            concluido = subprocess.run(
                [*self._base(), "%s@%s" % (self.usuario, self.host), "--", comando_remoto],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env=_ambiente(),
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return 124, "", "tempo esgotado"
        except OSError as erro:
            return 127, "", str(erro)
        return concluido.returncode, concluido.stdout, concluido.stderr
