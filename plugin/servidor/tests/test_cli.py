from base_juridica.catalogo import CATALOGO
from base_juridica.cli import main

from conftest import FIXTURES, abrir_com, abrir_http_erro


def test_baixar_acervo_nao_para_no_erro(tmp_cfg, monkeypatch, capsys):
    monkeypatch.setenv("BASE_DIR", str(tmp_cfg.base_dir))
    pagina = (FIXTURES / "planalto-l8245.htm").read_bytes()
    ok, erro = abrir_com(pagina), abrir_http_erro(403)
    chamadas = []

    def abrir(req, timeout=None):
        chamadas.append(req.full_url)
        return (erro if len(chamadas) == 1 else ok)(req, timeout)

    assert main(["baixar-acervo"], abrir=abrir) == 1
    linhas = capsys.readouterr().out.strip().split("\n")
    assert linhas[0].startswith(f"falhou {CATALOGO[0].id} ")
    assert all(l.startswith("ok ") for l in linhas[1 : len(CATALOGO)])
    assert linhas[-1].startswith("índice:")


def test_reconstruir_indice(cfg_com_l8245, monkeypatch, capsys):
    monkeypatch.setenv("BASE_DIR", str(cfg_com_l8245.base_dir))
    assert main(["reconstruir-indice"]) == 0
    assert "itens" in capsys.readouterr().out
