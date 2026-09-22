"""Catalogo declarativo de sondas (decisao D4).

Cada sonda e um registro com identificador, o COMANDO REMOTO LITERAL, a funcao de
parsing e o motivo a usar quando falhar. O comando fica a vista na propria entrada: e o
que permite auditar em trinta segundos o que a ferramenta executou na maquina alheia.

Nenhum comando escreve. Nenhum usa sudo. Acrescentar um dado ao inventario e acrescentar
uma entrada aqui, nao mexer no fluxo de coleta.
"""

import re

# ---------------------------------------------------------------------------
# Resultado de uma sonda (decisao D2)
# ---------------------------------------------------------------------------


class SemDado(Exception):
    """O comando respondeu, mas a resposta nao permite concluir nada."""


class Resultado:
    """Ou ha valor e o motivo e vazio, ou o valor e None e ha motivo. Nao ha terceira forma.

    E a presenca de `motivo` -- nao uma checagem de None espalhada pelo avaliador -- que
    produz o veredito `nao_verificado`.
    """

    __slots__ = ("valor", "motivo")

    def __init__(self, valor=None, motivo=None):
        self.valor = valor
        self.motivo = motivo

    @property
    def ok(self):
        return self.motivo is None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _hostname(saida):
    nome = saida.strip().splitlines()[0].strip() if saida.strip() else ""
    if not nome:
        raise SemDado()
    return nome


def _os_release(saida):
    campos = {}
    for linha in saida.splitlines():
        chave, _, valor = linha.partition("=")
        if _:
            campos[chave.strip()] = valor.strip().strip('"')
    distribuicao = campos.get("ID")
    versao = campos.get("VERSION_ID")
    if not distribuicao and not versao:
        raise SemDado()
    return {"distribuicao": distribuicao or None, "versao": versao or None}


def _kernel(saida):
    versao = saida.strip()
    if not versao:
        raise SemDado()
    return {"versao": versao}


def _servicos(saida):
    """UNIT LOAD ACTIVE SUB DESCRIPTION.

    Unidades com LOAD=not-found sao referencias a coisas que nao estao instaladas;
    listá-las como servicos do host seria inventar inventario.
    """
    unidades = []
    for linha in saida.splitlines():
        partes = linha.split(None, 4)
        if len(partes) < 4:
            continue
        nome, carga, ativo = partes[0], partes[1], partes[2]
        if carga == "not-found":
            continue
        if "." not in nome:
            continue
        tipo = nome.rsplit(".", 1)[1]
        if tipo not in ("service", "socket"):
            continue
        unidades.append({"nome": nome, "tipo": tipo, "estado": ativo})
    if not unidades:
        raise SemDado()
    # D9: ordenacao estavel.
    unidades.sort(key=lambda u: u["nome"])
    return unidades


def _tamanho_legivel(kilobytes):
    valor = float(kilobytes)
    for unidade in ("K", "M", "G", "T"):
        if valor < 1024 or unidade == "T":
            texto = ("%.1f" % valor).rstrip("0").rstrip(".")
            return "%s%s" % (texto, unidade)
        valor /= 1024
    return "%dK" % kilobytes


def _swap(saida):
    """Cabecalho + uma linha por area de swap. Sem linha de dados, swap esta desligado."""
    linhas = [linha for linha in saida.splitlines() if linha.strip()]
    if not linhas:
        raise SemDado()
    dados = linhas[1:]  # a primeira linha e sempre o cabecalho
    if not dados:
        return {"habilitado": False, "tamanho": None}
    total = 0
    for linha in dados:
        partes = linha.split()
        if len(partes) >= 3 and partes[2].isdigit():
            total += int(partes[2])
    return {"habilitado": True, "tamanho": _tamanho_legivel(total) if total else None}


_PROCESSO = re.compile(r'users:\(\("([^"]+)"')


def _portas(saida):
    portas = []
    for linha in saida.splitlines():
        campos = linha.split()
        if len(campos) < 4:
            continue
        local = campos[3]
        if ":" not in local:
            continue
        bind, _, porta_texto = local.rpartition(":")
        if not porta_texto.isdigit():
            continue
        bind = bind.strip("[]")
        bind = bind.split("%", 1)[0]  # 127.0.0.53%lo -> 127.0.0.53
        achado = _PROCESSO.search(linha)
        portas.append({
            "porta": int(porta_texto),
            "bind": bind or "*",
            # Sem privilegio, `ss` nao mostra o dono de processo alheio. Vazio e honesto.
            "processo": achado.group(1) if achado else None,
        })
    if not portas:
        raise SemDado()
    portas.sort(key=lambda p: (p["porta"], p["bind"]))
    return portas


def _chaves_ssh(saida):
    """Le APENAS a identificacao (o comentario) de cada chave autorizada.

    O material da chave (o campo base64) e lido do arquivo remoto pelo `cat`, mas nunca
    e guardado no modelo nem chega a qualquer renderizador: o parser descarta o campo.
    """
    chaves = []
    for linha in saida.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        campos = linha.split(None, 2)
        if len(campos) < 2:
            continue
        identificacao = campos[2].strip() if len(campos) > 2 else None
        chaves.append({"identificacao": identificacao or None})
    if not chaves:
        raise SemDado()
    chaves.sort(key=lambda c: (c["identificacao"] or ""))
    return chaves


def _ssh_login_de_root(saida):
    """Configuracao EFETIVA, vinda de `sshd -T`, nao a escrita no arquivo.

    `no` e a unica forma que nao permite login de root. `prohibit-password` e
    `forced-commands-only` permitem -- com restricao, mas permitem.
    """
    for linha in saida.splitlines():
        chave, _, valor = linha.strip().partition(" ")
        if chave.lower() == "permitrootlogin":
            return {"login_de_root": valor.strip().lower() != "no"}
    raise SemDado()


def _ntp(saida):
    campos = {}
    for linha in saida.splitlines():
        chave, _, valor = linha.partition("=")
        if _:
            campos[chave.strip()] = valor.strip()
    if "NTPSynchronized" not in campos:
        raise SemDado()
    return {"sincronizado": campos["NTPSynchronized"].lower() == "yes"}


# ---------------------------------------------------------------------------
# O catalogo
# ---------------------------------------------------------------------------


class Sonda:
    __slots__ = ("nome", "comando", "parser", "motivo")

    def __init__(self, nome, comando, parser, motivo):
        self.nome = nome
        self.comando = comando
        self.parser = parser
        self.motivo = motivo


CATALOGO = [
    Sonda(
        "hostname",
        "hostname",
        _hostname,
        "o host nao respondeu ao comando de identificacao",
    ),
    Sonda(
        "so",
        "cat /etc/os-release",
        _os_release,
        "o host nao expoe /etc/os-release",
    ),
    Sonda(
        "kernel",
        "uname -r",
        _kernel,
        "nao foi possivel obter a versao do kernel em execucao",
    ),
    Sonda(
        "servicos",
        "systemctl list-units --type=service --type=socket --all --plain --no-legend --no-pager",
        _servicos,
        "nao foi possivel listar as unidades do systemd neste host",
    ),
    Sonda(
        "swap",
        "cat /proc/swaps",
        _swap,
        "nao foi possivel ler /proc/swaps",
    ),
    Sonda(
        "portas_em_escuta",
        "ss -H -ltnp",
        _portas,
        "nao foi possivel listar as portas em escuta (o comando 'ss' respondeu com erro)",
    ),
    Sonda(
        "chaves_ssh",
        "cat ~/.ssh/authorized_keys",
        _chaves_ssh,
        "nao foi possivel ler as chaves autorizadas do usuario da coleta",
    ),
    Sonda(
        "ssh",
        "sshd -T",
        _ssh_login_de_root,
        "exige privilegio que o usuario da coleta nao tem",
    ),
    Sonda(
        "ntp",
        "timedatectl show -p NTPSynchronized -p NTP",
        _ntp,
        "nao foi possivel consultar o estado de sincronismo do relogio",
    ),
]

# Daemons de tempo reconhecidos, para derivar `ntp.mecanismo` da lista de servicos ja
# coletada em vez de gastar mais um comando na maquina alheia.
DAEMONS_DE_TEMPO = (
    "systemd-timesyncd",
    "chrony",
    "chronyd",
    "ntp",
    "ntpd",
    "ntpsec",
    "openntpd",
)


def coletar(sessao):
    """Percorre o catalogo. Uma sonda que falha nao interrompe as seguintes (D2)."""
    resultados = {}
    for sonda in CATALOGO:
        codigo, stdout, _stderr = sessao.executar(sonda.comando)
        if codigo != 0:
            resultados[sonda.nome] = Resultado(motivo=sonda.motivo)
            continue
        try:
            resultados[sonda.nome] = Resultado(valor=sonda.parser(stdout))
        except SemDado:
            resultados[sonda.nome] = Resultado(motivo=sonda.motivo)
        except Exception:
            # Saida inesperada de um comando remoto nao pode derrubar a coleta inteira.
            resultados[sonda.nome] = Resultado(
                motivo="a resposta do host para '%s' nao pode ser interpretada" % sonda.comando
            )
    return resultados


def mecanismo_de_tempo(resultado_servicos):
    """Deriva o mecanismo de NTP da lista de servicos ja coletada."""
    if not resultado_servicos.ok:
        return None
    for unidade in resultado_servicos.valor:
        if unidade["tipo"] != "service" or unidade["estado"] != "active":
            continue
        base = unidade["nome"].rsplit(".", 1)[0]
        if base in DAEMONS_DE_TEMPO:
            return base
    return None
