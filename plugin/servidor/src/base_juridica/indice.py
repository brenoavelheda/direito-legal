"""Índice de busca FTS5 em base/indice.sqlite, derivado dos markdown.

O índice é descartável: `reconstruir` refaz tudo a partir de base/leis,
base/categorias e base/precedentes. Um registro por artigo
(`<lei-id>#art-<n>`), um por arquivo de categoria (`<slug>/<seção>`) e um
por precedente (`<id>`).
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .arquivos import ler_frontmatter
from .config import Config
from .leis import carregar_lei
from .modelos import LeiDoc

ARQUIVO = "indice.sqlite"

STOPWORDS = frozenset(
    """
    a o as os um uma uns umas de da do das dos e em no na nos nas ao aos para pra pro por pelo pela
    pelos pelas com sem que se ou como qual quais quando onde quem cujo cuja meu minha meus minhas
    seu sua seus suas ele ela eles elas eu voce voces isso isto esse essa este esta esses essas
    aquele aquela lhe me te mais muito ja nao sim ser ter ha foi sao esta estou tem tenho pode posso
    devo deve sobre entre ate apos mas ainda tambem so
    """.split()
)

Tipo = Literal["artigo", "categoria", "precedente"]


@dataclass
class Resultado:
    tipo: Tipo
    id: str
    trecho: str
    fonte: str
    capturado_em: str
    estado: str
    score: float  # -bm25: maior é melhor


def _conectar(cfg: Config) -> sqlite3.Connection:
    con = sqlite3.connect(cfg.base_dir / ARQUIVO, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS indice USING fts5("
        "tipo UNINDEXED, id UNINDEXED, titulo, texto, fonte UNINDEXED, capturado_em UNINDEXED, "
        "estado UNINDEXED, tokenize='unicode61 remove_diacritics 2')"
    )
    return con


def _linhas_da_lei(doc: LeiDoc) -> list[tuple]:
    capturado = doc.capturado_em.isoformat()
    linhas = []
    for art in doc.artigos:
        texto = art.texto or " ".join(art.notas)
        linhas.append((
            "artigo", f"{doc.id}#art-{art.numero}", f"{doc.titulo}, art. {art.numero}", texto,
            doc.url, capturado, "revogado" if art.revogado else "vigente",
        ))
    return linhas


def _inserir_lei(con: sqlite3.Connection, doc: LeiDoc) -> int:
    con.execute("DELETE FROM indice WHERE tipo = 'artigo' AND id LIKE ?", (f"{doc.id}#%",))
    linhas = _linhas_da_lei(doc)
    con.executemany("INSERT INTO indice VALUES (?, ?, ?, ?, ?, ?, ?)", linhas)
    return len(linhas)


def _linha_do_arquivo(cfg: Config, path: Path) -> tuple:
    relativo = path.resolve().relative_to(cfg.base_dir.resolve())
    raiz = relativo.parts[0]
    if raiz == "categorias":
        tipo, id_ = "categoria", "/".join(relativo.with_suffix("").parts[1:])
    elif raiz == "precedentes":
        tipo, id_ = "precedente", path.stem
    else:
        raise ValueError(f"arquivo fora de categorias/ e precedentes/: {relativo}")
    bruto, corpo = ler_frontmatter(path.read_text(encoding="utf-8"))
    meta = {k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in bruto.items()}
    capturado = meta.get("capturado_em") or meta.get("atualizado_em") or datetime.fromtimestamp(
        path.stat().st_mtime, tz=timezone.utc).isoformat()
    titulo = meta.get("titulo") or meta.get("enunciado") or id_
    estado = meta.get("estado", "vigente" if tipo == "precedente" else "")
    return (tipo, id_, titulo, corpo, meta.get("url", ""), capturado, estado)


def indexar_lei(cfg: Config, doc: LeiDoc) -> None:
    with closing(_conectar(cfg)) as con, con:
        _inserir_lei(con, doc)


def indexar_arquivo(cfg: Config, path: Path) -> None:
    linha = _linha_do_arquivo(cfg, path)
    with closing(_conectar(cfg)) as con, con:
        con.execute("DELETE FROM indice WHERE tipo = ? AND id = ?", linha[:2])
        con.execute("INSERT INTO indice VALUES (?, ?, ?, ?, ?, ?, ?)", linha)


def reconstruir(cfg: Config) -> int:
    total = 0
    with closing(_conectar(cfg)) as con, con:
        con.execute("DELETE FROM indice")
        for md in sorted((cfg.base_dir / "leis").glob("*.md")):
            total += _inserir_lei(con, carregar_lei(cfg, md.stem))
        arquivos = sorted((cfg.base_dir / "categorias").glob("*/*.md")) + sorted(
            (cfg.base_dir / "precedentes").glob("*.md"))
        for path in arquivos:
            con.execute("INSERT INTO indice VALUES (?, ?, ?, ?, ?, ?, ?)", _linha_do_arquivo(cfg, path))
            total += 1
    return total


def _sem_acento(token: str) -> str:
    return unicodedata.normalize("NFKD", token).encode("ascii", "ignore").decode("ascii")


_PLURAIS = (("oes", "ao"), ("aes", "ao"), ("aos", "ao"), ("ais", "al"), ("eis", "el"), ("ns", "m"))


def _singular(p: str) -> str:
    """Singular aproximado (sem acento): prazos→prazo, acoes→acao, fiadores→fiador, bens→bem."""
    if len(p) < 4:
        return p
    for sufixo, troca in _PLURAIS:
        if p.endswith(sufixo) and len(p) > len(sufixo) + 1:
            return p[: -len(sufixo)] + troca
    if p.endswith(("res", "zes", "ses")) and len(p) > 4:
        return p[:-2]
    return p[:-1] if p.endswith("s") else p


def _formas(base: str) -> list[str]:
    """A palavra, o singular dela e, para -ao, o plural em -oes (o índice não tem radical)."""
    formas = [base, _singular(base)]
    if formas[1].endswith("ao"):
        formas.append(formas[1][:-2] + "oes")
    return formas


def _consulta(pergunta: str) -> str:
    termos = []
    for token in re.findall(r"\w+", pergunta.casefold()):
        base = _sem_acento(token)
        if not base or base in STOPWORDS:
            continue
        for forma in _formas(base):
            termo = f'"{forma[:6]}"*' if len(forma) >= 4 else f'"{forma}"'
            if termo not in termos:
                termos.append(termo)
    return " OR ".join(termos)


def buscar(cfg: Config, pergunta: str, limite: int = 8) -> list[Resultado]:
    consulta = _consulta(pergunta)
    if not consulta:
        return []
    if not (cfg.base_dir / ARQUIVO).exists():
        reconstruir(cfg)
    with closing(_conectar(cfg)) as con:
        linhas = con.execute(
            "SELECT tipo, id, snippet(indice, 3, '', '', '…', 40), fonte, capturado_em, estado, "
            "bm25(indice) FROM indice WHERE indice MATCH ? ORDER BY bm25(indice) LIMIT ?",
            (consulta, limite),
        ).fetchall()
    return [Resultado(t, i, tr, f, c, e, -s) for t, i, tr, f, c, e, s in linhas]
