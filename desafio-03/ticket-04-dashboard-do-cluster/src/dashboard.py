#!/usr/bin/env python3
"""Dashboard do cluster — retrato somente-leitura do contexto corrente.

Uso:
    dashboard [--porta 8700]

Sem argumento de cluster e sem argumento de contexto, por desenho: a aplicação
lê o `current-context` do kubeconfig e pronto. Trocar de cluster é trocar o
contexto por fora e reiniciar. Um seletor de cluster na tela é um botão que,
num momento de pressa, aponta a pessoa para produção achando que é staging.

Este módulo NÃO importa o cliente do Kubernetes. Só `coleta`, que por sua vez
só fala com o cluster através de `acesso.ler()`. Ver `acesso.py`.

Só `do_GET` é implementado: qualquer outro método HTTP recebe 501 do próprio
BaseHTTPRequestHandler.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acesso  # noqa: E402  (importado só para exibir o invariante na subida)
import coleta  # noqa: E402

RAIZ_UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")

_TIPOS = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


class Manipulador(BaseHTTPRequestHandler):
    server_version = "dashboard-cluster/1.0"

    # Somente leitura também no HTTP: nenhum do_POST/do_PUT/do_PATCH/do_DELETE.

    def do_GET(self) -> None:  # noqa: N802 - assinatura da stdlib
        url = urlparse(self.path)
        rota = url.path

        if rota in ("/", "/index.html"):
            return self._estatico("index.html")
        if rota.startswith("/ui/"):
            return self._estatico(rota[len("/ui/"):])
        if rota == "/api/contexto":
            return self._json(coleta.contexto())
        if rota == "/api/snapshot":
            ns = (parse_qs(url.query).get("ns") or [None])[0]
            return self._json(coleta.snapshot(ns))
        if rota == "/healthz":
            return self._json({"ok": True})
        self._erro(404, "rota não encontrada")

    # -- auxiliares --------------------------------------------------------

    def _json(self, dados: dict, status: int = 200) -> None:
        corpo = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _estatico(self, relativo: str) -> None:
        seguro = os.path.normpath(relativo).lstrip("/\\")
        caminho = os.path.join(RAIZ_UI, seguro)
        if not os.path.abspath(caminho).startswith(os.path.abspath(RAIZ_UI)):
            return self._erro(403, "caminho fora da interface")
        if not os.path.isfile(caminho):
            return self._erro(404, "arquivo não encontrado")
        with open(caminho, "rb") as fh:
            corpo = fh.read()
        ext = os.path.splitext(caminho)[1]
        self.send_response(200)
        self.send_header("Content-Type", _TIPOS.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, status: int, texto: str) -> None:
        self._json({"ok": False, "erro": texto}, status=status)

    def log_message(self, formato: str, *args) -> None:  # noqa: A002
        sys.stderr.write("%s - %s\n" % (self.address_string(), formato % args))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dashboard",
        description="Retrato somente-leitura do contexto corrente do kubeconfig.",
    )
    parser.add_argument(
        "--porta", type=int, default=8700, help="porta de escuta (padrão: 8700)"
    )
    args = parser.parse_args(argv)

    # Lido sem falar com o cluster: precisa funcionar com o apiserver fora do ar.
    ctx = coleta.contexto()
    print(f"contexto corrente : {ctx['contexto']}", file=sys.stderr)
    print(f"servidor          : {ctx['servidor']}", file=sys.stderr)
    print(f"kubeconfig        : {ctx['kubeconfig']}", file=sys.stderr)
    print(f"somente leitura   : verbos {sorted(acesso.VERBOS_PERMITIDOS)}", file=sys.stderr)
    print(f"servindo em       : http://127.0.0.1:{args.porta}/", file=sys.stderr)

    servidor = HTTPServer(("127.0.0.1", args.porta), Manipulador)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrando.", file=sys.stderr)
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
