"""Linha de comando: reconstruir o índice e baixar o acervo do catálogo.

    python -m base_juridica.cli reconstruir-indice
    python -m base_juridica.cli baixar-acervo
"""

from __future__ import annotations

import argparse
import sys
import urllib.request

from .captura import CapturaFalhou, FonteNaoOficial
from .catalogo import CATALOGO, ReferenciaDesconhecida
from .config import load_config
from .indice import reconstruir
from .leis import baixar_lei
from .planalto import ParseVazio


def main(argv: list[str] | None = None, *, abrir=urllib.request.urlopen) -> int:
    parser = argparse.ArgumentParser(prog="base_juridica.cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("reconstruir-indice", help="refaz base/indice.sqlite a partir dos markdown")
    sub.add_parser("baixar-acervo", help="baixa todas as leis do catálogo e reconstrói o índice")
    args = parser.parse_args(argv)
    cfg = load_config()

    if args.comando == "reconstruir-indice":
        print(f"índice: {reconstruir(cfg)} itens")
        return 0

    falhas = 0
    for item in CATALOGO:
        try:
            doc = baixar_lei(cfg, item.id, abrir=abrir)
            print(f"ok {item.id} {len(doc.artigos)}")
        except (CapturaFalhou, ParseVazio, FonteNaoOficial, ReferenciaDesconhecida) as e:
            falhas += 1
            print(f"falhou {item.id} {e}")
        sys.stdout.flush()
    print(f"índice: {reconstruir(cfg)} itens")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
