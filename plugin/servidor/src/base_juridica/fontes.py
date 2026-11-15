"""Classificação de fontes: oficial (vale como norma) ou comentário."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

# Domínios oficiais. Casa o hostname exato ou um subdomínio.
DOMINIOS_OFICIAIS = (
    "planalto.gov.br",
    "lexml.gov.br",
    "jus.br",
    "in.gov.br",
    "camara.leg.br",
    "senado.leg.br",
    "gov.br",
    "portal.cfm.org.br",
    "sistemas.cfm.org.br",
)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().rstrip(".")


def _casa(host: str, dominio: str) -> bool:
    return host == dominio or host.endswith("." + dominio)


def classificar_fonte(url: str) -> Literal["oficial", "comentario"]:
    host = _host(url)
    if host and any(_casa(host, d) for d in DOMINIOS_OFICIAIS):
        return "oficial"
    return "comentario"


def eh_jus_br(url: str) -> bool:
    return _casa(_host(url), "jus.br")
