#!/usr/bin/env python3
"""Verificação do invariante de somente-leitura (critério de aceite 9).

Três provas, todas mecânicas:

1. `acesso.py` é o ÚNICO módulo de src/ que importa o cliente `kubernetes`.
2. `VERBOS_PERMITIDOS` contém apenas verbos de leitura.
3. `acesso.ler()` recusa verbo de escrita ANTES de qualquer tráfego de rede.
4. O servidor HTTP implementa apenas `do_GET`.

Roda sem cluster. `python3 testes/test_invariante.py`.
"""

from __future__ import annotations

import ast
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(RAIZ, "src")
sys.path.insert(0, SRC)

VERBOS_DE_ESCRITA = [
    "create", "update", "patch", "delete", "deletecollection",
    "scale", "exec", "attach", "portforward", "replace", "apply", "evict",
]

falhas: list[str] = []
ok: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    (ok if condicao else falhas).append(descricao + (f" — {detalhe}" if detalhe and not condicao else ""))


# --- 1. um único módulo importa o cliente --------------------------------

def modulos_que_importam_kubernetes() -> list[str]:
    encontrados = []
    for dirpath, _dirnames, nomes in os.walk(SRC):
        for nome in nomes:
            if not nome.endswith(".py"):
                continue
            caminho = os.path.join(dirpath, nome)
            with open(caminho, "r", encoding="utf-8") as fh:
                arvore = ast.parse(fh.read(), filename=caminho)
            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    if any(a.name.split(".")[0] == "kubernetes" for a in no.names):
                        encontrados.append(os.path.relpath(caminho, RAIZ))
                elif isinstance(no, ast.ImportFrom):
                    if (no.module or "").split(".")[0] == "kubernetes":
                        encontrados.append(os.path.relpath(caminho, RAIZ))
    return sorted(set(encontrados))


importadores = modulos_que_importam_kubernetes()
checar(
    importadores == [os.path.join("src", "acesso.py")],
    "apenas src/acesso.py importa o cliente kubernetes",
    f"importadores encontrados: {importadores}",
)

# --- 2. verbos permitidos ------------------------------------------------

import acesso  # noqa: E402

checar(
    acesso.VERBOS_PERMITIDOS == frozenset({"get", "list", "watch"}),
    f"VERBOS_PERMITIDOS = {sorted(acesso.VERBOS_PERMITIDOS)} (somente leitura)",
    f"encontrado {sorted(acesso.VERBOS_PERMITIDOS)}",
)
checar(
    not (acesso.VERBOS_PERMITIDOS & set(VERBOS_DE_ESCRITA)),
    "nenhum verbo de escrita está na lista de permitidos",
)

# --- 3. ler() recusa escrita antes de qualquer rede ----------------------


class ChamadaProibida(Exception):
    pass


def jamais(**_kwargs):
    raise ChamadaProibida("houve tráfego de rede para um verbo de escrita!")


for verbo in VERBOS_DE_ESCRITA:
    try:
        acesso.ler(verbo, "pods", jamais)
        checar(False, f"ler('{verbo}', ...) recusado", "não levantou exceção")
    except acesso.VerboProibido:
        checar(True, f"ler('{verbo}', ...) recusado antes de qualquer rede")
    except ChamadaProibida as erro:
        checar(False, f"ler('{verbo}', ...) recusado", str(erro))

# --- 4. o servidor só implementa do_GET ----------------------------------

with open(os.path.join(SRC, "dashboard.py"), "r", encoding="utf-8") as fh:
    arvore = ast.parse(fh.read())
metodos_http = sorted(
    n.name
    for cls in ast.walk(arvore)
    if isinstance(cls, ast.ClassDef)
    for n in cls.body
    if isinstance(n, ast.FunctionDef) and n.name.startswith("do_")
)
checar(
    metodos_http == ["do_GET"],
    f"o servidor HTTP implementa apenas {metodos_http}",
    f"encontrado {metodos_http}",
)

# --- resultado -----------------------------------------------------------

print("INVARIANTE DE SOMENTE-LEITURA — verificação mecânica")
print("=" * 60)
for linha in ok:
    print(f"  [OK]    {linha}")
for linha in falhas:
    print(f"  [FALHA] {linha}")
print("=" * 60)
print(f"{len(ok)} verificações passaram, {len(falhas)} falharam.")
sys.exit(1 if falhas else 0)
