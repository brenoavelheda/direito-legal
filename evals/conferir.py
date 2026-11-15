"""Conferência das respostas da skill consulta (formato fixo da Task 11).

- pontuar: a última linha "ALTERNATIVA: <letra>" bate com o gabarito?
- linhas_sem_tag: linhas de "## Fundamentos" sem marcador de proveniência.
- citacoes_reprovadas: citações que o verificar_citacoes não aprova.
"""

from __future__ import annotations

import re

from base_juridica.citacoes import Verificacao, verificar_citacoes
from base_juridica.config import Config

# Mesma expressão de plugin/marcadores.md.
RE_TAG = re.compile(
    r"\[(Planalto|STJ|STF|TST|TSE|TNU|TJ[A-Z]{2}|TRF\d|DataJud|base — capturado \d{4}-\d{2}-\d{2}( — desatualizado)?"
    r"|comentário — [^\]]+|conhecimento do modelo — verificar|verificar)\]"
)
RE_ALTERNATIVA = re.compile(r"ALTERNATIVA:\s*\(?\s*([A-E])\s*\)?", re.IGNORECASE)
RE_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def pontuar(resposta: str, gabarito: str) -> bool:
    achadas = RE_ALTERNATIVA.findall(resposta)
    return bool(achadas) and achadas[-1].upper() == gabarito.strip().upper()


def _secao(resposta: str, titulo: str) -> list[str] | None:
    linhas = resposta.replace("\r\n", "\n").split("\n")
    inicio = next((i for i, l in enumerate(linhas) if l.strip().startswith(f"## {titulo}")), None)
    if inicio is None:
        return None
    fim = next((i for i in range(inicio + 1, len(linhas)) if linhas[i].startswith("## ")), len(linhas))
    return linhas[inicio + 1 : fim]


def linhas_fundamentos(resposta: str) -> list[str]:
    """Itens de lista da seção ## Fundamentos ([] sem a seção)."""
    return [l.strip() for l in _secao(resposta, "Fundamentos") or [] if RE_ITEM.match(l)]


def linhas_sem_tag(resposta: str) -> list[str]:
    if _secao(resposta, "Fundamentos") is None:
        return ["<sem seção ## Fundamentos>"]
    return [l for l in linhas_fundamentos(resposta) if not RE_TAG.search(l)]


def citacoes_reprovadas(cfg: Config, resposta: str) -> list[Verificacao]:
    return [v for v in verificar_citacoes(cfg, resposta) if v.status != "ok"]


def contraditor_alterou(resposta: str) -> bool:
    m = re.search(r"^## Contraditor:\s*(\w+)", resposta, re.MULTILINE)
    return bool(m) and m.group(1).casefold() == "alterou"
