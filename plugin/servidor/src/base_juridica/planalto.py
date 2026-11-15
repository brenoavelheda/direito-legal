"""Parser do HTML de leis do Planalto.

O Planalto marca o texto que deixou de valer com <strike>, <s>, <del> ou
style="text-decoration: line-through". As âncoras <a name="artN"> não são
confiáveis (o Código Civil compilado tem 4) e parte do texto fica fora de
<p> (o CDC tem artigos soltos em <font>), então o documento é lido como
uma sequência de linhas, e os artigos são identificados pelo texto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import CData, Comment, Declaration, Doctype, ProcessingInstruction

from .modelos import Artigo, Marco, Redacao


class ParseVazio(Exception):
    """Nenhum artigo reconhecido na página."""


# Letra do artigo ("54-A", "8º-A"): colada no hífen e sem palavra minúscula
# depois. "Art. 839 - A reclamação" é o art. 839, com hífen separador.
_LETRA = r"(?-i:\s*-(?P<letra>[A-Z])(?![\wÀ-ÿ])(?!\s+[a-záéíóúâêôãõçà]))"
_NUM = r"(?P<num>\d+(?:\.\d{3})*)\s*(?P<ord>º|°|o(?![a-záéíóúãõç]))?" + _LETRA + "?"
RE_ART = re.compile(r"^Art\.?\s*" + _NUM + r"\s*[.\-–—]?\s*")
# Início de artigo no meio de uma linha: depois de fim de frase, nunca depois de aspas.
RE_ART_MEIO = re.compile(r"(?<=[\.;:\)])\s+(?=Art\.?\s*\d)")
RE_NOTA = re.compile(
    r"\((?:Redação dada|Incluído|Incluída|Incluídos|Revogado|Revogada|Revogados|Vide|Vigência|Renumerado)[^)]*\)",
    re.IGNORECASE,
)
RE_REDACAO_DADA = re.compile(r"Redação dada pel[ao]\s+(?P<lei>[^)]+?)\s*\)", re.IGNORECASE)
RE_REVOGADO_POR = re.compile(r"Revogad[oa]s?\s+pel[ao]\s+(?P<lei>[^)]+?)\s*\)", re.IGNORECASE)
# Texto de link que é só marcador do Planalto, não parte da lei.
RE_MARCA = re.compile(
    r"^\(?\s*(?:Vigência(?:\s+encerrada)?|Produção\s+de\s+efeitos?|Regulamento|Regulamentação|Mensagem\s+de\s+veto"
    r"|Texto\s+compilado|Vide\b.*|Promulgação\b.*|Conversão\b.*)\s*\)?$",
    re.IGNORECASE,
)
RE_INCLUIDO_POR = re.compile(r"Incluíd[oa]s?\s+pel[ao]\s+(?P<lei>[^)]+?)\s*\)", re.IGNORECASE)
RE_ANO = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
RE_ROTULO = re.compile(
    r"^(Art\.?\s*\d+(?:\.\d{3})*\s*(?:º|°|o)?" + _LETRA.replace("?P<letra>", "") + r"?"
    r"|§\s*\d+\s*(?:º|°|o)?" + _LETRA.replace("?P<letra>", "") + r"?|Parágrafo único|[IVXLC]+\s*[-–—]|[a-z]\))",
    re.IGNORECASE,
)
RE_FIM = re.compile(r"^(Brasília,|Este texto não substitui)", re.IGNORECASE)
RE_ADCT = re.compile(r"DISPOSI[ÇC][ÕO]ES\s+CONSTITUCIONAIS\s+TRANSIT[ÓO]RIAS", re.IGNORECASE)
RE_CABECALHO = re.compile(
    r"^(?P<tipo>LEI\s+COMPLEMENTAR|LEI|DECRETO-LEI|DECRETO|MEDIDA\s+PROVIS[ÓO]RIA)\s+N\s*[º°o]?\s*\.?\s*"
    r"(?P<resto>\d[\d.]*\s*,\s*DE\s+\d{1,2}\s*[º°o]?\s+DE\s+\w+\s+DE\s+\d{4})",
    re.IGNORECASE,
)

BLOCOS = {"p", "div", "blockquote", "td", "th", "li", "dd", "dt", "center", "table", "tr", "body",
          "h1", "h2", "h3", "h4", "h5", "h6"}
IGNORAR = {"script", "style", "head", "title"}
NAO_TEXTO = (Comment, Declaration, Doctype, CData, ProcessingInstruction)


def normalizar_numero(bruto: str) -> str:
    s = re.sub(r"\s+", "", bruto.strip().rstrip("."))
    m = re.match(r"^(\d+(?:\.\d{3})*)(?:º|°|o)?(?:-([A-Za-z]))?$", s)
    if not m:
        return s
    numero = m.group(1).replace(".", "")
    return f"{numero}-{m.group(2).upper()}" if m.group(2) else numero


def _espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.replace("\xa0", " ")).strip()


def _riscado(el: Tag) -> bool:
    if el.name in ("strike", "s", "del"):
        return True
    return "line-through" in (el.get("style") or "").replace(" ", "").lower()


def _centralizado(el: Tag) -> bool:
    if el.name == "center" or (el.get("align") or "").lower() == "center":
        return True
    return "text-align:center" in (el.get("style") or "").replace(" ", "").lower()


@dataclass
class _Linha:
    texto: str
    mascara: list[bool]  # True onde o caractere está riscado
    centralizada: bool
    link: list[int] = field(default_factory=list)  # nº do <a> que contém o caractere (0: fora de link)


def _normalizar(texto: str, mascara: list[bool], link: list[int]) -> tuple[str, list[bool], list[int]]:
    saida: list[str] = []
    masc: list[bool] = []
    lnk: list[int] = []
    espaco = False
    for ch, m, k in zip(texto, mascara, link):
        if ch.isspace() or ch == "\xa0":
            espaco = bool(saida)
            continue
        if espaco:
            saida.append(" ")
            masc.append(m)
            lnk.append(k)
            espaco = False
        saida.append(ch)
        masc.append(m)
        lnk.append(k)
    return "".join(saida), masc, lnk


def _linhas(soup: BeautifulSoup) -> list[_Linha]:
    linhas: list[_Linha] = []
    partes: list[str] = []
    mascara: list[bool] = []
    links: list[int] = []
    numero_do_link: dict[int, int] = {}
    estado = {"bloco": None, "centro": False}

    def fechar() -> None:
        texto, masc, lnk = _normalizar("".join(partes), mascara, links)
        if texto:
            linhas.append(_Linha(texto, masc, estado["centro"], lnk))
        partes.clear()
        mascara.clear()
        links.clear()

    for el in soup.descendants:
        if isinstance(el, Tag):
            if el.name == "br":
                fechar()
            continue
        if not isinstance(el, NavigableString) or isinstance(el, NAO_TEXTO):
            continue
        ancestrais = [a for a in el.parents if isinstance(a, Tag)]
        if any(a.name in IGNORAR for a in ancestrais):
            continue
        bloco = next((a for a in ancestrais if a.name in BLOCOS), None)
        if bloco is not estado["bloco"]:
            fechar()
            estado["bloco"] = bloco
            estado["centro"] = any(_centralizado(a) for a in ancestrais if a.name != "body")
        s = str(el)
        risc = any(_riscado(a) for a in ancestrais)
        ancora = next((a for a in ancestrais if a.name == "a"), None)
        em_link = 0 if ancora is None else numero_do_link.setdefault(id(ancora), len(numero_do_link) + 1)
        partes.append(s)
        mascara.extend([risc] * len(s))
        links.extend([em_link] * len(s))
    fechar()
    return linhas


def _dividir(linha: _Linha) -> list[_Linha]:
    cortes = [m.end() for m in RE_ART_MEIO.finditer(linha.texto)]
    if not cortes:
        return [linha]
    pedacos = []
    inicio = 0
    for c in cortes + [len(linha.texto)]:
        texto = linha.texto[inicio:c].strip()
        if texto:
            ini = linha.texto.index(texto, inicio)
            fim = ini + len(texto)
            pedacos.append(_Linha(texto, linha.mascara[ini:fim], linha.centralizada, linha.link[ini:fim]))
        inicio = c
    return pedacos


@dataclass
class _Bloco:
    texto: str
    riscado: bool
    notas: list[str]
    rotulo: str


@dataclass
class _ArtigoBruto:
    numero: str
    blocos: list[_Bloco] = field(default_factory=list)


def _rotulo(texto: str) -> str:
    m = RE_ROTULO.match(texto)
    if not m:
        return ""
    rot = re.sub(r"\s+", "", m.group(1))
    if re.fullmatch(r"[IVXLCivxlc]+[-–—]", rot):
        rot = rot.replace("l", "I")  # Planalto digita inciso "I" como "l" minúsculo ("ll - ao consumidor")
    rot = rot.lower().replace("º", "o").replace("°", "o")
    rot = rot.replace("–", "-").replace("—", "-")
    return rot.replace("art", "art.", 1).replace("art..", "art.") if rot.startswith("art") else rot


def rotulo(texto: str) -> str:
    """Rótulo normalizado do dispositivo no início do texto ("§1o", "x-", "a)"; "" se não houver)."""
    return _rotulo(texto)


def _marcos(b: _Bloco) -> list[Marco]:
    rot = "caput" if b.rotulo.startswith("art.") else b.rotulo
    if not rot:
        return []
    marcos = []
    for tipo, regex in (("incluido", RE_INCLUIDO_POR), ("redacao", RE_REDACAO_DADA)):
        ano = _data_da_lei(_lei_da_nota(b.notas, regex))
        if ano:
            marcos.append(Marco(rot, tipo, ano.year))
    return marcos


def _marcas_de_link(linha: _Linha) -> tuple[list[bool], list[str]]:
    """Links que são só marcador do Planalto ("Vigência", "Vigência encerrada"…):
    saem do texto e do cálculo do risco e viram nota."""
    texto, n = linha.texto, len(linha.texto)
    ignorar = [False] * n
    marcas: list[str] = []
    i = 0
    while i < n:
        if not (linha.link and linha.link[i]):
            i += 1
            continue
        j = i
        while j < n and linha.link[j] == linha.link[i]:  # um <a> por vez: links vizinhos não se juntam
            j += 1
        trecho = texto[i:j].strip()
        if trecho and RE_MARCA.match(trecho):
            for k in range(i, j):
                ignorar[k] = True
            marcas.append(trecho if trecho.startswith("(") else f"({trecho})")
        i = j
    return ignorar, marcas


def _bloco(linha: _Linha) -> _Bloco:
    ignorar, marcas = _marcas_de_link(linha)
    texto = "".join(ch for ch, ig in zip(linha.texto, ignorar) if not ig)
    mascara = [m for m, ig in zip(linha.mascara, ignorar) if not ig]
    em_nota = [False] * len(texto)
    for m in RE_NOTA.finditer(texto):
        for i in range(m.start(), m.end()):
            em_nota[i] = True
    uteis = [r for r, n, ch in zip(mascara, em_nota, texto) if not n and not ch.isspace()]
    riscado = bool(uteis) and sum(uteis) >= 0.9 * len(uteis)
    notas = [_espacos(n) for n in RE_NOTA.findall(texto)] + marcas
    sem_notas = _espacos(RE_NOTA.sub("", texto))
    return _Bloco(texto=sem_notas, riscado=riscado, notas=notas, rotulo=_rotulo(sem_notas))


def _lei_da_nota(notas: list[str], regex: re.Pattern = RE_REDACAO_DADA) -> str | None:
    for n in notas:
        m = regex.search(n)
        if m:
            return _espacos(m.group("lei"))
    return None


def _data_da_lei(lei: str | None) -> date | None:
    if not lei:
        return None
    anos = RE_ANO.findall(lei)
    return date(int(anos[-1]), 1, 1) if anos else None


def _sem_rotulo_de_artigo(b: _Bloco) -> str:
    return RE_ART.sub("", b.texto, count=1) if b.rotulo.startswith("art.") else b.texto


def _montar(bruto: _ArtigoBruto) -> Artigo:
    vigentes: list[str] = []
    notas: list[str] = []
    redacoes: list[Redacao] = []
    marcos: list[Marco] = []
    blocos = bruto.blocos
    for i, b in enumerate(blocos):
        texto = _sem_rotulo_de_artigo(b)
        if b.riscado:
            # Quem tirou esta redação: a nota de revogação do próprio bloco ou a
            # "Redação dada" do próximo bloco com o mesmo rótulo.
            lei = _lei_da_nota(b.notas, RE_REVOGADO_POR)
            if lei is None:
                seguinte = next((x for x in blocos[i + 1 :] if x.rotulo and x.rotulo == b.rotulo), None)
                lei = _lei_da_nota(seguinte.notas) if seguinte else None
            redacoes.append(Redacao(texto=texto, alterado_por=lei, data=_data_da_lei(lei)))
            # Só a nota de revogação vale para o artigo; as outras são da redação antiga.
            notas.extend(n for n in b.notas if RE_REVOGADO_POR.search(n))
        else:
            if texto:
                vigentes.append(texto)
            notas.extend(b.notas)
            marcos.extend(_marcos(b))
    caputs = [b for b in blocos if not b.riscado and b.rotulo.startswith("art.")]
    revogado = not caputs or all(
        not _sem_rotulo_de_artigo(b) and any("revogad" in n.lower() for n in b.notas) for b in caputs
    )
    return Artigo(
        numero=bruto.numero,
        texto="" if revogado else "\n".join(vigentes),
        revogado=revogado,
        notas=notas,
        redacoes_anteriores=redacoes,
        marcos=marcos,
    )


def parse_lei(html: str) -> list[Artigo]:
    soup = BeautifulSoup(html, "html.parser")
    ordem: list[str] = []
    brutos: dict[str, _ArtigoBruto] = {}
    atual: _ArtigoBruto | None = None
    prefixo = ""
    for linha in _linhas(soup):
        if linha.centralizada:
            if ordem and RE_ADCT.search(linha.texto):
                prefixo = "ADCT-"
            continue
        for pedaco in _dividir(linha):
            b = _bloco(pedaco)
            if not b.texto and not b.notas:
                continue
            if RE_FIM.match(b.texto):
                # Fecho (data, assinaturas, aviso do DOU): nada mais se anexa ao
                # artigo atual, mas a página pode continuar (o ADCT vem depois).
                atual = None
                continue
            m = RE_ART.match(b.texto)
            if m:
                bruto = m.group("num") + (f"-{m.group('letra')}" if m.group("letra") else "")
                numero = prefixo + normalizar_numero(bruto)
                if numero not in brutos:
                    brutos[numero] = _ArtigoBruto(numero)
                    ordem.append(numero)
                atual = brutos[numero]
            if atual is not None:
                atual.blocos.append(b)
    if not ordem:
        raise ParseVazio("nenhum artigo reconhecido")
    return [_montar(brutos[n]) for n in ordem]


def titulo_da_pagina(html: str) -> str | None:
    """Cabeçalho "LEI Nº 8.245, DE 18 DE OUTUBRO DE 1991" antes do primeiro artigo."""
    for linha in _linhas(BeautifulSoup(html, "html.parser")):
        if RE_ART.match(linha.texto):
            return None
        m = RE_CABECALHO.match(linha.texto)
        if m:
            return f"{_espacos(m.group('tipo'))} Nº {_espacos(m.group('resto'))}"
    return None
