#!/usr/bin/env python3
"""Retrato somente-leitura de um namespace, para triagem.

Junta numa passada o que a triagem sempre precisa e que, feito à mão, vira seis a
dez comandos digitados na pressa. Em especial traz o estado do container
(`waiting` e `lastState.terminated`), que é onde mora a causa de reinício e que
os eventos não revelam.

GARANTIA DE LEITURA: toda chamada passa por `_kubectl()`, que só aceita os verbos
em VERBOS_PERMITIDOS. Não há apply, create, patch, scale, delete, exec nem
port-forward em lugar nenhum — e é essa ausência, e não uma flag de servidor, que
sustenta a promessa de que a triagem não escreve no cluster.

Uso:
    python3 snapshot.py <namespace> [--contexto <ctx>]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone

VERBOS_PERMITIDOS = {"get"}


def _kubectl(verbo, *args, contexto=None, namespace=None):
    if verbo not in VERBOS_PERMITIDOS:
        raise RuntimeError(
            f"verbo '{verbo}' bloqueado: esta ferramenta é somente-leitura")
    cmd = ["kubectl"]
    if contexto:
        cmd += ["--context", contexto]
    if namespace:
        cmd += ["-n", namespace]
    cmd += [verbo, *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout, r.returncode


def obter_json(recurso, contexto, ns):
    saida, rc = _kubectl("get", recurso, "-o", "json", contexto=contexto, namespace=ns)
    if rc != 0 or not saida.strip():
        return []
    try:
        return json.loads(saida).get("items", [])
    except json.JSONDecodeError:
        return []


def secao(titulo, nota=None):
    print(f"\n--- {titulo} ---")
    if nota:
        print(f"({nota})")


def workloads(deploys):
    secao("1. WORKLOADS: prontos sobre desejados")
    if not deploys:
        print("  nenhum Deployment no namespace")
        return
    for d in deploys:
        st = d.get("status", {})
        desejado = d.get("spec", {}).get("replicas", 0)
        pronto = st.get("readyReplicas", 0)  # ausente quando nenhuma esta pronta
        print(f"  {d['metadata']['name']}: {pronto}/{desejado} prontos")
        for c in st.get("conditions", []):
            if c.get("status") != "True":
                print(f"    condicao {c.get('type')}=False  motivo={c.get('reason')}")
                if c.get("message"):
                    print(f"      {c['message']}")


def pods_e_containers(pods):
    secao("2. PODS e ESTADO DO CONTAINER",
          "a causa de reinicio vive aqui, nao nos eventos")
    if not pods:
        print("  nenhum pod no namespace")
        return
    for p in pods:
        m, st = p["metadata"], p.get("status", {})
        print(f"\n  pod {m['name']}  fase={st.get('phase')}")
        print(f"    rotulos: {m.get('labels', {})}")
        for cs in st.get("containerStatuses") or []:
            print(f"    container {cs['name']}  pronto={cs.get('ready')}  "
                  f"reinicios={cs.get('restartCount')}")
            esperando = (cs.get("state") or {}).get("waiting")
            if esperando:
                print(f"      ESPERANDO: {esperando.get('reason')}")
                if esperando.get("message"):
                    print(f"        {esperando['message']}")
            morto = (cs.get("lastState") or {}).get("terminated")
            if morto:
                print(f"      ULTIMA MORTE: {morto.get('reason')} "
                      f"exitCode={morto.get('exitCode')}")


def recursos(pods):
    secao("3. RECURSOS DECLARADOS",
          "compare com a causa da morte: OOMKilled aponta para limits.memory")
    vistos = set()
    for p in pods:
        dono = p["metadata"].get("generateName", p["metadata"]["name"])
        for c in p["spec"].get("containers", []):
            chave = (dono, c["name"])
            if chave in vistos:
                continue
            vistos.add(chave)
            r = c.get("resources") or {}
            print(f"  {c['name']}: {r if r else 'SEM requests/limits'}")


def eventos(evs):
    secao("4. EVENTOS", "Warning primeiro; nem toda causa aparece aqui")
    avisos = [e for e in evs if e.get("type") == "Warning"]
    avisos.sort(key=lambda e: e.get("lastTimestamp") or "")
    for e in avisos[-10:]:
        alvo = e.get("involvedObject", {}).get("name", "")
        print(f"  Warning {e.get('reason')}  {alvo}")
        print(f"    {e.get('message', '')}")
    if not avisos:
        print("  nenhum evento de Warning")


def rede(svcs, pods, eps):
    secao("5. REDE: Service, Endpoints e coerencia do selector",
          "campo de enderecos AUSENTE e diferente de lista vazia")
    for s in svcs:
        nome = s["metadata"]["name"]
        sel = s["spec"].get("selector")
        print(f"\n  service {nome}  tipo={s['spec'].get('type')}  selector={sel}")
        if not sel:
            print("    sem selector — endpoints gerenciados a mao")
            continue
        casam = [p for p in pods
                 if all(p["metadata"].get("labels", {}).get(k) == v
                        for k, v in sel.items())]
        if casam:
            print(f"    {len(casam)} pod(s) casam com o selector")
        else:
            print("    NENHUM pod casa com o selector -> Service sem endpoint")
            for p in pods:
                print(f"      candidato {p['metadata']['name']} "
                      f"tem rotulos {p['metadata'].get('labels', {})}")

    print()
    for e in eps:
        nome = e["metadata"]["name"]
        subsets = e.get("subsets")
        if not subsets:
            print(f"  endpoints {nome}: SEM o campo de enderecos")
        else:
            total = sum(len(s.get("addresses", [])) for s in subsets)
            print(f"  endpoints {nome}: {total} endereco(s)")


def saudaveis(pods):
    secao("6. O QUE ESTA SAUDAVEL AO LADO",
          "triagem se distingue de chute por saber o que NAO quebrou")
    algum = False
    for p in pods:
        st = p.get("status", {})
        cs = st.get("containerStatuses") or []
        if st.get("phase") == "Running" and cs and all(c.get("ready") for c in cs):
            print(f"  ok: {p['metadata']['name']}")
            algum = True
    if not algum:
        print("  nada saudavel neste namespace")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("namespace")
    ap.add_argument("--contexto", default=None)
    args = ap.parse_args()

    ns, ctx = args.namespace, args.contexto

    pods = obter_json("pods", ctx, ns)
    deploys = obter_json("deployments", ctx, ns)
    svcs = obter_json("services", ctx, ns)
    eps = obter_json("endpoints", ctx, ns)
    evs = obter_json("events", ctx, ns)

    if not any([pods, deploys, svcs]):
        sys.exit(f"erro: namespace '{ns}' vazio ou inacessivel")

    print("=" * 62)
    print(f" NAMESPACE: {ns}")
    print(f" coletado em: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print("=" * 62)

    workloads(deploys)
    pods_e_containers(pods)
    recursos(pods)
    eventos(evs)
    rede(svcs, pods, eps)
    saudaveis(pods)

    print("\n" + "=" * 62)
    print(" fim do retrato. nenhuma escrita foi feita no cluster.")
    print("=" * 62)


if __name__ == "__main__":
    main()
