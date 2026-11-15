import pytest

from base_juridica.captura import FonteNaoOficial
from base_juridica.indice import buscar
from base_juridica.precedentes import (
    PrecedenteAusente, carregar_precedente, id_precedente, registrar_precedente,
)

from conftest import abrir_com

TEMA_1235 = ("A impenhorabilidade de quantia inferior a 40 salários mínimos (art. 833, X, do CPC) "
             "não é matéria de ordem pública")


@pytest.fixture
def fake_abrir_html_com_enunciado():
    pagina = ("<html><body><h1>Tema Repetitivo 1235</h1><p>Tese firmada: A   impenhorabilidade de quantia "
              "inferior a 40 <b>salarios minimos</b> (art. 833, X, do CPC) não é matéria de ordem "
              "pública e não pode ser reconhecida de ofício pelo juiz.</p></body></html>")
    return abrir_com(pagina.encode("utf-8"), content_type="text/html; charset=utf-8")


@pytest.fixture
def fake_abrir_html_outro_texto():
    return abrir_com("<p>Súmula Vinculante 25: É ilícita a prisão civil de depositário infiel.</p>".encode("utf-8"),
                     content_type="text/html; charset=utf-8")


@pytest.mark.parametrize("args,id_", [
    (("STJ", "súmula", "7"), "stj-sumula-7"),
    (("STF", "súmula vinculante", "25"), "stf-sv-25"),
    (("STJ", "tema", "1.235"), "stj-tema-1235"),
    (("stj", "Tema Repetitivo", "1235"), "stj-tema-1235"),
    (("STF", "SV", "25"), "stf-sv-25"),
])
def test_id_precedente(args, id_):
    assert id_precedente(*args) == id_


@pytest.mark.parametrize("args", [("ST/J", "súmula", "7"), ("STJ", "súmula", "7/../../x"), ("STJ", "", "7")])
def test_id_precedente_invalido(args):
    with pytest.raises(ValueError):
        id_precedente(*args)


def test_conferido_quando_enunciado_na_pagina(tmp_cfg, fake_abrir_html_com_enunciado):
    d = registrar_precedente(tmp_cfg, "STJ", "tema", "1235", TEMA_1235, "https://processo.stj.jus.br/repetitivos/x",
                             abrir=fake_abrir_html_com_enunciado)
    assert d.id == "stj-tema-1235" and d.conferido and d.sha256


def test_nao_conferido_quando_site_bloqueia(tmp_cfg, fake_abrir_403):
    d = registrar_precedente(tmp_cfg, "STJ", "súmula", "7", "A pretensão de simples reexame de prova não enseja recurso especial.",
                             "https://scon.stj.jus.br/x", abrir=fake_abrir_403)
    assert not d.conferido and d.sha256 is None and (tmp_cfg.base_dir / "precedentes" / "stj-sumula-7.md").exists()


def test_recusa_url_fora_do_jus(tmp_cfg):
    with pytest.raises(FonteNaoOficial):
        registrar_precedente(tmp_cfg, "STJ", "súmula", "7", "x", "https://www.dizerodireito.com.br/x")
    assert not (tmp_cfg.base_dir / "precedentes").exists()


def test_enunciado_diferente_da_pagina_nao_confere(tmp_cfg, fake_abrir_html_outro_texto):
    assert not registrar_precedente(tmp_cfg, "STF", "súmula vinculante", "25", "texto que não está na página",
                                    "https://portal.stf.jus.br/x", abrir=fake_abrir_html_outro_texto).conferido


def test_estado_cancelada_preservado(tmp_cfg, fake_abrir_403):
    registrar_precedente(tmp_cfg, "STJ", "súmula", "1", "x", "https://scon.stj.jus.br/x", estado="cancelada",
                         abrir=fake_abrir_403)
    assert carregar_precedente(tmp_cfg, "stj-sumula-1").estado == "cancelada"


def test_estado_invalido(tmp_cfg, fake_abrir_403):
    with pytest.raises(ValueError):
        registrar_precedente(tmp_cfg, "STJ", "súmula", "1", "x", "https://scon.stj.jus.br/x", estado="talvez",
                             abrir=fake_abrir_403)


def test_roundtrip_e_indexado(tmp_cfg, fake_abrir_html_com_enunciado):
    d = registrar_precedente(tmp_cfg, "STJ", "tema", "1235", TEMA_1235, "https://processo.stj.jus.br/repetitivos/x",
                             abrir=fake_abrir_html_com_enunciado)
    assert carregar_precedente(tmp_cfg, "stj-tema-1235") == d
    x = buscar(tmp_cfg, "impenhorabilidade ordem pública")[0]
    assert (x.tipo, x.id, x.fonte) == ("precedente", "stj-tema-1235", "https://processo.stj.jus.br/repetitivos/x")


def test_registrar_de_novo_substitui(tmp_cfg, fake_abrir_403):
    registrar_precedente(tmp_cfg, "STJ", "súmula", "1", "x", "https://scon.stj.jus.br/x", abrir=fake_abrir_403)
    registrar_precedente(tmp_cfg, "STJ", "súmula", "1", "x", "https://scon.stj.jus.br/x", estado="cancelada",
                         abrir=fake_abrir_403)
    assert [p.name for p in (tmp_cfg.base_dir / "precedentes").iterdir()] == ["stj-sumula-1.md"]


def test_carregar_ausente(tmp_cfg):
    with pytest.raises(PrecedenteAusente):
        carregar_precedente(tmp_cfg, "stj-sumula-999")
    with pytest.raises(PrecedenteAusente):
        carregar_precedente(tmp_cfg, "../leis/x")


PAGINA_SUMULAS = ("<p>Súmula 7 — A pretensão de simples reexame de prova não enseja recurso especial.</p>"
                  "<p>Súmula 8 — Aplica-se a correção monetária aos créditos habilitados em concordata preventiva, "
                  "salvo durante o período compreendido entre as datas de vigência da Lei 7.274.</p>").encode("utf-8")
SUMULA_7 = "A pretensão de simples reexame de prova não enseja recurso especial."


def test_enunciado_de_outro_numero_nao_confere(tmp_cfg):
    d = registrar_precedente(tmp_cfg, "STJ", "súmula", "8", SUMULA_7, "https://scon.stj.jus.br/x",
                             abrir=abrir_com(PAGINA_SUMULAS, content_type="text/html; charset=utf-8"))
    assert not d.conferido


def test_enunciado_certo_confere_na_pagina_com_varias(tmp_cfg):
    d = registrar_precedente(tmp_cfg, "STJ", "súmula", "7", SUMULA_7, "https://scon.stj.jus.br/x",
                             abrir=abrir_com(PAGINA_SUMULAS, content_type="text/html; charset=utf-8"))
    assert d.conferido


def test_enunciado_curto_demais_nao_confere(tmp_cfg):
    d = registrar_precedente(tmp_cfg, "STJ", "súmula", "7", "prova", "https://scon.stj.jus.br/x",
                             abrir=abrir_com(PAGINA_SUMULAS, content_type="text/html; charset=utf-8"))
    assert not d.conferido


def test_registro_nao_conferido_nao_rebaixa_conferido(tmp_cfg, fake_abrir_html_com_enunciado, fake_abrir_403):
    registrar_precedente(tmp_cfg, "STJ", "tema", "1235", TEMA_1235, "https://processo.stj.jus.br/repetitivos/x",
                         abrir=fake_abrir_html_com_enunciado)
    d = registrar_precedente(tmp_cfg, "STJ", "tema", "1235", "outro texto qualquer", "https://scon.stj.jus.br/y",
                             estado="superada", abrir=fake_abrir_403)
    salvo = carregar_precedente(tmp_cfg, "stj-tema-1235")
    assert d == salvo
    assert salvo.conferido and salvo.enunciado == TEMA_1235 and salvo.estado == "superada"


def test_pagina_de_tema_com_outros_numeros_antes_da_tese_confere(tmp_cfg):
    pagina = ("<h1>Tema Repetitivo 1235</h1><p>Processo: REsp 1.677.144/RS, julgado em 26/10/2023, "
              "relator Min. Fulano. Ramo do direito: processual civil.</p>"
              f"<p>Tese firmada: {TEMA_1235} e não pode ser reconhecida de ofício.</p>").encode("utf-8")
    d = registrar_precedente(tmp_cfg, "STJ", "tema", "1235", TEMA_1235, "https://processo.stj.jus.br/repetitivos/x",
                             abrir=abrir_com(pagina, content_type="text/html; charset=utf-8"))
    assert d.conferido
