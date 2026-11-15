import pytest

from base_juridica.fontes import classificar_fonte, eh_jus_br


@pytest.mark.parametrize("url,esperado", [
    ("https://www.planalto.gov.br/ccivil_03/leis/l8245.htm", "oficial"),
    ("https://scon.stj.jus.br/x", "oficial"),
    ("https://www.gov.br/anpd/pt-br", "oficial"),
    ("https://portal.cfm.org.br/x", "oficial"),
    ("https://www.migalhas.com.br/x", "comentario"),
    ("https://planalto.gov.br.evil.com/x", "comentario"),
    ("http://jus.br.example.com/x", "comentario"),
])
def test_classificar_fonte(url, esperado):
    assert classificar_fonte(url) == esperado


def test_eh_jus_br():
    assert eh_jus_br("https://processo.stj.jus.br/x")
    assert not eh_jus_br("https://www.planalto.gov.br/x")
    assert not eh_jus_br("https://stj.jus.br.evil.com/x")
