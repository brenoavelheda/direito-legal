"""Armazenamento de leis em base/leis/<id>.md e download pelo catálogo.

Formato: frontmatter (valores em JSON, que também é YAML válido) e, por
artigo, `## Art. <n>`, `estado:`, o texto, `### Notas` e
`### Redações anteriores` com `#### <alterado_por|original> (<ano|s/d>)`.
Linhas de texto que começam com `#` ou `\\` recebem um `\\` na frente, para
nunca serem lidas como cabeçalho.
"""

from __future__ import annotations

import re
import urllib.request
from datetime import date, datetime
from pathlib import Path

from .arquivos import escrever_frontmatter, gravar_atomico, ler_frontmatter, trava
from .captura import baixar
from .catalogo import RE_ID, ReferenciaDesconhecida, item_do_catalogo, item_por_url, resolver_referencia
from .config import Config
from .modelos import Artigo, LeiDoc, Marco, Redacao
from .planalto import ParseVazio, parse_lei, titulo_da_pagina


class LeiAusente(Exception):
    """A lei não está na base (ou o id é inválido)."""


class LeiParcial(ParseVazio):
    """A página trouxe bem menos artigos que a cópia da base: não grava."""


class FonteConflitante(ValueError):
    """A lei já está na base com outra URL: não troca a fonte em silêncio."""


MINIMO_DA_COPIA = 0.9  # nova captura com menos de 90% dos artigos da cópia é suspeita


CAMPOS = ("id", "apelidos", "titulo", "url", "capturado_em", "sha256")
RE_MARCO = re.compile(r"^- (?P<tipo>incluido|redacao) (?P<rotulo>\S+) \((?P<ano>\d{4})\)$")
RE_REDACAO = re.compile(r"^#### (?P<lei>.+) \((?P<ano>\d{4}|s/d)\)$")


def _pasta(cfg: Config) -> Path:
    return cfg.base_dir / "leis"


def _caminho(cfg: Config, id_: str) -> Path:
    if not RE_ID.match(id_ or ""):
        raise LeiAusente(f"id de lei inválido: {id_!r}")
    return _pasta(cfg) / f"{id_}.md"


def _escapar(linha: str) -> str:
    return "\\" + linha if linha.startswith(("#", "\\")) else linha


def _desescapar(linha: str) -> str:
    return linha[1:] if linha.startswith("\\") else linha


def _texto(texto: str) -> list[str]:
    return [_escapar(l) for l in texto.split("\n")] if texto else []


def _serializar(doc: LeiDoc) -> str:
    valores = {
        "id": doc.id, "apelidos": doc.apelidos, "titulo": doc.titulo, "url": doc.url,
        "capturado_em": doc.capturado_em.isoformat(), "sha256": doc.sha256,
    }
    linhas = [escrever_frontmatter({k: valores[k] for k in CAMPOS}), f"# {doc.titulo}", ""]
    for art in doc.artigos:
        linhas += [f"## Art. {art.numero}", f"estado: {'revogado' if art.revogado else 'vigente'}", ""]
        if art.texto:
            linhas += [*_texto(art.texto), ""]
        if art.notas:
            linhas += ["### Notas", *(f"- {_escapar(n)}" for n in art.notas), ""]
        if art.marcos:
            linhas += ["### Marcos", *(f"- {m.tipo} {m.rotulo} ({m.ano})" for m in art.marcos), ""]
        if art.redacoes_anteriores:
            linhas += ["### Redações anteriores", ""]
            for r in art.redacoes_anteriores:
                ano = str(r.data.year) if r.data else "s/d"
                linhas += [f"#### {r.alterado_por or 'original'} ({ano})", *_texto(r.texto), ""]
    return "\n".join(linhas)


def _juntar(buffer: list[str]) -> str:
    while buffer and not buffer[0]:
        buffer.pop(0)
    while buffer and not buffer[-1]:
        buffer.pop()
    return "\n".join(_desescapar(l) for l in buffer)


def _desserializar(conteudo: str) -> LeiDoc:
    meta, corpo = ler_frontmatter(conteudo)
    if not meta:
        raise ValueError("arquivo de lei sem frontmatter")

    artigos: list[Artigo] = []
    buffer: list[str] = []
    secao = None  # "texto" | "notas" | "redacoes"
    redacao: Redacao | None = None

    def fechar_buffer() -> None:
        if secao == "texto" and artigos:
            artigos[-1].texto = _juntar(buffer)
        elif secao == "redacoes" and redacao is not None:
            redacao.texto = _juntar(buffer)
        buffer.clear()

    for l in corpo.split("\n"):
        if l.startswith("## Art. "):
            fechar_buffer()
            artigos.append(Artigo(numero=l[len("## Art. ") :], texto=""))
            secao, redacao = "estado", None
        elif secao == "estado":
            if l.startswith("estado: "):
                artigos[-1].revogado = l == "estado: revogado"
                secao = "texto"
        elif l == "### Notas":
            fechar_buffer()
            secao = "notas"
        elif l == "### Marcos":
            fechar_buffer()
            secao = "marcos"
        elif l == "### Redações anteriores":
            fechar_buffer()
            secao, redacao = "redacoes", None
        elif secao == "marcos":
            if m := RE_MARCO.match(l):
                artigos[-1].marcos.append(Marco(m.group("rotulo"), m.group("tipo"), int(m.group("ano"))))
        elif secao == "notas":
            if l.startswith("- "):
                artigos[-1].notas.append(_desescapar(l[2:]))
        elif secao == "redacoes" and (m := RE_REDACAO.match(l)):
            fechar_buffer()
            lei = m.group("lei")
            ano = m.group("ano")
            redacao = Redacao(
                texto="",
                alterado_por=None if lei == "original" else lei,
                data=None if ano == "s/d" else date(int(ano), 1, 1),
            )
            artigos[-1].redacoes_anteriores.append(redacao)
        elif secao in ("texto", "redacoes"):
            buffer.append(l)
    fechar_buffer()

    return LeiDoc(
        id=meta["id"], apelidos=meta["apelidos"], titulo=meta["titulo"], url=meta["url"],
        capturado_em=datetime.fromisoformat(meta["capturado_em"]), sha256=meta["sha256"], artigos=artigos,
    )


def salvar_lei(cfg: Config, doc: LeiDoc) -> Path:
    with trava(cfg.base_dir):
        return gravar_atomico(_caminho(cfg, doc.id), _serializar(doc))


def carregar_lei(cfg: Config, id: str) -> LeiDoc:
    caminho = _caminho(cfg, id)
    if not caminho.is_file():
        raise LeiAusente(f"lei {id} não está na base: baixe com baixar_lei")
    return _desserializar(caminho.read_text(encoding="utf-8"))


def baixar_lei(cfg: Config, ref_ou_url: str, *, abrir=urllib.request.urlopen) -> LeiDoc:
    """Baixa do Planalto, parseia e grava. Nada é gravado se o parse falhar."""
    if ref_ou_url.strip().lower().startswith(("http://", "https://")):
        url = ref_ou_url.strip()
        item = item_por_url(url)
    else:
        id_ = resolver_referencia(ref_ou_url)
        item = item_do_catalogo(id_)
        if item is None:
            raise ReferenciaDesconhecida(
                f"{ref_ou_url!r} ({id_}) está fora do catálogo: passe a URL oficial do Planalto"
            )
        url = item.url

    captura = baixar(url, exigir="oficial", abrir=abrir)
    try:
        artigos = parse_lei(captura.html)
    except ParseVazio as e:
        raise ParseVazio(f"nenhum artigo reconhecido em {url}: página bloqueada ou formato mudou") from e

    if item is not None:
        id_, titulo, apelidos = item.id, item.titulo, list(item.apelidos)
    else:
        titulo = titulo_da_pagina(captura.html)
        if titulo is None:
            raise ReferenciaDesconhecida(f"não identifiquei qual lei está em {url}")
        id_, apelidos = resolver_referencia(titulo), []

    try:
        anterior = carregar_lei(cfg, id_)
    except LeiAusente:
        anterior = None
    if anterior is not None:
        # Lei do catálogo: a URL do catálogo manda. Fora dele, não troca a fonte.
        if item is None and anterior.url.casefold() != url.casefold():
            raise FonteConflitante(
                f"{id_} já está na base com a fonte {anterior.url}; {url} não a substitui. "
                "Para trocar a fonte, apague base/leis/" + f"{id_}.md antes."
            )
        if len(artigos) < MINIMO_DA_COPIA * len(anterior.artigos):
            raise LeiParcial(
                f"{url} trouxe {len(artigos)} artigos e a cópia da base tem {len(anterior.artigos)}: "
                "página parcial ou de outra versão; a cópia anterior foi mantida"
            )
        if item is None:
            apelidos = anterior.apelidos

    doc = LeiDoc(id=id_, apelidos=apelidos, titulo=titulo, url=url, capturado_em=captura.capturado_em,
                 sha256=captura.sha256, artigos=artigos)
    salvar_lei(cfg, doc)
    return doc
