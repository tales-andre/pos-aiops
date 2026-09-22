#!/usr/bin/env python3
"""Confere manifests Kubernetes contra as regras mecânicas do Padrão da Metacortex.

Cobre apenas o que se decide lendo o YAML. Regras que exigem conhecer a aplicação
(para onde a probe aponta, quais caminhos precisam ser graváveis, se o workload fala
com o apiserver) ficam fora daqui de propósito — elas são julgamento, não checagem.

Também ficam fora as regras que o `trivy config` já cobre (2.1, 3.1, 3.2, 3.6):
reimplementar isso seria manter duas verdades sobre a mesma regra.

Uso:
    python3 conferir_manifests.py <arquivo-ou-diretorio> [...]
    python3 conferir_manifests.py manifests/ --formato json

Saída: relatório por regra. Código de retorno 1 se algo barra, 0 caso contrário.
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("erro: este script precisa de PyYAML. Instale com: pip install pyyaml")

AMBIENTES = ("dev", "stg", "prod")
REGISTRY = "registry.metacortex.io"
ROTULOS = (
    "app.kubernetes.io/name",
    "app.kubernetes.io/instance",
    "app.kubernetes.io/part-of",
    "app.kubernetes.io/managed-by",
)
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Heurística para credencial embutida: URL com usuário:senha@, ou chave de env
# cujo nome sugere segredo e que traz valor literal.
URL_COM_SENHA = re.compile(r"//[^/\s:]+:[^/\s@]+@")
NOME_SENSIVEL = re.compile(r"(PASS|PASSWORD|SECRET|TOKEN|APIKEY|API_KEY|CREDENTIAL)", re.I)

CONTROLADORES = {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}


class Achado:
    def __init__(self, regra, forca, objeto, esperado, encontrado, veredito):
        self.regra = regra
        self.forca = forca
        self.objeto = objeto
        self.esperado = esperado
        self.encontrado = encontrado
        self.veredito = veredito

    def barra(self):
        return self.veredito == "barra"

    def como_dict(self):
        return {
            "regra": self.regra,
            "forca": self.forca,
            "objeto": self.objeto,
            "esperado": self.esperado,
            "encontrado": self.encontrado,
            "veredito": self.veredito,
        }


def carregar(caminhos):
    docs = []
    for bruto in caminhos:
        p = Path(bruto)
        arquivos = sorted(p.rglob("*.y*ml")) if p.is_dir() else [p]
        for arq in arquivos:
            try:
                conteudo = arq.read_text(encoding="utf-8")
            except OSError as e:
                print(f"aviso: não consegui ler {arq}: {e}", file=sys.stderr)
                continue
            for doc in yaml.safe_load_all(conteudo):
                if isinstance(doc, dict) and doc.get("kind"):
                    doc["__arquivo__"] = str(arq)
                    docs.append(doc)
    return docs


def identificar(doc):
    meta = doc.get("metadata") or {}
    return f"{doc.get('kind')}/{meta.get('name', '<sem nome>')}"


def ambiente_de(ns):
    if not ns:
        return None
    sufixo = ns.rsplit("-", 1)[-1]
    return sufixo if sufixo in AMBIENTES else None


def pod_spec(doc):
    """Devolve (labels_do_pod, spec_do_pod) do controlador, ou (None, None)."""
    kind = doc.get("kind")
    spec = doc.get("spec") or {}
    if kind == "CronJob":
        spec = ((spec.get("jobTemplate") or {}).get("spec")) or {}
    template = spec.get("template") or {}
    if not template:
        return None, None
    return (template.get("metadata") or {}).get("labels") or {}, template.get("spec") or {}


def containers_de(pspec):
    return (pspec.get("containers") or []) + (pspec.get("initContainers") or [])


def checar(docs):
    achados = []
    pods_por_ns = []  # (namespace, labels_do_pod, identificacao)

    for doc in docs:
        kind = doc.get("kind")
        meta = doc.get("metadata") or {}
        nome = meta.get("name") or ""
        ns = meta.get("namespace")
        alvo = identificar(doc)
        amb = ambiente_de(ns)

        # 1.1 — nome em kebab-case
        achados.append(Achado(
            "1.1 kebab-case", "obrigatório", alvo, "minúsculas com hífen", nome,
            "conforme" if KEBAB.match(nome) else "barra"))

        # 1.2 — namespace <cliente>-<ambiente>
        if kind == "Namespace":
            ns_alvo = nome
        else:
            ns_alvo = ns
        if ns_alvo:
            ok = amb is not None if kind != "Namespace" else ambiente_de(nome) is not None
            achados.append(Achado(
                "1.2 namespace <cliente>-<ambiente>", "obrigatório", alvo,
                "sufixo dev, stg ou prod", ns_alvo, "conforme" if ok else "barra"))

        # 1.3 — os quatro rótulos
        rotulos = meta.get("labels") or {}
        faltando = [r for r in ROTULOS if r not in rotulos]
        achados.append(Achado(
            "1.3 quatro rótulos", "obrigatório", alvo, "os quatro app.kubernetes.io",
            "completo" if not faltando else f"faltam {', '.join(faltando)}",
            "conforme" if not faltando else "barra"))

        labels_pod, pspec = pod_spec(doc)

        if kind in CONTROLADORES and labels_pod is not None:
            pods_por_ns.append((ns, labels_pod, alvo, kind,
                                (doc.get("spec") or {}).get("replicas")))

            # 1.4 — matchLabels idêntico aos rótulos do pod
            match = ((doc.get("spec") or {}).get("selector") or {}).get("matchLabels")
            if match is not None:
                igual = match == labels_pod
                achados.append(Achado(
                    "1.4 selector casa com o pod", "obrigatório", alvo,
                    "matchLabels idêntico aos rótulos do template",
                    "idêntico" if igual else f"matchLabels={match} pod={labels_pod}",
                    "conforme" if igual else "barra"))

            # 2.2 — presença das duas probes (para onde apontam é julgamento)
            if kind in ("Deployment", "StatefulSet", "DaemonSet"):
                for c in containers_de(pspec):
                    faltam = [p for p in ("readinessProbe", "livenessProbe") if p not in c]
                    achados.append(Achado(
                        "2.2 readiness e liveness", "obrigatório",
                        f"{alvo}/{c.get('name')}", "as duas declaradas",
                        "as duas" if not faltam else f"faltam {', '.join(faltam)}",
                        "conforme" if not faltam else "barra"))

            # 2.3 / 2.4 — só valem em prod
            if kind == "Deployment" and amb == "prod":
                replicas = (doc.get("spec") or {}).get("replicas")
                achados.append(Achado(
                    "2.3 replicas >= 2 em prod", "obrigatório", alvo, ">= 2", replicas,
                    "conforme" if isinstance(replicas, int) and replicas >= 2 else "barra"))

                estrategia = (doc.get("spec") or {}).get("strategy") or {}
                rolling = estrategia.get("rollingUpdate") or {}
                ok = (estrategia.get("type") == "RollingUpdate"
                      and rolling.get("maxUnavailable") == 0
                      and rolling.get("maxSurge") == 1)
                achados.append(Achado(
                    "2.4 estratégia de atualização", "obrigatório em prod", alvo,
                    "RollingUpdate, maxUnavailable 0, maxSurge 1",
                    estrategia or "ausente", "conforme" if ok else "barra"))

            # 3.4 — automount desligado (se fala com a API é julgamento)
            tem = pspec.get("automountServiceAccountToken")
            achados.append(Achado(
                "3.4 automountServiceAccountToken", "obrigatório", alvo, "false",
                tem if tem is not None else "ausente",
                "conforme" if tem is False else "barra"))

            # 3.5 — ServiceAccount dedicada
            sa = pspec.get("serviceAccountName")
            achados.append(Achado(
                "3.5 ServiceAccount dedicada", "recomendado", alvo, "SA própria",
                sa or "default", "conforme" if sa else "justificar"))

            for c in containers_de(pspec):
                ident = f"{alvo}/{c.get('name')}"

                # 3.7 — registry interno
                imagem = c.get("image") or ""
                achados.append(Achado(
                    "3.7 registry interno", "obrigatório", ident, REGISTRY, imagem,
                    "conforme" if imagem.startswith(REGISTRY + "/") else "barra"))

                # 3.3 — credencial em texto puro
                for env in c.get("env") or []:
                    valor = env.get("value")
                    if valor is None:
                        continue
                    texto = str(valor)
                    suspeito = bool(URL_COM_SENHA.search(texto)) or bool(
                        NOME_SENSIVEL.search(env.get("name", "")))
                    if suspeito:
                        achados.append(Achado(
                            "3.3 segredo em texto puro", "proibido", ident,
                            "secretKeyRef", f"{env.get('name')} com valor literal", "barra"))

    # 1.4 — do lado do Service, e 2.5 — PDB
    servicos = [d for d in docs if d.get("kind") == "Service"]
    for svc in servicos:
        sel = (svc.get("spec") or {}).get("selector")
        if not sel:
            continue
        ns = (svc.get("metadata") or {}).get("namespace")
        candidatos = [(lb, ident) for (n, lb, ident, _k, _r) in pods_por_ns if n == ns]
        identico = any(lb == sel for lb, _ in candidatos)
        casa = any(all(lb.get(k) == v for k, v in sel.items()) for lb, _ in candidatos)
        if identico:
            veredito, encontrado = "conforme", "idêntico"
        elif casa:
            veredito, encontrado = "barra", f"seleciona um subconjunto: {sel}"
        else:
            veredito, encontrado = "barra", f"nenhum pod casa com {sel} — Service sem endpoint"
        achados.append(Achado(
            "1.4 selector casa com o pod", "obrigatório", identificar(svc),
            "selector idêntico aos rótulos do pod", encontrado, veredito))

    pdbs = [d for d in docs if d.get("kind") == "PodDisruptionBudget"]
    for ns, labels_pod, ident, kind, replicas in pods_por_ns:
        # O padrão pede PDB para "workload de prod com mais de uma réplica".
        # Job e CronJob são execução finita — derrubá-los numa manutenção de nó
        # não causa indisponibilidade, então não entram.
        if ambiente_de(ns) != "prod" or kind in ("Job", "CronJob"):
            continue
        if not (isinstance(replicas, int) and replicas > 1):
            continue
        coberto = any(
            all(labels_pod.get(k) == v for k, v in
                (((p.get("spec") or {}).get("selector") or {}).get("matchLabels") or {}).items())
            for p in pdbs if (p.get("metadata") or {}).get("namespace") == ns)
        achados.append(Achado(
            "2.5 PodDisruptionBudget em prod", "recomendado", ident,
            "PDB cobrindo o workload", "existe" if coberto else "ausente",
            "conforme" if coberto else "justificar"))

    return achados


def relatorio(achados, formato):
    if formato == "json":
        print(json.dumps([a.como_dict() for a in achados], ensure_ascii=False, indent=2))
        return

    barram = [a for a in achados if a.barra()]
    justificar = [a for a in achados if a.veredito == "justificar"]
    conformes = [a for a in achados if a.veredito == "conforme"]

    if barram:
        print("BARRA\n")
        for a in barram:
            print(f"  [{a.regra}] ({a.forca}) {a.objeto}")
            print(f"    esperado:  {a.esperado}")
            print(f"    encontrado: {a.encontrado}\n")

    if justificar:
        print("JUSTIFICAR NO PR\n")
        for a in justificar:
            print(f"  [{a.regra}] {a.objeto} — esperado {a.esperado}, encontrado {a.encontrado}")
        print()

    print(f"Resumo: {len(barram)} barram, {len(justificar)} pedem justificativa, "
          f"{len(conformes)} conformes.")
    print("\nRegras 2.1, 3.1, 3.2 e 3.6 não são conferidas aqui — o catálogo do Trivy já as "
          "cobre. Rode: trivy config <caminho>")
    print("Regras que exigem ler o projeto (para onde a probe aponta, caminhos graváveis, "
          "dono, dimensionamento) não são mecânicas — veja o corpo da skill.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("caminhos", nargs="+", help="arquivos ou diretórios com manifests")
    ap.add_argument("--formato", choices=("texto", "json"), default="texto")
    args = ap.parse_args()

    docs = carregar(args.caminhos)
    if not docs:
        sys.exit("erro: nenhum manifesto encontrado nos caminhos informados")

    achados = checar(docs)
    relatorio(achados, args.formato)
    sys.exit(1 if any(a.barra() for a in achados) else 0)


if __name__ == "__main__":
    main()
