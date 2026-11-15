import asyncio
import json

import pytest

from base_juridica import arquivos, categorias
from base_juridica.server import mcp

from conftest import abrir_com, FIXTURES


def chamar(ferramenta, /, **kw):
    r = asyncio.run(mcp.call_tool(ferramenta, kw))
    return json.loads(r.content[0].text)


@pytest.fixture
def cfg_env_vazio(tmp_cfg, monkeypatch):
    monkeypatch.setenv("BASE_DIR", str(tmp_cfg.base_dir))
    return tmp_cfg


@pytest.fixture
def cfg_env_com_l8245(cfg_com_l8245, monkeypatch):
    monkeypatch.setenv("BASE_DIR", str(cfg_com_l8245.base_dir))
    return cfg_com_l8245


def test_ferramentas_expostas():
    nomes = {t.name for t in asyncio.run(mcp.list_tools())}
    assert nomes == {"configuracao","buscar","ler_artigo","listar_categorias","ler_categoria","baixar_lei","baixar_precedente","integrar","verificar_citacoes","atualizar"}


def test_nome_do_servidor():
    assert mcp.name == "base-juridica"


def test_ler_artigo_envelopado(cfg_env_com_l8245):
    r = chamar("ler_artigo", lei="Lei 8.245/91", artigo="28")
    assert r["texto"].startswith("<<<conteúdo recuperado") and r["estado"] == "vigente" and r["desatualizado"] is False


def test_ler_artigo_com_data(cfg_env_com_l8245):
    r = chamar("ler_artigo", lei="lei-8245-1991", artigo="4", data="2005-06-01")
    assert "art. 924 do Código Civil" in r["texto"] and r["incerto"] is False


@pytest.mark.parametrize("artigo", ["art. 54-A", "54-A", "Art. 54-A."])
def test_ler_artigo_aceita_variantes(cfg_env_com_l8245, artigo):
    assert chamar("ler_artigo", lei="Lei do Inquilinato", artigo=artigo)["artigo"] == "54-A"


def test_ler_artigo_inexistente(cfg_env_com_l8245):
    assert chamar("ler_artigo", lei="lei-8245-1991", artigo="999")["erro"] == "ArtigoAusente"


def test_ler_artigo_lei_ausente(cfg_env_vazio):
    r = chamar("ler_artigo", lei="CPC", artigo="833")
    assert r["erro"] == "LeiAusente" and "baixar_lei" in r["mensagem"]


def test_integrar_erro_vira_mensagem(cfg_env_vazio):
    r = chamar("integrar", categoria="x", secao="guia", conteudo="y", fontes=[])
    assert r["erro"] == "SemFonte"


def test_pasta_de_dados_inexistente_vira_mensagem(monkeypatch, tmp_path):
    monkeypatch.delenv("BASE_DIR", raising=False)
    monkeypatch.setenv("DIREITO_LEGAL_DADOS", str(tmp_path / "nao-existe"))
    assert chamar("listar_categorias")["erro"] == "ConfigError"


def test_buscar_envelopa_trechos(cfg_env_com_l8245):
    r = chamar("buscar", pergunta="preferência locatário")
    assert r["resultados"] and all(x["trecho"].startswith("<<<conteúdo recuperado") for x in r["resultados"])


def test_integrar_listar_e_ler(cfg_env_vazio):
    r = chamar("integrar", categoria="Locação residencial", secao="guia", conteudo="Resumo.",
               fontes=["https://www.planalto.gov.br/ccivil_03/leis/l8245.htm"])
    assert r["slug"] == "locacao-residencial" and r["criada"] is True
    assert chamar("listar_categorias")["categorias"][0]["slug"] == "locacao-residencial"
    secoes = chamar("ler_categoria", nome="Locação residencial")["secoes"]
    assert "Resumo." in secoes["guia"] and secoes["guia"].startswith("<<<conteúdo recuperado")


def test_ler_categoria_travessia(cfg_env_vazio):
    assert chamar("ler_categoria", nome="../leis")["erro"] == "SlugInvalido"


def test_verificar_citacoes(cfg_env_com_l8245):
    r = chamar("verificar_citacoes", texto="Ver art. 28 e art. 999 da Lei 8.245/91.")
    assert [c["status"] for c in r["citacoes"]] == ["ok", "nao_encontrada"]


def test_baixar_lei_e_atualizar(cfg_env_vazio, monkeypatch):
    import base_juridica.server as s

    monkeypatch.setattr(s, "_abrir", abrir_com((FIXTURES / "planalto-l8245.htm").read_bytes()))
    r = chamar("baixar_lei", referencia="Lei 8.245/91")
    assert r["lei"] == "lei-8245-1991" and r["artigos"] > 80
    assert chamar("buscar", pergunta="preferência locatário")["resultados"]
    assert chamar("atualizar", lei="Lei 8.245/91") == {"lei": "lei-8245-1991", "alterados": [], "incluidos": [], "removidos": []}


def test_baixar_precedente(cfg_env_vazio, monkeypatch):
    import base_juridica.server as s

    monkeypatch.setattr(s, "_abrir", abrir_com(b"", status=403))
    r = chamar("baixar_precedente", tribunal="STJ", tipo="súmula", numero="7",
               enunciado="A pretensão de simples reexame de prova não enseja recurso especial.",
               url="https://scon.stj.jus.br/x")
    assert r["id"] == "stj-sumula-7" and r["conferido"] is False and "[verificar]" in r["aviso"]


def test_base_ocupada_vira_mensagem(cfg_env_vazio, monkeypatch):
    real = arquivos.trava
    monkeypatch.setattr(categorias, "trava", lambda base_dir: real(base_dir, espera_s=0.1))
    (cfg_env_vazio.base_dir / ".trava").write_text("999999", encoding="ascii")
    r = chamar("integrar", categoria="Locação", secao="guia", conteudo="x",
               fontes=["https://www.planalto.gov.br/ccivil_03/leis/l8245.htm"])
    assert r["erro"] == "TravaOcupada"


def test_configuracao_mostra_as_pastas(cfg_env_vazio):
    r = chamar("configuracao")
    dados = cfg_env_vazio.base_dir.parent
    assert r["base"] == str(cfg_env_vazio.base_dir) and r["dados"] == str(dados)
    assert r["perfil"] == str(dados / "perfil.md") and r["perfil_existe"] is False
    assert r["casos"] == str(dados / "casos")
