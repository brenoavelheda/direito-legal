"""Captura de páginas oficiais com cabeçalhos de navegador."""

from __future__ import annotations

import hashlib
import http.client
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Literal

from .fontes import classificar_fonte, eh_jus_br
from .modelos import Captura

LIMITE_BYTES = 10 * 1024 * 1024
TIMEOUT_S = 60
CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class FonteNaoOficial(Exception):
    """URL fora dos domínios permitidos."""


class CapturaFalhou(Exception):
    """Falha de rede, HTTP diferente de 200 ou página grande demais."""


def _charset(content_type: str, corpo: bytes) -> str | None:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        return m.group(1)
    m = re.search(rb"charset=[\"']?([\w-]+)", corpo[:4096], re.I)
    return m.group(1).decode("ascii") if m else None


def _decodificar(corpo: bytes, content_type: str) -> str:
    declarado = _charset(content_type, corpo)
    for enc in [e for e in (declarado, "utf-8") if e]:
        try:
            return corpo.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return corpo.decode("cp1252", errors="replace")


def baixar(
    url: str,
    *,
    exigir: Literal["oficial", "jus"] = "oficial",
    abrir=urllib.request.urlopen,
) -> Captura:
    permitido = eh_jus_br(url) if exigir == "jus" else classificar_fonte(url) == "oficial"
    if not permitido:
        raise FonteNaoOficial(f"domínio não permitido ({exigir}): {url}")
    req = urllib.request.Request(url, headers=CABECALHOS)
    try:
        with abrir(req, timeout=TIMEOUT_S) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                raise CapturaFalhou(f"HTTP {status} em {url}")
            corpo = resp.read(LIMITE_BYTES + 1)
            restante = getattr(resp, "length", None)
            if len(corpo) <= LIMITE_BYTES and restante:
                # http.client: corpo menor que o Content-Length (conexão caiu no meio).
                raise CapturaFalhou(f"resposta truncada em {url}: faltaram {restante} bytes")
            content_type = resp.headers.get("Content-Type", "") if resp.headers else ""
    except CapturaFalhou:
        raise
    except urllib.error.HTTPError as e:
        raise CapturaFalhou(f"HTTP {e.code} em {url}") from e
    except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException) as e:
        raise CapturaFalhou(f"falha de rede em {url}: {e}") from e
    if len(corpo) > LIMITE_BYTES:
        raise CapturaFalhou(f"página acima de 10 MB: {url}")
    return Captura(
        url=url,
        html=_decodificar(corpo, content_type),
        sha256=hashlib.sha256(corpo).hexdigest(),
        capturado_em=datetime.now(timezone.utc),
    )
