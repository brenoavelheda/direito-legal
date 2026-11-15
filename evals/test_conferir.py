from datetime import datetime, timezone

import pytest

from base_juridica.config import Config
from base_juridica.leis import salvar_lei
from base_juridica.modelos import Artigo, LeiDoc
from conferir import citacoes_reprovadas, contraditor_alterou, linhas_sem_tag, pontuar


def test_pontuar():
    assert pontuar("...\nALTERNATIVA: C\n", "C") and not pontuar("ALTERNATIVA: B", "C")


@pytest.mark.parametrize("resposta,gabarito,esperado", [
    ("ALTERNATIVA: (c)", "C", True),
    ("**ALTERNATIVA: D**", "D", True),
    ("ALTERNATIVA: A\n...\nALTERNATIVA: B", "B", True),
    ("sem linha final", "A", False),
    ("A alternativa correta é a C", "C", False),
])
def test_pontuar_variantes(resposta, gabarito, esperado):
    assert pontuar(resposta, gabarito) is esperado


def test_linhas_sem_tag():
    r = "## Fundamentos\n- prazo de 30 dias — art. 28 da Lei 8.245/91 [base — capturado 2026-11-15]\n- outra coisa sem fonte\n## Certeza: alta — x"
    assert linhas_sem_tag(r) == ["- outra coisa sem fonte"]


def test_linhas_sem_tag_aceita_todas_as_tags():
    r = ("## Resposta\n- fora da seção não conta\n## Fundamentos\n"
         "- a — Tema 1235/STJ [STJ]\n- b — x [comentário — dizerodireito.com.br]\n"
         "- c — y [conhecimento do modelo — verificar]\n- d — z [base — capturado 2026-11-15 — desatualizado]\n"
         "- e — prazo [base — capturado 2026-11-15] [verificar]\n- f — w [Planalto]\n\n## Certeza: alta — x")
    assert linhas_sem_tag(r) == []


def test_sem_secao_fundamentos_conta_como_falha():
    assert linhas_sem_tag("## Resposta\nsim") == ["<sem seção ## Fundamentos>"]


def test_citacoes_reprovadas(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    cfg = Config(base_dir=base)
    salvar_lei(cfg, LeiDoc("lei-8245-1991", [], "Lei 8.245", "https://www.planalto.gov.br/x",
                           datetime(2026, 11, 15, tzinfo=timezone.utc), "0" * 64, [Artigo("28", "Texto.")]))
    reprovadas = citacoes_reprovadas(cfg, "Ver art. 28 e art. 999 da Lei 8.245/91.")
    assert [v.citacao.artigo for v in reprovadas] == ["999"]


def test_contraditor_alterou():
    assert contraditor_alterou("## Contraditor: alterou — prazo é outro")
    assert not contraditor_alterou("## Contraditor: manteve")
    assert not contraditor_alterou("## Contraditor: dispensado")


def test_linhas_fundamentos():
    from conferir import linhas_fundamentos

    r = "## Fundamentos\n- a [STJ]\n- b\n\ntexto solto\n## Certeza: alta — x"
    assert linhas_fundamentos(r) == ["- a [STJ]", "- b"]
