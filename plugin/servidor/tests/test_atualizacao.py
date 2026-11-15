from datetime import date, datetime, timedelta, timezone

import pytest

from base_juridica.atualizacao import atualizar_lei, garantir_atual, redacao_em
from base_juridica.indice import buscar
from base_juridica.leis import baixar_lei, carregar_lei, salvar_lei
from base_juridica.modelos import Artigo, Redacao


@pytest.fixture
def abrir_que_falha_se_chamado():
    def abrir(req, timeout=None):
        raise AssertionError("não deveria recapturar")
    return abrir


@pytest.fixture
def l8245_doc(tmp_cfg, fake_abrir_l8245):
    return baixar_lei(tmp_cfg, "Lei 8.245/91", abrir=fake_abrir_l8245)


@pytest.fixture
def cfg_l8245_capturada_hoje(tmp_cfg, l8245_doc):
    return tmp_cfg


@pytest.fixture
def cfg_l8245_capturada_31_dias(tmp_cfg, l8245_doc):
    l8245_doc.capturado_em = datetime.now(timezone.utc) - timedelta(days=31)
    salvar_lei(tmp_cfg, l8245_doc)
    return tmp_cfg


@pytest.fixture
def cfg_l8245_antiga(tmp_cfg, l8245_doc):
    art4 = next(a for a in l8245_doc.artigos if a.numero == "4")
    art4.texto = "Texto antigo do art. 4 trocado para o teste."
    salvar_lei(tmp_cfg, l8245_doc)
    return tmp_cfg


def test_copia_recente_nao_recaptura(cfg_l8245_capturada_hoje, abrir_que_falha_se_chamado):
    _, desatualizado = garantir_atual(cfg_l8245_capturada_hoje, "lei-8245-1991", abrir=abrir_que_falha_se_chamado)
    assert desatualizado is False


def test_30_dias_ainda_e_atual(cfg_l8245_capturada_hoje, abrir_que_falha_se_chamado):
    agora = carregar_lei(cfg_l8245_capturada_hoje, "lei-8245-1991").capturado_em + timedelta(days=30)
    _, desatualizado = garantir_atual(cfg_l8245_capturada_hoje, "lei-8245-1991", agora=agora,
                                      abrir=abrir_que_falha_se_chamado)
    assert desatualizado is False


def test_copia_31_dias_recaptura(cfg_l8245_capturada_31_dias, fake_abrir_l8245):
    doc, desatualizado = garantir_atual(cfg_l8245_capturada_31_dias, "lei-8245-1991", abrir=fake_abrir_l8245)
    assert desatualizado is False and (datetime.now(timezone.utc) - doc.capturado_em).days == 0


def test_recaptura_falha_devolve_copia_marcada(cfg_l8245_capturada_31_dias, fake_abrir_403):
    doc, desatualizado = garantir_atual(cfg_l8245_capturada_31_dias, "lei-8245-1991", abrir=fake_abrir_403)
    assert desatualizado is True and doc.id == "lei-8245-1991"


def test_recaptura_bloqueada_devolve_copia_marcada(cfg_l8245_capturada_31_dias, fake_abrir_sem_artigos):
    antes = (cfg_l8245_capturada_31_dias.base_dir / "leis" / "lei-8245-1991.md").read_bytes()
    doc, desatualizado = garantir_atual(cfg_l8245_capturada_31_dias, "lei-8245-1991", abrir=fake_abrir_sem_artigos)
    assert desatualizado is True and len(doc.artigos) > 80
    assert (cfg_l8245_capturada_31_dias.base_dir / "leis" / "lei-8245-1991.md").read_bytes() == antes


def test_diff_registra_historico(cfg_l8245_antiga, fake_abrir_l8245):
    d = atualizar_lei(cfg_l8245_antiga, "lei-8245-1991", abrir=fake_abrir_l8245)
    assert "4" in d.alterados
    assert "lei-8245-1991" in (cfg_l8245_antiga.base_dir / "historico-normativo.md").read_text(encoding="utf-8")


def test_diff_reindexa(cfg_l8245_antiga, fake_abrir_l8245):
    atualizar_lei(cfg_l8245_antiga, "lei-8245-1991", abrir=fake_abrir_l8245)
    assert buscar(cfg_l8245_antiga, "reaver imóvel alugado multa pactuada")[0].id == "lei-8245-1991#art-4"


def test_sem_mudanca_nao_escreve_historico(cfg_l8245_capturada_hoje, fake_abrir_l8245):
    d = atualizar_lei(cfg_l8245_capturada_hoje, "lei-8245-1991", abrir=fake_abrir_l8245)
    assert (d.alterados, d.incluidos, d.removidos) == ([], [], [])
    assert not (cfg_l8245_capturada_hoje.base_dir / "historico-normativo.md").exists()


def test_diff_inclusao_e_remocao(tmp_cfg, l8245_doc, fake_abrir_l8245):
    l8245_doc.artigos = [a for a in l8245_doc.artigos if a.numero != "54-A"] + [Artigo("999", "Fantasma.")]
    salvar_lei(tmp_cfg, l8245_doc)
    d = atualizar_lei(tmp_cfg, "lei-8245-1991", abrir=fake_abrir_l8245)
    assert d.incluidos == ["54-A"] and d.removidos == ["999"]
    hist = (tmp_cfg.base_dir / "historico-normativo.md").read_text(encoding="utf-8")
    assert "Incluídos: 54-A" in hist and "Removidos: 999" in hist


def test_redacao_em_data(l8245_doc):
    art4 = next(a for a in l8245_doc.artigos if a.numero == "4")
    texto, incerto = redacao_em(art4, date(2005, 6, 1))
    assert "art. 924 do Código Civil" in texto and not incerto
    texto, incerto = redacao_em(art4, date(2012, 6, 1))
    assert incerto


def test_redacao_em_hoje_e_o_texto_vigente(l8245_doc):
    art4 = next(a for a in l8245_doc.artigos if a.numero == "4")
    assert redacao_em(art4, date(2026, 11, 15)) == (art4.texto, False)


def test_redacao_em_artigo_revogado():
    art = Artigo("9", "", revogado=True, notas=["(Revogado pela Lei nº 2, de 2015)"],
                 redacoes_anteriores=[Redacao("Texto antes da revogação.", None, None)])
    assert redacao_em(art, date(2010, 1, 1)) == ("Texto antes da revogação.", False)
    assert redacao_em(art, date(2015, 6, 1))[1] is True
    assert redacao_em(art, date(2020, 1, 1)) == ("", False)


def test_redacao_sem_data_e_incerta():
    art = Artigo("1", "Atual.", redacoes_anteriores=[Redacao("Antiga.", None, None)])
    assert redacao_em(art, date(2000, 1, 1))[1] is True


def test_recaptura_parcial_devolve_copia_marcada(cfg_l8245_capturada_31_dias):
    from conftest import abrir_com

    pagina = ("<p>LEI Nº 8.245, DE 18 DE OUTUBRO DE 1991</p><p>Art. 1º Só um artigo.</p>").encode("utf-8")
    doc, desatualizado = garantir_atual(cfg_l8245_capturada_31_dias, "lei-8245-1991",
                                        abrir=abrir_com(pagina, content_type="text/html; charset=utf-8"))
    assert desatualizado is True and len(doc.artigos) > 80


ART_5 = ("<html><body><p>Art. 5º Caput.</p><p><strike>§ 1º Antigo.</strike></p>"
         "<p>§ 1º Novo. (Redação dada pela Lei nº 9.999, de 2020)</p>"
         "<p>§ 2º X. (Incluído pela Lei nº 9.998, de 2022)</p></body></html>")


def _art(html, numero):
    from base_juridica.planalto import parse_lei

    return next(a for a in parse_lei(html) if a.numero == numero)


def test_redacao_em_monta_o_artigo_inteiro_na_data():
    art = _art(ART_5, "5")
    assert redacao_em(art, date(2019, 6, 1)) == ("Caput.\n§ 1º Antigo.", False)
    assert redacao_em(art, date(2021, 6, 1)) == ("Caput.\n§ 1º Novo.", False)
    assert redacao_em(art, date(2023, 6, 1)) == ("Caput.\n§ 1º Novo.\n§ 2º X.", False)
    texto, incerto = redacao_em(art, date(2022, 6, 1))
    assert incerto and "§ 2º X." in texto


def test_redacao_em_artigo_incluido_depois_nao_existia():
    art = _art("<p>Art. 54-A. Na locação não residencial. (Incluído pela Lei nº 12.744, de 2012)</p>", "54-A")
    assert redacao_em(art, date(2010, 1, 1)) == ("", False)
    assert redacao_em(art, date(2013, 1, 1)) == ("Na locação não residencial.", False)


def test_redacao_dada_sem_texto_antigo_e_incerta():
    art = _art("<p>Art. 7º Texto atual. (Redação dada pela Lei nº 9.000, de 2015)</p>", "7")
    assert redacao_em(art, date(2010, 1, 1)) == ("Texto atual.", True)
