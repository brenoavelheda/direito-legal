import pytest

from base_juridica.captura import CapturaFalhou, FonteNaoOficial, baixar
from conftest import abrir_com


def test_baixar_recusa_dominio_nao_oficial():
    with pytest.raises(FonteNaoOficial):
        baixar("https://www.migalhas.com.br/x")


def test_baixar_jus_recusa_planalto():
    with pytest.raises(FonteNaoOficial):
        baixar("https://www.planalto.gov.br/x", exigir="jus")


def test_baixar_decodifica_cp1252_e_calcula_sha(fake_abrir_bytes):
    c = baixar("https://www.planalto.gov.br/x", abrir=fake_abrir_bytes)
    assert "Preferência" in c.html and len(c.sha256) == 64


def test_baixar_utf8_quando_declarado():
    c = baixar("https://www.planalto.gov.br/x", abrir=abrir_com("ação".encode("utf-8"), content_type="text/html; charset=UTF-8"))
    assert c.html == "ação"


def test_baixar_erro_http_nomeia_url(fake_abrir_403):
    with pytest.raises(CapturaFalhou, match="planalto.gov.br/x"):
        baixar("https://www.planalto.gov.br/x", abrir=fake_abrir_403)


def test_baixar_recusa_pagina_grande():
    with pytest.raises(CapturaFalhou, match="10 MB"):
        baixar("https://www.planalto.gov.br/x", abrir=abrir_com(b"x" * (10 * 1024 * 1024 + 1)))


@pytest.mark.rede
def test_baixar_planalto_real():
    c = baixar("https://www.planalto.gov.br/ccivil_03/leis/l8245.htm")
    assert "Art. 28" in c.html


URL = "https://www.planalto.gov.br/ccivil_03/leis/l8245.htm"


def test_resposta_truncada_falha():
    from conftest import _Resposta

    class Truncada(_Resposta):
        length = 99850  # http.client: bytes do Content-Length ainda não lidos

    def abrir(req, timeout=None):
        return Truncada(b"<p>Art. 1</p>")

    with pytest.raises(CapturaFalhou, match="truncada"):
        baixar(URL, abrir=abrir)


@pytest.mark.parametrize("erro", ["IncompleteRead", "BadStatusLine", "RemoteDisconnected"])
def test_erro_http_client_vira_captura_falhou(erro):
    import http.client

    excecao = {"IncompleteRead": http.client.IncompleteRead(b"x", 10),
               "BadStatusLine": http.client.BadStatusLine("x"),
               "RemoteDisconnected": http.client.RemoteDisconnected("x")}[erro]

    def abrir(req, timeout=None):
        raise excecao

    with pytest.raises(CapturaFalhou, match="planalto"):
        baixar(URL, abrir=abrir)
