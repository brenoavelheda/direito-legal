"""Categorias: assuntos jurídicos reutilizáveis em base/categorias/<slug>/.

Cada categoria tem cinco arquivos (SECOES). `guia.md` leva o frontmatter
(titulo, criado_em, atualizado_em). Cada integração é anexada como
`### AAAA-MM-DD` + conteúdo + `Fontes:` com cada URL marcada `[oficial]`
ou `[comentário]`. Em normas e precedentes, entrada com fonte não oficial
vai para `## Comentários`, no fim do arquivo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .arquivos import escrever_frontmatter, gravar_atomico, ler_frontmatter, trava
from .config import Config
from .fontes import classificar_fonte
from .indice import indexar_arquivo

SECOES = ("guia", "normas", "precedentes", "fontes", "perguntas")
TITULOS_SECAO = {
    "guia": "Guia", "normas": "Normas", "precedentes": "Precedentes", "fontes": "Fontes", "perguntas": "Perguntas",
}
COMENTARIOS = "## Comentários"
RE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RE_URL = re.compile(r"^https?://[^\s/]+\S*$")


class SemFonte(Exception):
    """Integração sem fonte, ou fonte que não é URL."""


class SecaoInvalida(Exception):
    """Seção fora de SECOES."""


class SlugInvalido(Exception):
    """Nome de categoria vazio ou com caminho (travessia)."""


class CategoriaAusente(Exception):
    """A categoria não existe na base."""


@dataclass
class ResultadoIntegracao:
    slug: str
    arquivo: Path
    criada: bool
    tipo: Literal["norma", "comentario"]


@dataclass
class CategoriaResumo:
    slug: str
    titulo: str
    resumo: str
    atualizado_em: str


def slugificar(titulo: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def _raiz(cfg: Config) -> Path:
    return (cfg.base_dir / "categorias").resolve()


def _pasta(cfg: Config, slug: str) -> Path:
    if not RE_SLUG.match(slug):
        raise SlugInvalido(f"slug inválido: {slug!r}")
    pasta = (_raiz(cfg) / slug).resolve()
    if pasta.parent != _raiz(cfg):
        raise SlugInvalido(f"categoria fora de base/categorias: {slug!r}")
    return pasta


def slug_da_categoria(categoria: str) -> str:
    if any(c in categoria for c in ("/", "\\", ":")) or ".." in categoria:
        raise SlugInvalido(f"nome de categoria com caminho: {categoria!r}")
    slug = slugificar(categoria)
    if not slug:
        raise SlugInvalido(f"nome de categoria vazio: {categoria!r}")
    return slug


def _agora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


RE_MARCADOR = re.compile(r"\[(oficial|coment[aá]rio)\]", re.IGNORECASE)
RE_SUBLINHADO = re.compile(r"^\s*(=+|-+)\s*$")  # "===" ou "---" sob uma linha vira título (setext)


def _neutralizar(linha: str) -> str:
    """Conteúdo nunca forja a estrutura do arquivo: títulos (com espaço na
    frente também) descem para nível 4+, `Fontes:` e sublinhado de título
    ganham `\\` e os marcadores [oficial]/[comentário] viram parênteses."""
    linha = RE_MARCADOR.sub(r"(\1)", linha)
    solta = linha.lstrip()
    if solta.startswith("#"):
        return "###" + solta
    if solta.casefold().startswith("fontes:") or RE_SUBLINHADO.match(linha):
        return "\\" + solta
    return linha


def _rebaixar_titulos(conteudo: str) -> str:
    return "\n".join(_neutralizar(l) for l in conteudo.strip().split("\n"))


def _criar(cfg: Config, pasta: Path, titulo: str) -> None:
    agora = _agora()
    for secao in SECOES:
        cabecalho = f"# {TITULOS_SECAO[secao]} — {titulo}\n"
        if secao == "guia":
            cabecalho = escrever_frontmatter({"titulo": titulo, "criado_em": agora, "atualizado_em": agora}) \
                + "\n" + cabecalho
        gravar_atomico(pasta / f"{secao}.md", cabecalho)


def _tocar_guia(guia: Path) -> None:
    meta, corpo = ler_frontmatter(guia.read_text(encoding="utf-8"))
    meta["atualizado_em"] = _agora()
    gravar_atomico(guia, escrever_frontmatter(meta) + corpo)


def _entrada(conteudo: str, fontes: list[str]) -> str:
    marcadas = [f"- {u} [{'oficial' if classificar_fonte(u) == 'oficial' else 'comentário'}]" for u in fontes]
    data = datetime.now(timezone.utc).astimezone().date().isoformat()
    return "\n".join([f"### {data}", "", _rebaixar_titulos(conteudo), "", "Fontes:", *marcadas, ""])


def _anexar(texto: str, entrada: str, comentario: bool) -> str:
    linhas = texto.rstrip("\n").split("\n")
    if comentario:
        if COMENTARIOS not in linhas:
            linhas += ["", COMENTARIOS]
        return "\n".join(linhas + ["", entrada])
    if COMENTARIOS in linhas:
        i = linhas.index(COMENTARIOS)
        return "\n".join(linhas[:i] + [entrada] + linhas[i:]) + "\n"
    return "\n".join(linhas + ["", entrada])


def integrar(cfg: Config, categoria: str, secao: str, conteudo: str, fontes: list[str]) -> ResultadoIntegracao:
    """Anexa uma entrada à seção (cria a categoria se for nova), sob a trava da base."""
    with trava(cfg.base_dir):
        return _integrar(cfg, categoria, secao, conteudo, fontes)


def _integrar(cfg: Config, categoria: str, secao: str, conteudo: str, fontes: list[str]) -> ResultadoIntegracao:
    if secao not in SECOES:
        raise SecaoInvalida(f"seção inválida: {secao!r} (use {', '.join(SECOES)})")
    fontes = [f.strip() for f in fontes]
    if not fontes:
        raise SemFonte("integração exige ao menos uma fonte")
    invalidas = [f for f in fontes if not RE_URL.match(f)]
    if invalidas:
        raise SemFonte(f"fonte precisa ser URL http(s): {invalidas!r}")
    slug = slug_da_categoria(categoria)
    pasta = _pasta(cfg, slug)
    criada = not (pasta / "guia.md").exists()
    if criada:
        _criar(cfg, pasta, categoria.strip())
    oficial = all(classificar_fonte(f) == "oficial" for f in fontes)
    tipo: Literal["norma", "comentario"] = "norma" if oficial else "comentario"
    arquivo = pasta / f"{secao}.md"
    atual = arquivo.read_text(encoding="utf-8") if arquivo.exists() else f"# {TITULOS_SECAO[secao]}\n"
    vai_para_comentarios = tipo == "comentario" and secao in ("normas", "precedentes")
    gravar_atomico(arquivo, _anexar(atual, _entrada(conteudo, fontes), vai_para_comentarios))
    guia = pasta / "guia.md"
    _tocar_guia(guia)
    indexar_arquivo(cfg, arquivo)
    if arquivo != guia:
        indexar_arquivo(cfg, guia)
    return ResultadoIntegracao(slug=slug, arquivo=arquivo, criada=criada, tipo=tipo)


def _resumo(corpo: str) -> str:
    for linha in corpo.split("\n"):
        l = linha.strip()
        if l and not l.startswith(("#", "Fontes:", "- http")):
            return l[:200]
    return ""


def listar_categorias(cfg: Config) -> list[CategoriaResumo]:
    raiz = cfg.base_dir / "categorias"
    if not raiz.is_dir():
        return []
    resumos = []
    for pasta in sorted(p for p in raiz.iterdir() if p.is_dir() and RE_SLUG.match(p.name)):
        guia = pasta / "guia.md"
        meta, corpo = ler_frontmatter(guia.read_text(encoding="utf-8")) if guia.exists() else ({}, "")
        resumos.append(CategoriaResumo(
            slug=pasta.name, titulo=str(meta.get("titulo") or pasta.name), resumo=_resumo(corpo),
            atualizado_em=str(meta.get("atualizado_em") or ""),
        ))
    return resumos


def ler_categoria(cfg: Config, slug: str) -> dict[str, str]:
    pasta = _pasta(cfg, slug)
    if not pasta.is_dir():
        raise CategoriaAusente(f"categoria {slug} não existe: crie com integrar")
    secoes = {}
    for secao in SECOES:
        arquivo = pasta / f"{secao}.md"
        texto = arquivo.read_text(encoding="utf-8") if arquivo.exists() else ""
        secoes[secao] = ler_frontmatter(texto)[1]
    return secoes
