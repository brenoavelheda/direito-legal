import io
import urllib.error
from pathlib import Path

import pytest

from base_juridica.config import Config
from base_juridica.indice import reconstruir
from base_juridica.leis import baixar_lei


class _Resposta:
    def __init__(self, corpo: bytes, status: int = 200, content_type: str = "text/html"):
        self._corpo = corpo
        self.status = status
        self.headers = {"Content-Type": content_type}

    def read(self, n: int = -1) -> bytes:
        return self._corpo if n < 0 else self._corpo[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def abrir_com(corpo: bytes, status: int = 200, content_type: str = "text/html"):
    def abrir(req, timeout=None):
        return _Resposta(corpo, status, content_type)

    return abrir


def abrir_http_erro(codigo: int):
    def abrir(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, codigo, "erro", {}, io.BytesIO(b""))

    return abrir


@pytest.fixture
def fake_abrir_bytes():
    return abrir_com("<p>Art. 1º Preferência</p>".encode("cp1252"))


@pytest.fixture
def fake_abrir_403():
    return abrir_http_erro(403)


FIXTURES = Path(__file__).parent / "fixtures"



@pytest.fixture
def tmp_cfg(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    return Config(base_dir=base)


@pytest.fixture
def fake_abrir_l8245():
    return abrir_com((FIXTURES / "planalto-l8245.htm").read_bytes())


@pytest.fixture
def fake_abrir_sem_artigos():
    return abrir_com("<html><body><p>Verificando se você é humano...</p></body></html>".encode("utf-8"),
                     content_type="text/html; charset=utf-8")


@pytest.fixture
def cfg_com_l8245(tmp_cfg, fake_abrir_l8245):
    baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=fake_abrir_l8245)
    reconstruir(tmp_cfg)
    return tmp_cfg


@pytest.fixture
def cfg_com_cpc(tmp_cfg):
    baixar_lei(tmp_cfg, "CPC", abrir=abrir_com((FIXTURES / "planalto-l13105.htm").read_bytes()))
    reconstruir(tmp_cfg)
    return tmp_cfg


@pytest.fixture(autouse=True)
def _pasta_padrao_isolada(tmp_path, monkeypatch):
    # Nenhum teste cria ~/direito-legal-dados de verdade.
    from base_juridica import config
    monkeypatch.setattr(config, "pasta_padrao", lambda: tmp_path / "padrao-direito-legal-dados")
