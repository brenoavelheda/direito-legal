from datetime import date, datetime, timedelta, timezone

import pytest

from base_juridica.captura import FonteNaoOficial
from base_juridica.catalogo import CATALOGO, ReferenciaDesconhecida, resolver_referencia
from base_juridica.fontes import classificar_fonte
from base_juridica.leis import LeiAusente, baixar_lei, carregar_lei, salvar_lei
from base_juridica.modelos import Artigo, LeiDoc, Redacao
from base_juridica.planalto import ParseVazio

URL_8245 = "https://www.planalto.gov.br/ccivil_03/leis/l8245.htm"


@pytest.fixture
def lei_exemplo():
    return LeiDoc(
        id="lei-8245-1991",
        apelidos=["Lei do Inquilinato"],
        titulo="Lei nº 8.245, de 18 de outubro de 1991",
        url=URL_8245,
        capturado_em=datetime(2026, 11, 15, 10, 30, tzinfo=timezone(timedelta(hours=-3))),
        sha256="ab" * 32,
        artigos=[
            Artigo(
                numero="4",
                texto="Durante o prazo estipulado...\nParágrafo único. O locatário ficará dispensado...",
                notas=["(Redação dada pela Lei nº 12.744, de 2012)"],
                redacoes_anteriores=[
                    Redacao("Texto original do art. 4º.", None, None),
                    Redacao("Texto de 2009.", "Lei nº 12.744, de 2012", date(2012, 1, 1)),
                ],
            ),
            Artigo(numero="54-A", texto="Na locação não residencial..."),
            Artigo(numero="77", texto="", revogado=True, notas=["(Revogado pela Lei nº 9.999, de 2010)"]),
            Artigo(numero="78", texto="# linha que começa com cerquilha\n\\ e outra com barra"),
        ],
    )


@pytest.fixture
def lei_8245_ja_salva(tmp_cfg, lei_exemplo):
    salvar_lei(tmp_cfg, lei_exemplo)
    return lei_exemplo


@pytest.mark.parametrize("ref,id_", [
    ("CPC", "lei-13105-2015"), ("cpc/2015", "lei-13105-2015"),
    ("Lei 8.245/91", "lei-8245-1991"), ("Lei nº 8.245, de 18 de outubro de 1991", "lei-8245-1991"),
    ("Lei 10.931/2004", "lei-10931-2004"), ("Decreto-Lei 911/69", "dl-911-1969"),
    ("Lei 14.905/2024", "lei-14905-2024"),
])
def test_resolver_referencia(ref, id_):
    assert resolver_referencia(ref) == id_


@pytest.mark.parametrize("ref,id_", [
    ("Constituição", "cf-1988"), ("CF/88", "cf-1988"), ("código civil", "lei-10406-2002"),
    ("LINDB", "dl-4657-1942"), ("Lei 8.009", "lei-8009-1990"), ("lei-8245-1991", "lei-8245-1991"),
    ("DECRETO-LEI Nº 911, DE 1º DE OUTUBRO DE 1969", "dl-911-1969"),
    ("Lei Complementar nº 123, de 14 de dezembro de 2006", "lc-123-2006"),
])
def test_resolver_referencia_variantes(ref, id_):
    assert resolver_referencia(ref) == id_


@pytest.mark.parametrize("ref", ["", "lei do bairro", "../../etc/passwd", "Lei 99.999"])
def test_resolver_referencia_desconhecida(ref):
    with pytest.raises(ReferenciaDesconhecida):
        resolver_referencia(ref)


def test_catalogo_so_tem_urls_do_planalto():
    assert len(CATALOGO) == 12
    assert all(classificar_fonte(i.url) == "oficial" and "planalto.gov.br" in i.url for i in CATALOGO)
    assert len({i.id for i in CATALOGO}) == len(CATALOGO)


def test_roundtrip_md(tmp_cfg, lei_exemplo):
    carregado = carregar_lei(tmp_cfg, salvar_lei(tmp_cfg, lei_exemplo).stem)
    assert carregado == lei_exemplo


def test_salvar_nao_deixa_temporario(tmp_cfg, lei_exemplo):
    salvar_lei(tmp_cfg, lei_exemplo)
    assert [p.name for p in (tmp_cfg.base_dir / "leis").iterdir()] == ["lei-8245-1991.md"]


def test_carregar_ausente(tmp_cfg):
    with pytest.raises(LeiAusente):
        carregar_lei(tmp_cfg, "lei-8245-1991")


@pytest.mark.parametrize("id_", ["../segredo", "lei/../../x", "LEI-1-2000", ""])
def test_carregar_id_invalido(tmp_cfg, id_):
    with pytest.raises(LeiAusente):
        carregar_lei(tmp_cfg, id_)


def test_baixar_lei_grava_e_parseia(tmp_cfg, fake_abrir_l8245):
    doc = baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=fake_abrir_l8245)
    assert doc.id == "lei-8245-1991" and (tmp_cfg.base_dir / "leis" / "lei-8245-1991.md").exists()
    assert doc.url == URL_8245 and doc.apelidos == ["Lei do Inquilinato"]
    assert carregar_lei(tmp_cfg, "lei-8245-1991") == doc


def test_baixar_lei_por_url_fora_do_catalogo_identifica_pelo_cabecalho(tmp_cfg, fake_abrir_l8245):
    doc = baixar_lei(tmp_cfg, "https://www.planalto.gov.br/ccivil_03/leis/outra.htm", abrir=fake_abrir_l8245)
    assert doc.id == "lei-8245-1991" and doc.titulo.upper().startswith("LEI Nº 8.245")


def test_baixar_lei_nao_grava_quando_parse_vazio(tmp_cfg, fake_abrir_sem_artigos, lei_8245_ja_salva):
    antes = (tmp_cfg.base_dir / "leis" / "lei-8245-1991.md").read_bytes()
    with pytest.raises(ParseVazio) as exc:
        baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=fake_abrir_sem_artigos)
    assert URL_8245 in str(exc.value)
    assert (tmp_cfg.base_dir / "leis" / "lei-8245-1991.md").read_bytes() == antes


def test_baixar_lei_fora_do_catalogo_sem_url(tmp_cfg, fake_abrir_l8245):
    with pytest.raises(ReferenciaDesconhecida, match="URL"):
        baixar_lei(tmp_cfg, "Lei 14.905/2024", abrir=fake_abrir_l8245)


def test_baixar_lei_recusa_url_nao_oficial(tmp_cfg, fake_abrir_l8245):
    with pytest.raises(FonteNaoOficial):
        baixar_lei(tmp_cfg, "https://www.jusbrasil.com.br/legislacao/l8245", abrir=fake_abrir_l8245)


@pytest.mark.rede
def test_rede_dl_911_no_planalto(tmp_cfg):
    doc = baixar_lei(tmp_cfg, "Decreto-Lei 911/69")
    assert doc.id == "dl-911-1969" and {"2", "3", "8-A"} <= {a.numero for a in doc.artigos}


@pytest.mark.parametrize("ref,id_", [
    ("Decreto nº 12.797, de 30 de dezembro de 2025", "dec-12797-2025"),
    ("DECRETO Nº 12.797, DE 30 DE DEZEMBRO DE 2025", "dec-12797-2025"),
    ("Decreto 12.797/2025", "dec-12797-2025"),
    ("dec-12797-2025", "dec-12797-2025"),
])
def test_resolver_decreto(ref, id_):
    assert resolver_referencia(ref) == id_


def test_decreto_salva_e_carrega(tmp_cfg, lei_exemplo):
    lei_exemplo.id = "dec-12797-2025"
    assert carregar_lei(tmp_cfg, salvar_lei(tmp_cfg, lei_exemplo).stem).id == "dec-12797-2025"


PAGINA_2_ARTIGOS = ("<html><body><p>LEI Nº 8.245, DE 18 DE OUTUBRO DE 1991</p>"
                    "<p>Art. 1º A locação de imóvel urbano regula-se pelo disposto nesta lei.</p>"
                    "<p>Art. 2º Havendo mais de um locador ou mais de um locatário, entende-se que são solidários.</p>"
                    "</body></html>").encode("utf-8")


def test_baixar_lei_url_nao_sobrescreve_lei_existente(tmp_cfg, fake_abrir_l8245):
    from base_juridica.leis import FonteConflitante

    from conftest import abrir_com

    baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=fake_abrir_l8245)
    antes = (tmp_cfg.base_dir / "leis" / "lei-8245-1991.md").read_bytes()
    with pytest.raises(FonteConflitante, match="l8245"):
        baixar_lei(tmp_cfg, "https://www2.camara.leg.br/legin/fed/lei/1991/lei-8245-publicacaooriginal.html",
                   abrir=abrir_com(PAGINA_2_ARTIGOS, content_type="text/html; charset=utf-8"))
    assert (tmp_cfg.base_dir / "leis" / "lei-8245-1991.md").read_bytes() == antes


def test_baixar_lei_parcial_nao_grava(tmp_cfg, fake_abrir_l8245):
    from base_juridica.leis import LeiParcial

    from conftest import abrir_com

    baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=fake_abrir_l8245)
    antes = (tmp_cfg.base_dir / "leis" / "lei-8245-1991.md").read_bytes()
    with pytest.raises(LeiParcial, match="91"):
        baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=abrir_com(PAGINA_2_ARTIGOS, content_type="text/html; charset=utf-8"))
    assert issubclass(LeiParcial, ParseVazio)
    assert (tmp_cfg.base_dir / "leis" / "lei-8245-1991.md").read_bytes() == antes


def test_rebaixar_por_url_fora_do_catalogo_mantem_apelidos(tmp_cfg, lei_exemplo, fake_abrir_l8245):
    lei_exemplo.id, lei_exemplo.url = "lei-8245-1991", "https://www.planalto.gov.br/ccivil_03/leis/outra.htm"
    lei_exemplo.apelidos = ["Apelido manual"]
    lei_exemplo.artigos = lei_exemplo.artigos[:2]
    salvar_lei(tmp_cfg, lei_exemplo)
    doc = baixar_lei(tmp_cfg, "https://www.planalto.gov.br/ccivil_03/leis/outra.htm", abrir=fake_abrir_l8245)
    assert doc.apelidos == ["Apelido manual"] and len(doc.artigos) > 80


def test_catalogo_decide_a_url_mesmo_com_copia_de_url_antiga(tmp_cfg, fake_abrir_l8245):
    doc = baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=fake_abrir_l8245)
    doc.url = "https://www.planalto.gov.br/ccivil_03/leis/l8245compilado.htm"
    salvar_lei(tmp_cfg, doc)
    assert baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=fake_abrir_l8245).url == URL_8245


def test_roundtrip_md_com_marcos(tmp_cfg, lei_exemplo):
    from base_juridica.modelos import Marco

    lei_exemplo.artigos[0].marcos = [Marco("§2o", "incluido", 2022), Marco("caput", "redacao", 2012)]
    assert carregar_lei(tmp_cfg, salvar_lei(tmp_cfg, lei_exemplo).stem) == lei_exemplo
