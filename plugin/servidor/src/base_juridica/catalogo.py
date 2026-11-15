"""Catálogo das leis da v1a e resolução de referências para ids.

Id de lei: `lei-<número sem pontos>-<ano com 4 dígitos>`; decreto-lei vira
`dl-…`, lei complementar `lc-…`, decreto `dec-…`. A Constituição é `cf-1988`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

PLANALTO = "https://www.planalto.gov.br/ccivil_03/"


class ReferenciaDesconhecida(Exception):
    """A referência não corresponde a nenhuma lei conhecida nem ao padrão Lei N/AAAA."""


@dataclass(frozen=True)
class CatalogoItem:
    id: str
    apelidos: list[str] = field(hash=False)
    titulo: str
    url: str


def _item(id_: str, apelidos: list[str], titulo: str, caminho: str) -> CatalogoItem:
    return CatalogoItem(id_, apelidos, titulo, PLANALTO + caminho)


# Códigos e LINDB apontam para a página não compilada: a compilada omite o
# texto riscado e, com ele, as redações anteriores.
CATALOGO: list[CatalogoItem] = [
    _item("cf-1988", ["CF", "CF/88", "CF/1988", "CRFB", "CRFB/88", "Constituição", "Constituição Federal"],
          "Constituição da República Federativa do Brasil de 1988", "constituicao/constituicao.htm"),
    _item("lei-10406-2002", ["CC", "CC/2002", "Código Civil"],
          "Lei nº 10.406, de 10 de janeiro de 2002 (Código Civil)", "leis/2002/l10406.htm"),
    _item("lei-13105-2015", ["CPC", "CPC/2015", "Código de Processo Civil"],
          "Lei nº 13.105, de 16 de março de 2015 (Código de Processo Civil)",
          "_ato2015-2018/2015/lei/l13105.htm"),
    _item("lei-8078-1990", ["CDC", "Código de Defesa do Consumidor"],
          "Lei nº 8.078, de 11 de setembro de 1990 (Código de Defesa do Consumidor)", "leis/l8078.htm"),
    _item("dl-4657-1942", ["LINDB", "Lei de Introdução às Normas do Direito Brasileiro"],
          "Decreto-Lei nº 4.657, de 4 de setembro de 1942 (Lei de Introdução às Normas do Direito Brasileiro)",
          "decreto-lei/del4657.htm"),
    _item("lei-8245-1991", ["Lei do Inquilinato"],
          "Lei nº 8.245, de 18 de outubro de 1991 (Lei do Inquilinato)", "leis/l8245.htm"),
    _item("dl-911-1969", ["Lei da Alienação Fiduciária"],
          "Decreto-Lei nº 911, de 1º de outubro de 1969 (alienação fiduciária)",
          "decreto-lei/1965-1988/del0911.htm"),
    _item("lei-10931-2004", ["Lei da CCB", "Lei da Cédula de Crédito Bancário"],
          "Lei nº 10.931, de 2 de agosto de 2004 (patrimônio de afetação; Cédula de Crédito Bancário)",
          "_ato2004-2006/2004/lei/l10.931.htm"),
    _item("lei-8009-1990", ["Lei do bem de família"],
          "Lei nº 8.009, de 29 de março de 1990 (impenhorabilidade do bem de família)", "leis/l8009.htm"),
    _item("lei-9099-1995", ["Lei dos Juizados", "Lei dos Juizados Especiais", "LJE"],
          "Lei nº 9.099, de 26 de setembro de 1995 (Juizados Especiais Cíveis e Criminais)", "leis/l9099.htm"),
    _item("lei-10259-2001", ["Lei dos JEFs", "Lei dos Juizados Especiais Federais"],
          "Lei nº 10.259, de 12 de julho de 2001 (Juizados Especiais Federais)", "leis/leis_2001/l10259.htm"),
    _item("lei-8906-1994", ["Estatuto da OAB", "EAOAB", "Estatuto da Advocacia"],
          "Lei nº 8.906, de 4 de julho de 1994 (Estatuto da Advocacia e da OAB)", "leis/l8906.htm"),
]

RE_ID = re.compile(r"^(?:(?:lei|dl|lc|dec)-\d+-\d{4}|cf-1988)$")

_TIPOS = {"lei": "lei", "lei complementar": "lc", "decreto-lei": "dl", "decreto lei": "dl", "dl": "dl", "lc": "lc",
          "decreto": "dec"}
RE_REF = re.compile(
    r"^(?P<tipo>lei complementar|lei|decreto-lei|decreto lei|decreto|dl|lc)\s*"
    r"(?:n(?:o|º|°|\.)*\s*)?"
    r"(?P<num>\d{1,3}(?:\.?\d{3})*)"
    r"(?:\s*/\s*(?P<ano2>\d{2}|\d{4})"
    r"|\s*,\s*de\s+(?:\d{1,2}\s*(?:o|º|°)?\s+de\s+[a-zç]+\s+de\s+)?(?P<ano4>\d{4}))?"
    r"(?:\s*\(.*\))?$"
)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento.casefold().replace("\xa0", " ")).strip()


def _chave(texto: str) -> str:
    # º e ° somem no NFKD/ASCII; o "o" ordinal (Nº → "no") fica.
    return _normalizar(texto.replace("º", "o").replace("°", "o"))


_POR_APELIDO: dict[str, str] = {}
for _i in CATALOGO:
    for _a in [_i.id, *_i.apelidos]:
        _POR_APELIDO[_chave(_a)] = _i.id


def _ano(ano2: str | None, ano4: str | None) -> int | None:
    if ano4:
        return int(ano4)
    if ano2 is None:
        return None
    if len(ano2) == 4:
        return int(ano2)
    n = int(ano2)
    return 1900 + n if n > 30 else 2000 + n


def item_do_catalogo(id_: str) -> CatalogoItem | None:
    return next((i for i in CATALOGO if i.id == id_), None)


def item_por_url(url: str) -> CatalogoItem | None:
    def chave(u: str) -> str:
        return re.sub(r"^https?://(www\.)?", "", u.strip().casefold())

    alvo = chave(url)
    return next((i for i in CATALOGO if chave(i.url) == alvo), None)


def resolver_referencia(ref: str) -> str:
    chave = _chave(ref)
    if chave in _POR_APELIDO:
        return _POR_APELIDO[chave]
    if RE_ID.match(chave):
        return chave
    m = RE_REF.match(chave)
    if not m:
        raise ReferenciaDesconhecida(f"referência não reconhecida: {ref!r}")
    prefixo = _TIPOS[m.group("tipo")]
    numero = m.group("num").replace(".", "")
    ano = _ano(m.group("ano2"), m.group("ano4"))
    if ano is not None:
        return f"{prefixo}-{numero}-{ano}"
    candidatos = [i.id for i in CATALOGO if i.id.startswith(f"{prefixo}-{numero}-")]
    if len(candidatos) == 1:
        return candidatos[0]
    raise ReferenciaDesconhecida(f"referência sem ano e fora do catálogo: {ref!r}")
