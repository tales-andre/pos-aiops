"""Ponto de passagem para o apiserver do Kubernetes.

ESTE É O ÚNICO MÓDULO DO PROJETO QUE FALA COM O CLUSTER.

O invariante do dashboard é "somente leitura". Ele é verificável aqui e em nenhum
outro lugar: VERBOS_PERMITIDOS abaixo é a lista completa de operações que este
projeto sabe executar, e `ler()` é a única porta de saída. Qualquer verbo fora
dessa lista é recusado ANTES de existir tráfego de rede.

Se você está auditando este projeto quanto a risco de escrita em produção, leia
VERBOS_PERMITIDOS e `ler()`. É só isso. O teste `testes/test_invariante.py`
garante que nenhum outro módulo de src/ importe o cliente do Kubernetes.
"""

from __future__ import annotations

import os
import socket
import ssl
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import URLError

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException

# ---------------------------------------------------------------------------
# O INVARIANTE
# ---------------------------------------------------------------------------

#: Conjunto COMPLETO de verbos que este projeto pode executar contra o apiserver.
#: Todos são verbos de leitura. Nada aqui altera estado do cluster.
#: Escrita (create, update, patch, delete, deletecollection, scale, exec,
#: attach, portforward, eviction) é deliberadamente ausente e recusada em
#: tempo de execução por `ler()`.
VERBOS_PERMITIDOS = frozenset({"get", "list", "watch"})

#: Timeout curto para qualquer conversa com o apiserver. Sem isto, um cluster
#: fora do ar prende o servidor single-thread por minutos em vez de devolver
#: uma mensagem clara (ver design.md, Risks).
TIMEOUT_SEGUNDOS = 6


class VerboProibido(RuntimeError):
    """Levantada quando um caminho de código pede um verbo fora da lista."""


# ---------------------------------------------------------------------------
# Categorias de falha
# ---------------------------------------------------------------------------

CLUSTER_INALCANCAVEL = "cluster_inalcancavel"
CREDENCIAL_INVALIDA = "credencial_invalida"
PERMISSAO_NEGADA = "permissao_negada"
NAO_ENCONTRADO = "nao_encontrado"
FALHA_DESCONHECIDA = "falha_desconhecida"

#: Título de painel por categoria. `{r}` é o nome do recurso; as categorias de
#: ambiente não o usam, porque a causa não é do recurso — é do cluster ou da
#: credencial, e repetir o recurso ali só confunde quem lê a tela.
_TEXTO_CATEGORIA = {
    CLUSTER_INALCANCAVEL: "o cluster não respondeu",
    CREDENCIAL_INVALIDA: "a credencial não foi aceita",
    PERMISSAO_NEGADA: "sem permissão para ler {r}",
    NAO_ENCONTRADO: "{r} não existe neste cluster",
    FALHA_DESCONHECIDA: "falha ao ler {r}",
}


@dataclass(frozen=True)
class FalhaDeLeitura(Exception):
    """Falha classificada. É dado, não acidente: sobe até `coleta` e vira envelope."""

    categoria: str
    recurso: str
    mensagem: str

    def __str__(self) -> str:  # pragma: no cover - conveniência de depuração
        return f"[{self.categoria}] {self.recurso}: {self.mensagem}"


def texto_da_categoria(categoria: str, recurso: str) -> str:
    """Frase em linguagem clara para uma categoria, do jeito que vai à tela."""
    base = _TEXTO_CATEGORIA.get(categoria, _TEXTO_CATEGORIA[FALHA_DESCONHECIDA])
    return base.format(r=recurso)


def classificar(erro: BaseException, recurso: str) -> FalhaDeLeitura:
    """Traduz a exceção crua do cliente numa categoria nomeada.

    A ação de quem lê a tela é diferente em cada caso — por isso cluster fora do
    ar, credencial inválida e permissão negada nunca colapsam na mesma mensagem.
    """
    if isinstance(erro, FalhaDeLeitura):
        return erro

    if isinstance(erro, ApiException):
        status = erro.status
        detalhe = (erro.reason or "").strip() or f"HTTP {status}"
        if status in (401,):
            return FalhaDeLeitura(
                CREDENCIAL_INVALIDA,
                recurso,
                "a credencial do kubeconfig foi recusada pelo apiserver "
                f"({detalhe}). Renove o login e reinicie.",
            )
        if status in (403,):
            return FalhaDeLeitura(
                PERMISSAO_NEGADA,
                recurso,
                f"o contexto corrente não tem permissão de leitura em {recurso} ({detalhe}).",
            )
        if status == 404:
            return FalhaDeLeitura(
                NAO_ENCONTRADO,
                recurso,
                f"este cluster não expõe {recurso} ({detalhe}).",
            )
        if status in (0, 502, 503, 504):
            return FalhaDeLeitura(
                CLUSTER_INALCANCAVEL,
                recurso,
                f"o apiserver não completou a resposta ({detalhe}).",
            )
        return FalhaDeLeitura(
            FALHA_DESCONHECIDA, recurso, f"resposta inesperada do apiserver ({detalhe})."
        )

    # urllib3 embrulha o erro de rede; o nome da classe é o sinal mais estável
    # entre versões do cliente.
    nome = type(erro).__name__
    texto = str(erro)
    if nome in {"MaxRetryError", "NewConnectionError", "ConnectTimeoutError",
                "ReadTimeoutError", "ProtocolError", "TimeoutError"} or isinstance(
        erro, (socket.timeout, socket.gaierror, ConnectionError, URLError, OSError)
    ):
        return FalhaDeLeitura(
            CLUSTER_INALCANCAVEL,
            recurso,
            f"não foi possível estabelecer conexão com o apiserver ({nome}).",
        )
    if isinstance(erro, ssl.SSLError) or "certificate" in texto.lower():
        return FalhaDeLeitura(
            CREDENCIAL_INVALIDA,
            recurso,
            f"falha de TLS/certificado ao falar com o apiserver ({nome}).",
        )
    if isinstance(erro, ConfigException):
        return FalhaDeLeitura(
            CREDENCIAL_INVALIDA, recurso, f"kubeconfig inválido ou incompleto: {texto}"
        )
    return FalhaDeLeitura(FALHA_DESCONHECIDA, recurso, f"{nome}: {texto}")


# ---------------------------------------------------------------------------
# Contexto corrente
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Contexto:
    nome: str
    servidor: str
    kubeconfig: str
    erro: str | None = None
    #: namespace declarado no contexto corrente do kubeconfig, quando houver.
    #: É o recurso de última instância quando não se consegue LISTAR namespaces
    #: — uma credencial restrita costuma ler o próprio namespace e mais nada.
    namespace_padrao: str | None = None


def contexto_corrente() -> Contexto:
    """Lê contexto e endereço do kubeconfig, SEM falar com o cluster.

    Precisa funcionar com o cluster fora do ar: o cabeçalho da tela mostra para
    onde se está olhando mesmo quando não há resposta do outro lado.
    """
    caminho = os.environ.get("KUBECONFIG") or os.path.expanduser("~/.kube/config")
    try:
        contextos, atual = k8s_config.list_kube_config_contexts()
    except Exception as erro:  # noqa: BLE001 - qualquer falha vira contexto degradado
        return Contexto("(desconhecido)", "(desconhecido)", caminho, str(erro))

    nome = (atual or {}).get("name") or "(nenhum contexto corrente)"
    cluster_alvo = ((atual or {}).get("context") or {}).get("cluster")
    ns_padrao = ((atual or {}).get("context") or {}).get("namespace")

    # O endereço vem de reler o YAML: é o caminho que funciona mesmo quando o
    # cluster está fora do ar, porque não depende de nenhuma chamada de rede.
    servidor = "(desconhecido)"
    try:
        import yaml  # dependência já presente via cliente do Kubernetes

        for arquivo in caminho.split(os.pathsep):
            if not arquivo:
                continue
            try:
                with open(os.path.expanduser(arquivo), "r", encoding="utf-8") as fh:
                    doc = yaml.safe_load(fh) or {}
            except OSError:
                continue
            for entrada in doc.get("clusters") or []:
                if entrada.get("name") == cluster_alvo:
                    servidor = (entrada.get("cluster") or {}).get("server") or servidor
                    break
            if servidor != "(desconhecido)":
                break
    except Exception:  # noqa: BLE001 - servidor desconhecido não impede a tela
        pass

    del contextos
    return Contexto(nome, servidor, caminho, namespace_padrao=ns_padrao)


# ---------------------------------------------------------------------------
# A ÚNICA PORTA DE SAÍDA
# ---------------------------------------------------------------------------

_apis: dict[str, Any] = {}


def _api(qual: str) -> Any:
    if qual not in _apis:
        try:
            k8s_config.load_kube_config()
        except Exception as erro:  # noqa: BLE001
            raise classificar(erro, "kubeconfig") from erro
        conf = k8s_client.Configuration.get_default_copy()
        conf.retries = 0

        # Remendo de incompatibilidade DENTRO do cliente oficial (visto na
        # versão 36.0.0): `load_kube_config` grava o token em
        # `api_key["authorization"]`, mas `Configuration.auth_settings()`
        # procura por `api_key["BearerToken"]`. O resultado é o pior possível:
        # nenhum header Authorization é enviado, e o apiserver responde 403
        # como `system:anonymous` — ou seja, a falha se DISFARÇA de permissão
        # negada em vez de aparecer como credencial não enviada.
        # Sem isto, qualquer kubeconfig de token (ServiceAccount, e é o caso do
        # contexto de leitura restrita) lê o cluster inteiro como anônimo.
        if "authorization" in conf.api_key and "BearerToken" not in conf.api_key:
            conf.api_key["BearerToken"] = conf.api_key["authorization"]
            if "authorization" in conf.api_key_prefix:
                conf.api_key_prefix["BearerToken"] = conf.api_key_prefix["authorization"]

        api_client = k8s_client.ApiClient(configuration=conf)
        _apis["core"] = k8s_client.CoreV1Api(api_client)
        _apis["apps"] = k8s_client.AppsV1Api(api_client)
        _apis["discovery"] = k8s_client.DiscoveryV1Api(api_client)
    return _apis[qual]


def limpar_cache_de_conexao() -> None:
    """Descarta os clientes construídos (usado entre execuções de teste)."""
    _apis.clear()


def ler(verbo: str, recurso: str, chamada: Callable[..., Any], **kwargs: Any) -> Any:
    """Executa UMA operação de leitura contra o apiserver.

    Este é o único ponto do projeto que emite tráfego para o cluster.

    - `verbo` é validado contra VERBOS_PERMITIDOS ANTES de qualquer rede.
    - qualquer falha vira `FalhaDeLeitura` com categoria nomeada.
    """
    if verbo not in VERBOS_PERMITIDOS:
        raise VerboProibido(
            f"verbo '{verbo}' recusado: este projeto é somente leitura. "
            f"Permitidos: {sorted(VERBOS_PERMITIDOS)}"
        )
    kwargs.setdefault("_request_timeout", TIMEOUT_SEGUNDOS)
    try:
        return chamada(**kwargs)
    except Exception as erro:  # noqa: BLE001 - classificação é o contrato
        raise classificar(erro, recurso) from erro


# --- as leituras concretas, todas passando por `ler` -----------------------


def listar_namespaces() -> Any:
    return ler("list", "namespaces", _api("core").list_namespace)


def listar_deployments(ns: str) -> Any:
    return ler(
        "list", "deployments", _api("apps").list_namespaced_deployment, namespace=ns
    )


def listar_pods(ns: str) -> Any:
    return ler("list", "pods", _api("core").list_namespaced_pod, namespace=ns)


def listar_services(ns: str) -> Any:
    return ler("list", "services", _api("core").list_namespaced_service, namespace=ns)


def listar_endpointslices(ns: str) -> Any:
    return ler(
        "list",
        "endpointslices",
        _api("discovery").list_namespaced_endpoint_slice,
        namespace=ns,
    )


def listar_endpoints(ns: str) -> Any:
    """Alternativa de compatibilidade para cluster sem EndpointSlice (D5)."""
    return ler("list", "endpoints", _api("core").list_namespaced_endpoints, namespace=ns)


def listar_eventos(ns: str) -> Any:
    return ler("list", "events", _api("core").list_namespaced_event, namespace=ns)


def versao_do_servidor() -> Any:
    return ler("get", "version", k8s_client.VersionApi(_api("core").api_client).get_code)
