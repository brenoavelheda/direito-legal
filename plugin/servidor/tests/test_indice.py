import pytest

from base_juridica.indice import buscar, indexar_arquivo, indexar_lei, reconstruir
from base_juridica.leis import baixar_lei, carregar_lei, salvar_lei


def test_busca_preferencia_locatario(cfg_com_l8245):
    r = buscar(cfg_com_l8245, "prazo para o inquilino exercer a preferência na compra")
    assert any(x.id == "lei-8245-1991#art-28" for x in r[:3])


def test_busca_ignora_acentos(cfg_com_cpc):
    assert [x.id for x in buscar(cfg_com_cpc, "impenhorabilidade poupanca salario")[:5]] == \
           [x.id for x in buscar(cfg_com_cpc, "impenhorabilidade poupança salário")[:5]]
    assert any(x.id == "lei-13105-2015#art-833" for x in buscar(cfg_com_cpc, "impenhoraveis poupanca")[:5])


def test_resultado_traz_fonte_e_estado(cfg_com_l8245):
    x = buscar(cfg_com_l8245, "preferência locatário")[0]
    assert x.fonte.startswith("https://www.planalto.gov.br") and x.estado in {"vigente", "revogado"} and x.capturado_em


def test_reconstruir_reflete_edicao_manual(cfg_com_l8245):
    (cfg_com_l8245.base_dir / "categorias" / "teste").mkdir(parents=True)
    (cfg_com_l8245.base_dir / "categorias" / "teste" / "guia.md").write_text("palavraunica xyzzy", encoding="utf-8")
    reconstruir(cfg_com_l8245)
    assert buscar(cfg_com_l8245, "xyzzy")[0].tipo == "categoria"


def test_pergunta_com_aspas_e_operadores_nao_quebra(cfg_com_l8245):
    assert isinstance(buscar(cfg_com_l8245, 'locação "residencial" AND OR NEAR('), list)


def test_pergunta_so_com_stopwords_devolve_vazio(cfg_com_l8245):
    assert buscar(cfg_com_l8245, "o que é a de") == []


def test_reconstruir_conta_itens(cfg_com_l8245):
    assert reconstruir(cfg_com_l8245) == len(carregar_lei(cfg_com_l8245, "lei-8245-1991").artigos)


def test_indexar_lei_substitui_versao_anterior(cfg_com_l8245):
    doc = carregar_lei(cfg_com_l8245, "lei-8245-1991")
    doc.artigos[27].texto = "texto trocado com termo qwertyuiop"
    salvar_lei(cfg_com_l8245, doc)
    indexar_lei(cfg_com_l8245, doc)
    assert buscar(cfg_com_l8245, "qwertyuiop")[0].id == f"lei-8245-1991#art-{doc.artigos[27].numero}"
    assert len([x for x in buscar(cfg_com_l8245, "inequívoca aceitação integral proposta", limite=50)
                if x.id == f"lei-8245-1991#art-{doc.artigos[27].numero}"]) <= 1


def test_indexar_arquivo_precedente_le_frontmatter(tmp_cfg):
    p = tmp_cfg.base_dir / "precedentes" / "stj-sumula-7.md"
    p.parent.mkdir()
    p.write_text('---\nid: "stj-sumula-7"\nurl: "https://scon.stj.jus.br/x"\n'
                 'capturado_em: "2026-11-15T10:00:00-03:00"\nestado: "vigente"\n---\n\n'
                 "A pretensão de simples reexame de prova não enseja recurso especial.\n", encoding="utf-8")
    indexar_arquivo(tmp_cfg, p)
    x = buscar(tmp_cfg, "reexame de prova")[0]
    assert (x.tipo, x.id, x.fonte, x.estado) == ("precedente", "stj-sumula-7", "https://scon.stj.jus.br/x", "vigente")


def test_indice_ausente_e_reconstruido_na_busca(tmp_cfg, fake_abrir_l8245):
    baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=fake_abrir_l8245)
    assert not (tmp_cfg.base_dir / "indice.sqlite").exists()
    assert buscar(tmp_cfg, "preferência locatário")


@pytest.mark.parametrize("pergunta", ["prazos", "multas", "dano", "danos", "prazo"])
def test_plural_e_singular_de_palavra_curta(tmp_cfg, pergunta):
    from base_juridica.categorias import integrar
    integrar(tmp_cfg, "x", "guia", "O prazo para a multa e os danos.",
             ["https://www.planalto.gov.br/ccivil_03/leis/l8245.htm"])
    assert buscar(tmp_cfg, pergunta), pergunta


def test_plural_em_es(tmp_cfg):
    from base_juridica.categorias import integrar
    integrar(tmp_cfg, "x", "guia", "A ação de despejo e o fiador.",
             ["https://www.planalto.gov.br/ccivil_03/leis/l8245.htm"])
    assert buscar(tmp_cfg, "ações") and buscar(tmp_cfg, "fiadores")
