"""Escrita atômica e frontmatter dos markdown da base.

Os valores do frontmatter são literais JSON, que também são YAML válido:
nada de dependência de YAML e leitura sem perda.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

TENTATIVAS_REPLACE = 10  # no Windows, os.replace falha enquanto outro processo lê o destino


class TravaOcupada(Exception):
    """Outro processo está gravando na base há mais tempo que a espera."""


_trava_local = threading.local()
_trava_threads = threading.RLock()


@contextmanager
def trava(base_dir: Path, *, espera_s: float = 60, velha_s: float = 300) -> Iterator[None]:
    """Exclusão para ler-modificar-gravar na base: entre threads (RLock) e entre
    processos (arquivo base/.trava criado com O_EXCL). Reentrante na mesma thread.
    Trava com mais de velha_s segundos é de processo morto e é removida."""
    with _trava_threads:
        profundidade = getattr(_trava_local, "profundidade", 0)
        caminho = base_dir / ".trava"
        if profundidade == 0:
            limite = time.monotonic() + espera_s
            while True:
                try:
                    fd = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(fd, str(os.getpid()).encode("ascii"))
                    os.close(fd)
                    break
                except FileExistsError:
                    try:
                        if time.time() - caminho.stat().st_mtime > velha_s:
                            caminho.unlink(missing_ok=True)
                            continue
                    except FileNotFoundError:
                        continue
                    if time.monotonic() > limite:
                        raise TravaOcupada(f"base ocupada por outro processo ({caminho})") from None
                    time.sleep(0.05)
        _trava_local.profundidade = profundidade + 1
        try:
            yield
        finally:
            _trava_local.profundidade -= 1
            if _trava_local.profundidade == 0:
                caminho.unlink(missing_ok=True)


def gravar_atomico(destino: Path, texto: str) -> Path:
    """Grava num temporário da mesma pasta e troca com os.replace."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=f".{destino.stem}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        for tentativa in range(TENTATIVAS_REPLACE):
            try:
                os.replace(tmp, destino)
                break
            except PermissionError:
                if tentativa == TENTATIVAS_REPLACE - 1:
                    raise
                time.sleep(0.05 * (tentativa + 1))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return destino


def escrever_frontmatter(meta: dict[str, Any]) -> str:
    linhas = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items()]
    return "\n".join(["---", *linhas, "---", ""])


def ler_frontmatter(conteudo: str) -> tuple[dict[str, Any], str]:
    """Devolve (meta, corpo). Sem frontmatter: ({}, conteudo).

    Valor que não é JSON (frontmatter editado à mão) fica como texto.
    """
    conteudo = conteudo.replace("\r\n", "\n")
    if not conteudo.startswith("---\n"):
        return {}, conteudo
    fim = conteudo.find("\n---\n", 3)
    if fim < 0:
        return {}, conteudo
    meta: dict[str, Any] = {}
    for linha in conteudo[4:fim].split("\n"):
        chave, sep, valor = linha.partition(":")
        if not sep:
            continue
        valor = valor.strip()
        try:
            meta[chave.strip()] = json.loads(valor)
        except ValueError:
            meta[chave.strip()] = valor
    return meta, conteudo[fim + 5 :]
