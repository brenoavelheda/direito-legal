"""Tipos compartilhados entre os módulos do servidor."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Redacao:
    """Redação que deixou de valer.

    alterado_por: lei que a substituiu (texto da nota do Planalto).
    data: quando deixou de valer; só o ano é conhecido -> date(ano, 1, 1).
    """

    texto: str
    alterado_por: str | None
    data: date | None


@dataclass
class Marco:
    """Dispositivo vigente incluído ou alterado em `ano` (nota do Planalto).

    rotulo: "caput", "§1o", "x-", "parágrafoúnico"… (planalto.rotulo).
    tipo: "incluido" ou "redacao".
    """

    rotulo: str
    tipo: str
    ano: int


@dataclass
class Artigo:
    numero: str
    texto: str
    revogado: bool = False
    notas: list[str] = field(default_factory=list)
    redacoes_anteriores: list[Redacao] = field(default_factory=list)
    marcos: list[Marco] = field(default_factory=list)


@dataclass
class LeiDoc:
    id: str
    apelidos: list[str]
    titulo: str
    url: str
    capturado_em: datetime
    sha256: str
    artigos: list[Artigo]


@dataclass
class PrecedenteDoc:
    id: str
    tribunal: str
    tipo: str
    numero: str
    enunciado: str
    estado: str
    url: str
    capturado_em: datetime
    sha256: str | None
    conferido: bool


@dataclass
class Captura:
    url: str
    html: str
    sha256: str
    capturado_em: datetime
