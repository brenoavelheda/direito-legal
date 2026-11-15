"""Precedentes (súmulas, súmulas vinculantes, temas) em base/precedentes/<id>.md.

Cada precedente é gravado uma vez por id; registrar de novo substitui. O
servidor tenta abrir a URL oficial (*.jus.br) e marca `conferido` quando o
enunciado aparece na página. Site que bloqueia acesso automatizado (o STJ
responde 403) não impede o registro: fica `conferido: false`.
"""

from __future__ import annotations

import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from .arquivos import escrever_frontmatter, gravar_atomico, ler_frontmatter, trava
from .captura import CapturaFalhou, FonteNaoOficial, baixar
from .config import Config
from .fontes import eh_jus_br
from .indice import indexar_arquivo
from .modelos import PrecedenteDoc


class PrecedenteAusente(Exception):
    """O precedente não está na base (ou o id é inválido)."""


ESTADOS = ("vigente", "cancelada", "superada")
_ESTADO_ALIAS = {"cancelado": "cancelada", "superado": "superada", "revogada": "cancelada", "revogado": "cancelada"}
_TIPOS = {
    "sumula": "sumula", "sumula vinculante": "sv", "sv": "sv", "tema": "tema", "tema repetitivo": "tema",
    "recurso repetitivo": "tema", "repetitivo": "tema", "tema de repercussao geral": "tema",
    "repercussao geral": "tema",
}
RE_ID = re.compile(r"^[a-z0-9]+-[a-z0-9-]+-[0-9a-z]+$")
CAMPOS = ("id", "tribunal", "tipo", "numero", "enunciado", "estado", "url", "capturado_em", "sha256", "conferido")


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def normalizar_texto(texto: str) -> str:
    """Sem acentos, minúsculas, sem pontuação, espaços colapsados."""
    texto = _sem_acento(texto.replace("\xa0", " ")).casefold()
    texto = re.sub(r"(?<=\d)\.(?=\d)", "", texto)  # "1.235" e "1235" são o mesmo número
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", texto)).strip()


MIN_PALAVRAS = 8  # enunciado curto ("prova") aparece em qualquer página
JANELA = 1500  # o número do precedente tem de aparecer até aqui antes do enunciado


def _confere(pagina: str, enunciado: str, numero: str) -> bool:
    """O enunciado está na página, depois do número do precedente: o último
    "súmula/tema N" antes dele é este N (página com vários); sem esse padrão
    na janela, basta o número aparecer nela."""
    alvo = normalizar_texto(enunciado)
    if len(alvo.split()) < MIN_PALAVRAS:
        return False
    num = numero.strip().replace(".", "")
    inicio = pagina.find(alvo)
    while inicio >= 0:
        janela = pagina[max(0, inicio - JANELA) : inicio]
        rotulados = re.findall(r"\b(?:sumula|tema|vinculante|sv)\s+(?:n\s+|no\s+)?(\d+)\b", janela)
        if (rotulados and rotulados[-1] == num) or (not rotulados and re.search(rf"\b{num}\b", janela)):
            return True
        inicio = pagina.find(alvo, inicio + 1)
    return False


def id_precedente(tribunal: str, tipo: str, numero: str) -> str:
    trib = normalizar_texto(tribunal)
    if not re.fullmatch(r"[a-z0-9]+", trib or ""):
        raise ValueError(f"tribunal inválido: {tribunal!r}")
    chave_tipo = normalizar_texto(tipo)
    if not chave_tipo:
        raise ValueError("tipo de precedente vazio")
    tipo_id = _TIPOS.get(chave_tipo, chave_tipo.replace(" ", "-"))
    num = numero.strip().replace(".", "")
    if not re.fullmatch(r"\d+[a-z]?", num.casefold()):
        raise ValueError(f"número de precedente inválido: {numero!r}")
    return f"{trib}-{tipo_id}-{num.casefold()}"


def _estado(estado: str) -> str:
    e = _sem_acento(estado).strip().casefold()
    e = _ESTADO_ALIAS.get(e, e)
    if e not in ESTADOS:
        raise ValueError(f"estado inválido: {estado!r} (use {', '.join(ESTADOS)})")
    return e


def _caminho(cfg: Config, id_: str) -> Path:
    if not RE_ID.match(id_ or ""):
        raise PrecedenteAusente(f"id de precedente inválido: {id_!r}")
    return cfg.base_dir / "precedentes" / f"{id_}.md"


def _serializar(doc: PrecedenteDoc) -> str:
    meta = {k: getattr(doc, k) for k in CAMPOS}
    meta["capturado_em"] = doc.capturado_em.isoformat()
    meta = {"titulo": f"{doc.tribunal} {doc.tipo} {doc.numero}", **meta}
    return escrever_frontmatter(meta) + "\n" + doc.enunciado + "\n"


def registrar_precedente(
    cfg: Config, tribunal: str, tipo: str, numero: str, enunciado: str, url: str,
    estado: str = "vigente", *, abrir=urllib.request.urlopen,
) -> PrecedenteDoc:
    if not eh_jus_br(url):
        raise FonteNaoOficial(f"precedente só com URL de domínio *.jus.br: {url}")
    id_ = id_precedente(tribunal, tipo, numero)
    estado = _estado(estado)
    enunciado = re.sub(r"\s+", " ", enunciado).strip()
    try:
        captura = baixar(url, exigir="jus", abrir=abrir)
    except CapturaFalhou:
        captura = None
    if captura is not None:
        pagina = normalizar_texto(BeautifulSoup(captura.html, "html.parser").get_text(" "))
        conferido = _confere(pagina, enunciado, numero)
        sha256, capturado_em = captura.sha256, captura.capturado_em
    else:
        conferido, sha256, capturado_em = False, None, datetime.now(timezone.utc)
    doc = PrecedenteDoc(
        id=id_, tribunal=tribunal.strip(), tipo=tipo.strip(), numero=numero.strip(), enunciado=enunciado,
        estado=estado, url=url, capturado_em=capturado_em, sha256=sha256, conferido=conferido,
    )
    with trava(cfg.base_dir):
        try:
            anterior = carregar_precedente(cfg, id_)
        except PrecedenteAusente:
            anterior = None
        if anterior is not None and anterior.conferido and not conferido:
            # Registro não conferido não rebaixa nem troca o enunciado de um conferido;
            # só o estado (cancelada/superada) é atualizado.
            anterior.estado = estado
            doc = anterior
        caminho = gravar_atomico(_caminho(cfg, id_), _serializar(doc))
    indexar_arquivo(cfg, caminho)
    return doc


def carregar_precedente(cfg: Config, id: str) -> PrecedenteDoc:
    caminho = _caminho(cfg, id)
    if not caminho.is_file():
        raise PrecedenteAusente(f"precedente {id} não está na base: registre com baixar_precedente")
    meta, _ = ler_frontmatter(caminho.read_text(encoding="utf-8"))
    return PrecedenteDoc(
        **{k: meta[k] for k in CAMPOS if k != "capturado_em"},
        capturado_em=datetime.fromisoformat(meta["capturado_em"]),
    )
