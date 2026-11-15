"""Extração e verificação de citações de artigos, precedentes e acórdãos.

Artigo sem lei explícita herda a próxima lei citada na mesma frase; se não
houver, a lei citada antes, na mesma frase. Lei de outra frase não é
herdada: a citação fica sem lei e não passa na verificação. Referência a
lei que não se resolve (sem ano, estadual) também vincula o artigo — e o
deixa sem lei, em vez de deixá-lo herdar outra.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from typing import Literal

from .catalogo import CATALOGO, ReferenciaDesconhecida, item_do_catalogo, resolver_referencia
from .config import Config
from .leis import LeiAusente, carregar_lei
from .modelos import Artigo, LeiDoc
from .planalto import RE_ROTULO, normalizar_numero, rotulo
from .precedentes import PrecedenteAusente, carregar_precedente, id_precedente


@dataclass
class Citacao:
    tipo: Literal["artigo", "precedente", "acordao"]
    trecho: str
    lei_id: str | None
    artigo: str | None
    precedente_id: str | None
    dispositivo: str | None = None  # rótulo normalizado: "x-", "§2o", "parágrafoúnico"
    linha: str = ""  # linha do texto onde a citação aparece (acórdãos: URL e tag)


@dataclass
class Verificacao:
    citacao: Citacao
    status: Literal["ok", "nao_encontrada", "revogada", "cancelada", "fonte_ausente"]
    detalhe: str
    sugestao: str | None


# --- frases -----------------------------------------------------------------

ABREVIACOES = {"art", "arts", "inc", "incs", "n", "no", "nº", "al", "par", "p", "pág", "pag", "fl", "fls",
               "cf", "ss", "dec", "rel", "des", "dr", "dra", "sr", "sra", "v", "min", "ex", "obs"}
# Ponto e vírgula não encerra a frase: "...preferência; o prazo é de 30 dias (art. 28)".
RE_FIM_FRASE = re.compile(r"[.!?](?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ\"“(])|\n")


def _limites_de_frase(texto: str) -> list[int]:
    limites = []
    for m in RE_FIM_FRASE.finditer(texto):
        if m.group() == ".":
            palavra = re.search(r"(\w+)$", texto[: m.start()])
            if palavra and palavra.group(1).casefold() in ABREVIACOES:
                continue
        limites.append(m.end())
    return limites


# --- leis -------------------------------------------------------------------

_N = r"(?i:n(?:º|°|o\.?|\.)?\s*)?"
_APELIDOS: dict[str, tuple[str, str]] = {}
for _item in CATALOGO:
    for _a in _item.apelidos:
        _APELIDOS[_a.casefold()] = (_item.id, "")
_APELIDOS["adct"] = ("cf-1988", "ADCT-")


def _alternativa(apelido: str) -> str:
    esc = re.escape(apelido)
    # Siglas são sensíveis a maiúsculas: "Cf." (confira) não é a Constituição.
    return esc if apelido.isupper() else f"(?i:{esc})"


_ORIGINAIS = sorted({a for i in CATALOGO for a in i.apelidos} | {"ADCT"}, key=len, reverse=True)
RE_LEI = re.compile(
    r"(?<!\w)(?:(?P<alias>" + "|".join(_alternativa(a) for a in _ORIGINAIS) + r")"
    r"|(?P<generica>(?:(?i:lei\s+complementar|decreto-lei|decreto\s+lei|decreto|lei)|DL|LC)"
    r"(?i:\s+(?P<esfera>federal|estadual|municipal|distrital))?\s*" + _N +
    r"\d{1,3}(?:\.?\d{3})*"
    r"(?:\s*/\s*\d{2,4}|(?i:\s*,\s*de\s+\d{1,2}\s*(?:º|°|o)?\s+de\s+[a-zç]+\s+de\s+\d{4}))?))(?!\w)"
)


@dataclass
class _Lei:
    inicio: int
    fim: int
    id: str | None  # None: referência que não se resolve (sem ano, estadual…)
    prefixo: str


def _leis(texto: str) -> list[_Lei]:
    achadas = []
    for m in RE_LEI.finditer(texto):
        if m.group("alias"):
            id_, prefixo = _APELIDOS[m.group("alias").casefold()]
        elif (m.group("esfera") or "").casefold() in ("estadual", "municipal", "distrital"):
            id_, prefixo = None, ""
        else:
            ref = re.sub(r"(?i)\s+federal\b", "", m.group("generica"))
            try:
                id_, prefixo = resolver_referencia(ref), ""
            except ReferenciaDesconhecida:
                id_, prefixo = None, ""
        achadas.append(_Lei(m.start(), m.end(), id_, prefixo))
    return achadas


# --- artigos ----------------------------------------------------------------

# "1.015" ou "1015": nunca cortar o número ("art. 1015" não é o art. 101).
_NUM = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?!\d)(?:\s?[º°]|o(?![a-zà-ú]))?(?:-[A-Z]\b)?"
_DISPOSITIVO = (r"(?:\s*,\s*(?P<disp>§\s*\d+\s*(?:º|°|o)?(?:-[A-Z]\b)?|(?i:par[áa]grafo\s+[úu]nico)"
                r"|(?i:inciso\s+)?[IVXLC]+\b(?!\s*-)))?")
RE_ARTIGO = re.compile(
    r"(?<!\w)(?i:arts?\.?|artigos?)\s*(?P<nums>" + _NUM + r"(?:\s*(?:,|e|a|ao|até)\s*" + _NUM + r")*)"
    + _DISPOSITIVO
)
RE_SEPARADOR = re.compile(r"\s*(,|\be\b|\bao\b|\baté\b|\ba\b)\s*")
LIMITE_INTERVALO = 100


def _numeros(nums: str) -> list[str]:
    partes = RE_SEPARADOR.split(nums)
    numeros = [normalizar_numero(partes[0])]
    for sep, bruto in zip(partes[1::2], partes[2::2]):
        n = normalizar_numero(bruto)
        anterior = numeros[-1]
        if sep in ("a", "ao", "até") and anterior.isdigit() and n.isdigit() and 0 < int(n) - int(anterior) <= LIMITE_INTERVALO:
            numeros.extend(str(i) for i in range(int(anterior) + 1, int(n) + 1))
        else:
            numeros.append(n)
    return numeros


def _rotulo_do_dispositivo(bruto: str | None) -> str | None:
    if not bruto:
        return None
    bruto = re.sub(r"(?i)^inciso\s+", "", bruto.strip())
    if re.fullmatch(r"[IVXLC]+", bruto):
        return bruto.lower() + "-"
    return rotulo(bruto) or None


# --- precedentes ------------------------------------------------------------

_TRIB_NOMES = {"superior tribunal de justiça": "STJ", "superior tribunal de justica": "STJ",
               "supremo tribunal federal": "STF", "tribunal superior do trabalho": "TST"}
_TRIB = r"[A-Z]{2,5}\d?|(?i:superior tribunal de justi[çc]a|supremo tribunal federal|tribunal superior do trabalho)"


def _trib(g: str) -> str:
    return rf"(?:\s*/\s*(?P<{g}a>{_TRIB})|\s+(?i:d[oa])\s+(?P<{g}b>{_TRIB}))?"


_NUM_PREC = r"\d{1,3}(?:\.?\d{3})*"


def _lista(g: str) -> str:
    return rf"(?P<{g}>{_NUM_PREC}(?:\s*(?:,|\be\b)\s*{_NUM_PREC})*)"


RE_PRECEDENTE = re.compile(
    r"(?<!\w)(?:"
    r"(?P<sv_tipo>(?i:s[úu]mulas?\s+vinculantes?)|SVs?)\s*" + _N + _lista("sv")
    + r"|(?P<sum_tipo>(?i:s[úu]mulas?))\s*" + _N + _lista("sum") + _trib("ts")
    + r"|(?P<tema_tipo>(?i:temas?))(?:\s+(?P<qual>(?i:repetitivos?|de\s+repercuss[ãa]o\s+geral)))?\s*" + _N
    + _lista("tema") + _trib("tt")
    + r")(?!\w)"
)


def _nome_trib(bruto: str | None) -> str | None:
    if not bruto:
        return None
    return _TRIB_NOMES.get(bruto.casefold(), bruto)


def _numeros_prec(lista: str, palavra: str) -> list[str]:
    numeros = re.findall(r"\d+(?:\.\d{3})*", lista)
    # Só o plural ("Temas 1235 e 1285") abre lista; "Tema 1235 e 40 SM" é um tema só.
    return numeros if palavra.casefold().rstrip().endswith("s") else numeros[:1]


def _precedentes(m: re.Match) -> list[tuple[str, str, str | None]]:
    """[(tipo, número, id ou None se o tribunal não foi identificado)]."""
    if m.group("sv"):
        return [("sv", n, id_precedente("STF", "súmula vinculante", n))
                for n in _numeros_prec(m.group("sv"), m.group("sv_tipo").split()[0])]
    if m.group("sum"):
        trib = _nome_trib(m.group("tsa") or m.group("tsb"))
        return [("sumula", n, id_precedente(trib, "súmula", n) if trib else None)
                for n in _numeros_prec(m.group("sum"), m.group("sum_tipo"))]
    trib = _nome_trib(m.group("tta") or m.group("ttb"))
    if trib is None and m.group("qual"):
        trib = "STJ" if m.group("qual").casefold().startswith("repetitivo") else "STF"
    return [("tema", n, id_precedente(trib, "tema", n) if trib else None)
            for n in _numeros_prec(m.group("tema"), m.group("tema_tipo"))]


# --- acórdãos ---------------------------------------------------------------

# Acórdão individual: a existência não é verificada. Passa só com
# URL *.jus.br na mesma linha ou marcado como conhecimento do modelo.
RE_ACORDAO = re.compile(
    r"(?<![\w-])(?P<classe>REsp|AREsp|EREsp|RE|ARE|AgInt|AgRg|EDcl|HC|RHC|RMS|MS|ADI|ADC|ADO|ADPF|Rcl)"
    r"\s*" + _N + r"(?P<num>\d{1,3}(?:\.\d{3})+|\d+)(?!\d)(?:\s*/\s*[A-Z]{2})?"
)
RE_URL_JUS = re.compile(r"https?://[^\s)\]>]*\.jus\.br\b", re.IGNORECASE)
TAG_MODELO = "[conhecimento do modelo — verificar]"


def _linha_em(texto: str, pos: int) -> str:
    ini = texto.rfind("\n", 0, pos) + 1
    fim = texto.find("\n", pos)
    return texto[ini : fim if fim >= 0 else len(texto)]


def _unico(valores: list[str | None]) -> str | None:
    distintos = {v for v in valores if v}
    return distintos.pop() if len(distintos) == 1 else None


# --- extração ---------------------------------------------------------------

def extrair_citacoes(texto: str) -> list[Citacao]:
    """Extrai citações. Artigo sem lei na frase, ou precedente sem tribunal,
    herda a lei/tribunal de uma citação completa do mesmo número no texto,
    se ela for única."""
    limites = _limites_de_frase(texto)

    def frase(pos: int) -> int:
        return bisect.bisect_right(limites, pos)

    leis = _leis(texto)
    # (posição, citação, chave do número, pode herdar)
    achadas: list[tuple[int, Citacao, str, bool]] = []
    for m in RE_ARTIGO.finditer(texto):
        f = frase(m.start())
        mesma = [l for l in leis if frase(l.inicio) == f]
        depois = [l for l in mesma if l.inicio >= m.end()]
        antes = [l for l in mesma if l.fim <= m.start()]
        lei = depois[0] if depois else (antes[-1] if antes else None)
        trecho = texto[m.start() : lei.fim] if lei and lei.inicio >= m.end() else m.group()
        numeros = _numeros(m.group("nums"))
        dispositivo = _rotulo_do_dispositivo(m.group("disp")) if len(numeros) == 1 else None
        for n in numeros:
            achadas.append((m.start(), Citacao(
                tipo="artigo", trecho=trecho.strip(), lei_id=lei.id if lei else None,
                artigo=(lei.prefixo if lei else "") + n, precedente_id=None, dispositivo=dispositivo,
                linha=_linha_em(texto, m.start()),
            ), n, lei is None))
    for m in RE_PRECEDENTE.finditer(texto):
        for tipo, numero, pid in _precedentes(m):
            achadas.append((m.start(), Citacao(
                tipo="precedente", trecho=m.group().strip(), lei_id=None, artigo=None, precedente_id=pid,
                linha=_linha_em(texto, m.start()),
            ), f"{tipo}-{numero.replace('.', '')}", True))
    for m in RE_ACORDAO.finditer(texto):
        achadas.append((m.start(), Citacao(
            tipo="acordao", trecho=m.group().strip(), lei_id=None, artigo=None, precedente_id=None,
            linha=_linha_em(texto, m.start()),
        ), "", False))

    for _, c, chave, pode_herdar in achadas:
        if not pode_herdar:
            continue
        if c.tipo == "artigo" and c.lei_id is None:
            c.lei_id = _unico([x.lei_id for _, x, k, _ in achadas
                               if x.tipo == "artigo" and k == chave and x.artigo == chave])
        elif c.tipo == "precedente" and c.precedente_id is None:
            c.precedente_id = _unico([x.precedente_id for _, x, k, _ in achadas
                                      if x.tipo == "precedente" and k == chave])
    achadas.sort(key=lambda x: x[0])
    return [c for _, c, _, _ in achadas]


# --- verificação ------------------------------------------------------------

def _verificar_dispositivo(c: Citacao, art: Artigo, rot: str, titulo: str) -> Verificacao | None:
    """None quando o dispositivo existe e vale; senão, a reprovação."""
    alvo = c.dispositivo
    linhas = art.texto.split("\n")[1:] if art.texto else []
    vigentes = {rotulo(l): l for l in linhas}
    if alvo in vigentes:
        linha = vigentes[alvo]
        resto = linha[RE_ROTULO.match(linha).end():].strip(" -–—.:")
        if not resto:
            return Verificacao(c, "revogada", f"{alvo} do {rot} de {titulo} está sem texto (revogado)", None)
        return None
    if any(rotulo(r.texto) == alvo for r in art.redacoes_anteriores):
        return Verificacao(c, "revogada", f"{alvo} do {rot} de {titulo} só existe em redação anterior", None)
    return Verificacao(c, "nao_encontrada", f"{alvo} não existe no {rot} de {titulo}", None)


def _verificar_artigo(cfg: Config, c: Citacao, cache: dict[str, LeiDoc | None]) -> Verificacao:
    if c.lei_id is None:
        return Verificacao(c, "nao_encontrada",
                           "lei não identificada na frase: cite a lei junto do artigo, com número e ano", None)
    if c.lei_id not in cache:
        try:
            cache[c.lei_id] = carregar_lei(cfg, c.lei_id)
        except LeiAusente:
            cache[c.lei_id] = None
    doc = cache[c.lei_id]
    if doc is None:
        if item_do_catalogo(c.lei_id):
            sugestao = f'baixar_lei("{c.lei_id}")'
        else:
            sugestao = f'baixar_lei("<URL oficial do Planalto>") para {c.lei_id}'
        return Verificacao(c, "fonte_ausente", f"{c.lei_id} não está na base", sugestao)
    art = next((a for a in doc.artigos if a.numero == c.artigo), None)
    rot = f"art. {c.artigo.removeprefix('ADCT-')}{' do ADCT' if c.artigo.startswith('ADCT-') else ''}"
    if art is None:
        return Verificacao(c, "nao_encontrada", f"{rot} não existe em {doc.titulo}", None)
    capturado = doc.capturado_em.date().isoformat()
    if art.revogado:
        return Verificacao(c, "revogada", f"{rot} de {doc.titulo} está revogado", None)
    if c.dispositivo:
        reprovado = _verificar_dispositivo(c, art, rot, doc.titulo)
        if reprovado:
            return reprovado
    return Verificacao(c, "ok", f"{rot} de {doc.titulo} (capturado em {capturado})", None)


def _verificar_precedente(cfg: Config, c: Citacao) -> Verificacao:
    if c.precedente_id is None:
        return Verificacao(c, "nao_encontrada", "tribunal não identificado: escreva, p. ex., Súmula 7/STJ", None)
    try:
        p = carregar_precedente(cfg, c.precedente_id)
    except PrecedenteAusente:
        trib, tipo, numero = c.precedente_id.split("-", 2)
        tipo = {"sumula": "súmula", "sv": "súmula vinculante"}.get(tipo, tipo)
        sugestao = (f'baixar_precedente(tribunal="{trib.upper()}", tipo="{tipo}", numero="{numero}", '
                    'enunciado="<texto oficial>", url="<URL *.jus.br>")')
        return Verificacao(c, "fonte_ausente", f"{c.precedente_id} não está na base", sugestao)
    if p.estado != "vigente":
        return Verificacao(c, "cancelada", f"{c.precedente_id} está {p.estado}", None)
    # O enunciado é texto recuperado: fica fora do detalhe (quem quiser lê com buscar).
    detalhe = f"{c.precedente_id} vigente"
    if not p.conferido:
        detalhe = f"[verificar] não conferido no site oficial — {detalhe}"
    return Verificacao(c, "ok", detalhe, None)


def _chave_acordao(c: Citacao) -> tuple[str, str] | None:
    m = RE_ACORDAO.match(c.trecho)
    return (m.group("classe").casefold(), m.group("num").replace(".", "")) if m else None


def _verificar_acordao(c: Citacao, com_url: set[tuple[str, str]]) -> Verificacao:
    if RE_URL_JUS.search(c.linha):
        return Verificacao(c, "ok", f"{c.trecho}: URL oficial na mesma linha (existência não verificada)", None)
    if _chave_acordao(c) in com_url:
        return Verificacao(c, "ok", f"{c.trecho}: URL oficial em outra linha do texto (existência não verificada)", None)
    if TAG_MODELO in c.linha:
        return Verificacao(c, "ok", f"{c.trecho}: marcado como conhecimento do modelo", None)
    return Verificacao(c, "fonte_ausente", f"{c.trecho}: acórdão sem URL *.jus.br",
                       f"ponha na mesma linha a URL *.jus.br do acórdão ou a tag {TAG_MODELO}")


def verificar_citacoes(cfg: Config, texto: str) -> list[Verificacao]:
    cache: dict[str, LeiDoc | None] = {}
    verificacoes = []
    citacoes = extrair_citacoes(texto)
    # Re-menção curta de um acórdão ("o REsp 1.626.997/RJ condiciona…") vale
    # pela URL oficial dada noutra linha para o mesmo acórdão.
    com_url = {_chave_acordao(c) for c in citacoes if c.tipo == "acordao" and RE_URL_JUS.search(c.linha)}
    for c in citacoes:
        if c.tipo == "artigo":
            verificacoes.append(_verificar_artigo(cfg, c, cache))
        elif c.tipo == "precedente":
            verificacoes.append(_verificar_precedente(cfg, c))
        else:
            verificacoes.append(_verificar_acordao(c, com_url))
    return verificacoes
