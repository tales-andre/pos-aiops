"""Monta o retrato ("snapshot") do cluster e normaliza as armadilhas da API.

Este módulo NÃO importa o cliente do Kubernetes. Todo acesso passa por
`acesso.ler()`. Ver `acesso.py` para o invariante de somente-leitura.

As três armadilhas tratadas aqui, todas do mesmo tipo — a API responde por
OMISSÃO em vez de por valor vazio:

1. Pod em CrashLoopBackOff continua com `phase: Running`. O estado exibido vem
   de `containerStatuses`, nunca de `phase`.
2. Deployment sem réplica pronta NÃO traz `readyReplicas`. Ausência é lida
   como zero, para que `0/3` apareça em vez de campo em branco.
3. Service sem endpoint não traz o campo de endereços vazio — não traz o campo.
   Ausência e lista vazia colapsam em "sem endpoint"; falha de leitura NUNCA
   vira "sem endpoint".
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import acesso

#: Precedência de motivos de espera que indicam falha, para ordenar os pods.
_ESTADOS_DE_FALHA = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "CreateContainerError",
    "InvalidImageName",
    "RunContainerError",
    "OOMKilled",
    "Error",
}


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


def _envelope(recurso: str, coletor: Callable[[], list[dict[str, Any]]]) -> dict[str, Any]:
    """Executa um coletor e embrulha o resultado OU a falha classificada.

    É isto que permite degradação parcial: um 403 em `services` produz um
    envelope de falha naquele painel e não toca nos outros.
    """
    try:
        return {"ok": True, "recurso": recurso, "itens": coletor()}
    except acesso.FalhaDeLeitura as falha:
        return {
            "ok": False,
            "recurso": recurso,
            "categoria": falha.categoria,
            "titulo": acesso.texto_da_categoria(falha.categoria, recurso),
            "mensagem": falha.mensagem,
        }
    except Exception as erro:  # noqa: BLE001 - nada sobe para a interface
        falha = acesso.classificar(erro, recurso)
        return {
            "ok": False,
            "recurso": recurso,
            "categoria": falha.categoria,
            "titulo": acesso.texto_da_categoria(falha.categoria, recurso),
            "mensagem": falha.mensagem,
        }


def _idade(instante: Any) -> str:
    if not instante:
        return "-"
    try:
        agora = datetime.now(timezone.utc)
        delta = agora - instante.replace(tzinfo=instante.tzinfo or timezone.utc)
        segundos = int(delta.total_seconds())
    except Exception:  # noqa: BLE001
        return "-"
    if segundos < 0:
        segundos = 0
    if segundos < 60:
        return f"{segundos}s"
    if segundos < 3600:
        return f"{segundos // 60}m"
    if segundos < 86400:
        return f"{segundos // 3600}h"
    return f"{segundos // 86400}d"


# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------


def _coletar_namespaces() -> list[dict[str, Any]]:
    lista = acesso.listar_namespaces()
    itens = []
    for ns in lista.items or []:
        itens.append(
            {
                "nome": ns.metadata.name,
                "fase": (ns.status.phase if ns.status else None) or "-",
                "idade": _idade(ns.metadata.creation_timestamp),
            }
        )
    itens.sort(key=lambda i: i["nome"])
    return itens


# ---------------------------------------------------------------------------
# Deployments — ARMADILHA 2
# ---------------------------------------------------------------------------


def _coletar_deployments(ns: str) -> list[dict[str, Any]]:
    lista = acesso.listar_deployments(ns)
    itens = []
    for dep in lista.items or []:
        status = dep.status
        spec = dep.spec

        # ARMADILHA 2: `readyReplicas` NÃO vem quando é zero. `None` e `0`
        # precisam colapsar no mesmo valor exibido, senão a tela mostra branco.
        prontos = getattr(status, "ready_replicas", None) or 0
        desejados = getattr(spec, "replicas", None)
        if desejados is None:
            desejados = 0
        disponiveis = getattr(status, "available_replicas", None) or 0
        atualizados = getattr(status, "updated_replicas", None) or 0

        itens.append(
            {
                "nome": dep.metadata.name,
                "prontos": prontos,
                "desejados": desejados,
                "texto": f"{prontos}/{desejados}",
                "saudavel": desejados > 0 and prontos == desejados,
                "disponiveis": disponiveis,
                "atualizados": atualizados,
                "idade": _idade(dep.metadata.creation_timestamp),
                "imagens": [
                    c.image for c in (spec.template.spec.containers or []) if c.image
                ]
                if spec and spec.template and spec.template.spec
                else [],
            }
        )
    itens.sort(key=lambda i: (i["saudavel"], i["nome"]))
    return itens


# ---------------------------------------------------------------------------
# Pods — ARMADILHA 1
# ---------------------------------------------------------------------------


def _estado_do_container(cs: Any) -> tuple[str, str | None]:
    """Devolve (estado, motivo) a partir do status de UM container.

    ARMADILHA 1: `phase` mente. Um pod em CrashLoopBackOff tem
    `phase: Running`. O estado real está em `containerStatuses`:

      - `state.waiting.reason`     -> CrashLoopBackOff, ImagePullBackOff, ...
      - `state.terminated.reason`  -> Completed, Error, OOMKilled
      - `lastState.terminated.reason` -> POR QUE ele caiu da última vez.
        É daqui que sai `OOMKilled`, que NÃO aparece em `state.waiting.reason`
        (lá está apenas `CrashLoopBackOff`). Sem este campo, a tela diz que o
        pod reinicia mas não diz por quê — que é a informação que resolve a
        triagem.
    """
    estado = cs.state
    motivo_anterior = None
    ultimo = getattr(cs, "last_state", None)
    if ultimo is not None and getattr(ultimo, "terminated", None) is not None:
        term = ultimo.terminated
        partes = []
        if term.reason:
            partes.append(term.reason)
        if term.exit_code is not None and term.reason != "Completed":
            partes.append(f"exit {term.exit_code}")
        if partes:
            motivo_anterior = " / ".join(partes)

    if estado is not None and getattr(estado, "waiting", None) is not None:
        razao = estado.waiting.reason or "Waiting"
        return razao, motivo_anterior or (estado.waiting.message or None)
    if estado is not None and getattr(estado, "terminated", None) is not None:
        term = estado.terminated
        razao = term.reason or "Terminated"
        detalhe = None
        if term.exit_code is not None and razao != "Completed":
            detalhe = f"exit {term.exit_code}"
        return razao, detalhe or motivo_anterior
    if estado is not None and getattr(estado, "running", None) is not None:
        if not cs.ready:
            return "Running (não pronto)", motivo_anterior
        return "Running", motivo_anterior
    return "Desconhecido", motivo_anterior


def _coletar_pods(ns: str) -> list[dict[str, Any]]:
    lista = acesso.listar_pods(ns)
    itens = []
    for pod in lista.items or []:
        status = pod.status
        estados = list(getattr(status, "container_statuses", None) or [])
        reinicios = sum((cs.restart_count or 0) for cs in estados)
        prontos = sum(1 for cs in estados if cs.ready)
        total = len(pod.spec.containers or []) if pod.spec else len(estados)

        estado_exibido = None
        motivo = None
        for cs in estados:
            e, m = _estado_do_container(cs)
            if e in _ESTADOS_DE_FALHA or e.startswith("Running (não"):
                estado_exibido, motivo = e, m
                break
            if estado_exibido is None:
                estado_exibido, motivo = e, m

        if estado_exibido is None:
            # Sem containerStatuses ainda (Pending). Aí sim `phase` é o que há,
            # e vem qualificada com o motivo do agendamento quando existir.
            estado_exibido = (status.phase if status else None) or "Desconhecido"
            cond = [
                c
                for c in (getattr(status, "conditions", None) or [])
                if c.type == "PodScheduled" and c.status != "True"
            ]
            if cond:
                motivo = cond[0].reason or cond[0].message

        em_falha = estado_exibido in _ESTADOS_DE_FALHA or estado_exibido.startswith(
            "Running (não"
        )
        itens.append(
            {
                "nome": pod.metadata.name,
                "estado": estado_exibido,
                "motivo": motivo,
                "reinicios": reinicios,
                "prontos": f"{prontos}/{total}",
                "fase_api": (status.phase if status else None) or "-",
                "no": (pod.spec.node_name if pod.spec else None) or "-",
                "idade": _idade(pod.metadata.creation_timestamp),
                "em_falha": em_falha,
            }
        )
    itens.sort(key=lambda i: (not i["em_falha"], i["nome"]))
    return itens


# ---------------------------------------------------------------------------
# Services + endpoints — ARMADILHA 3 (D5: EndpointSlice primeiro)
# ---------------------------------------------------------------------------


def _contagem_por_service(ns: str) -> tuple[dict[str, int], str]:
    """Agrega endereços prontos por Service.

    D5: EndpointSlice é a fonte, e um Service pode ter VÁRIAS slices — então
    "tem endpoint?" é agregação, não leitura. `Endpoints` é a alternativa de
    compatibilidade para cluster antigo.

    ARMADILHA 3: em ambas as fontes, `addresses` pode vir AUSENTE (None) em vez
    de lista vazia. `or []` colapsa os dois casos em zero endereços — que é
    "sem endpoint", e nunca "não consegui ler". Se a leitura falhar, a exceção
    sobe e vira envelope de falha, preservando essa distinção.
    """
    contagem: dict[str, int] = {}
    try:
        slices = acesso.listar_endpointslices(ns)
        for fatia in slices.items or []:
            rotulos = (fatia.metadata.labels or {}) if fatia.metadata else {}
            nome = rotulos.get("kubernetes.io/service-name")
            if not nome:
                continue
            contagem.setdefault(nome, 0)
            for ep in fatia.endpoints or []:
                condicoes = getattr(ep, "conditions", None)
                pronto = True if condicoes is None else (condicoes.ready is not False)
                if pronto:
                    contagem[nome] += len(ep.addresses or [])
        return contagem, "EndpointSlice"
    except acesso.FalhaDeLeitura as falha:
        if falha.categoria not in (acesso.NAO_ENCONTRADO,):
            raise
    # Cluster sem EndpointSlice: cai para Endpoints.
    eps = acesso.listar_endpoints(ns)
    for ep in eps.items or []:
        nome = ep.metadata.name
        total = 0
        for sub in ep.subsets or []:
            total += len(sub.addresses or [])
        contagem[nome] = total
    return contagem, "Endpoints"


def _coletar_services(ns: str) -> list[dict[str, Any]]:
    lista = acesso.listar_services(ns)
    contagem, fonte = _contagem_por_service(ns)
    itens = []
    for svc in lista.items or []:
        nome = svc.metadata.name
        spec = svc.spec
        portas = []
        for p in (spec.ports or []) if spec else []:
            texto = f"{p.port}"
            if p.target_port is not None and str(p.target_port) != str(p.port):
                texto += f"->{p.target_port}"
            if p.protocol and p.protocol != "TCP":
                texto += f"/{p.protocol}"
            portas.append(texto)
        tipo = (spec.type if spec else None) or "ClusterIP"
        n = contagem.get(nome, 0)
        itens.append(
            {
                "nome": nome,
                "tipo": tipo,
                "portas": portas,
                "endpoints": n,
                "sem_endpoint": n == 0 and tipo != "ExternalName",
                "fonte_endpoint": fonte,
                "selector": (spec.selector or {}) if spec else {},
                "idade": _idade(svc.metadata.creation_timestamp),
            }
        )
    itens.sort(key=lambda i: (not i["sem_endpoint"], i["nome"]))
    return itens


# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------


def _coletar_eventos(ns: str) -> list[dict[str, Any]]:
    lista = acesso.listar_eventos(ns)
    itens = []
    for ev in lista.items or []:
        quando = (
            getattr(ev, "last_timestamp", None)
            or getattr(ev, "event_time", None)
            or getattr(ev, "first_timestamp", None)
            or ev.metadata.creation_timestamp
        )
        alvo = getattr(ev, "involved_object", None)
        objeto = "-"
        if alvo is not None:
            objeto = f"{alvo.kind or '?'}/{alvo.name or '?'}"
        itens.append(
            {
                "tipo": ev.type or "Normal",
                "motivo": ev.reason or "-",
                "objeto": objeto,
                "mensagem": (ev.message or "").strip(),
                "idade": _idade(quando),
                "contagem": getattr(ev, "count", None) or 1,
                "_ordem": quando.timestamp() if quando else 0,
            }
        )
    # Warning primeiro; dentro de cada grupo, o mais recente antes.
    itens.sort(key=lambda i: (i["tipo"] != "Warning", -i["_ordem"]))
    for i in itens:
        i.pop("_ordem", None)
    return itens[:60]


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def contexto() -> dict[str, Any]:
    ctx = acesso.contexto_corrente()
    return {
        "contexto": ctx.nome,
        "servidor": ctx.servidor,
        "kubeconfig": ctx.kubeconfig,
        "namespace_padrao": ctx.namespace_padrao,
        "erro": ctx.erro,
    }


def snapshot(namespace: str | None = None) -> dict[str, Any]:
    """Retrato do cluster agora. Nunca levanta: falha vira envelope."""
    retrato: dict[str, Any] = {
        "lido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "namespace": namespace,
        **contexto(),
    }
    retrato["namespaces"] = _envelope("namespaces", _coletar_namespaces)

    if not namespace:
        # Sem namespace escolhido, tenta o primeiro que não seja de sistema.
        env = retrato["namespaces"]
        if env["ok"]:
            candidatos = [
                i["nome"]
                for i in env["itens"]
                if not i["nome"].startswith(("kube-", "local-path"))
                and i["nome"] != "default"
            ]
            namespace = candidatos[0] if candidatos else (
                env["itens"][0]["nome"] if env["itens"] else None
            )
        else:
            # Não conseguiu LISTAR namespaces. Isso não significa que não se
            # possa LER dentro de um: uma credencial restrita costuma enxergar
            # apenas o próprio namespace, e ele está declarado no contexto do
            # kubeconfig. Sem esta queda, um 403 em `namespaces` derrubaria
            # todos os painéis — exatamente o comportamento ingênuo que a
            # especificação proíbe.
            namespace = retrato.get("namespace_padrao")
        retrato["namespace"] = namespace

    if namespace:
        retrato["deployments"] = _envelope(
            "deployments", lambda: _coletar_deployments(namespace)
        )
        retrato["pods"] = _envelope("pods", lambda: _coletar_pods(namespace))
        retrato["services"] = _envelope("services", lambda: _coletar_services(namespace))
        retrato["eventos"] = _envelope("events", lambda: _coletar_eventos(namespace))
    else:
        # Sem namespace para ler. A mensagem tem que dizer a causa REAL: se a
        # listagem de namespaces falhou por cluster fora do ar, repetir essa
        # falha nos demais painéis é honesto; inventar "nenhum namespace
        # selecionado" esconderia o motivo e enganaria quem lê a tela.
        origem = retrato["namespaces"]
        if not origem["ok"]:
            base = {k: origem[k] for k in ("ok", "categoria", "titulo", "mensagem")}
        else:
            base = {
                "ok": False,
                "categoria": acesso.FALHA_DESCONHECIDA,
                "titulo": "nenhum namespace para ler",
                "mensagem": (
                    "o cluster não tem namespace visível para esta credencial e o "
                    "contexto do kubeconfig não declara um namespace padrão."
                ),
            }
        for chave in ("deployments", "pods", "services", "eventos"):
            retrato[chave] = dict(base, recurso=chave)

    return retrato
