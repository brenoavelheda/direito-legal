from datetime import datetime, timezone

import pytest

from base_juridica.citacoes import extrair_citacoes, verificar_citacoes
from base_juridica.leis import salvar_lei
from base_juridica.modelos import Artigo, LeiDoc
from base_juridica.precedentes import registrar_precedente


@pytest.fixture
def cfg_com_artigo_revogado(tmp_cfg):
    salvar_lei(tmp_cfg, LeiDoc(
        id="lei-1234-2000", apelidos=[], titulo="Lei nº 1.234, de 2000", url="https://www.planalto.gov.br/x",
        capturado_em=datetime(2026, 11, 15, tzinfo=timezone.utc), sha256="0" * 64,
        artigos=[Artigo("4", "Vigente."), Artigo("5", "", revogado=True, notas=["(Revogado pela Lei nº 2, de 2001)"])],
    ))
    return tmp_cfg


@pytest.fixture
def cfg_com_sumula_cancelada(tmp_cfg, fake_abrir_403):
    registrar_precedente(tmp_cfg, "STJ", "súmula", "1", "x", "https://scon.stj.jus.br/x", estado="cancelada",
                         abrir=fake_abrir_403)
    return tmp_cfg


@pytest.fixture
def cfg_com_cf(tmp_cfg):
    salvar_lei(tmp_cfg, LeiDoc(
        id="cf-1988", apelidos=["CF"], titulo="Constituição", url="https://www.planalto.gov.br/c",
        capturado_em=datetime(2026, 11, 15, tzinfo=timezone.utc), sha256="0" * 64,
        artigos=[Artigo("5", "Todos são iguais..."), Artigo("ADCT-10", "Até que seja promulgada...")],
    ))
    return tmp_cfg


@pytest.mark.parametrize("texto,lei,art", [
    ("art. 833, X, do CPC", "lei-13105-2015", "833"),
    ("art. 833, inciso X, do CPC/2015", "lei-13105-2015", "833"),
    ("artigo 28 da Lei 8.245/91", "lei-8245-1991", "28"),
    ("art. 28 da Lei nº 8.245, de 18 de outubro de 1991", "lei-8245-1991", "28"),
    ("art. 1.015 do CPC", "lei-13105-2015", "1015"),
    ("art. 54-A da Lei do Inquilinato", "lei-8245-1991", "54-A"),
    ("art. 5º, LXVII, da CF", "cf-1988", "5"),
    ("art. 833, § 2º, do CPC", "lei-13105-2015", "833"),
    ("art. 1º da Lei 8.009/90", "lei-8009-1990", "1"),
    ("art. 3º do Decreto-Lei 911/69", "dl-911-1969", "3"),
    ("art. 10 do ADCT", "cf-1988", "ADCT-10"),
    ("Art. 406 do Código Civil", "lei-10406-2002", "406"),
])
def test_extrai_artigo(texto, lei, art):
    c = extrair_citacoes(texto)[0]
    assert (c.tipo, c.lei_id, c.artigo) == ("artigo", lei, art)


def test_intervalo_vira_varias():
    assert [c.artigo for c in extrair_citacoes("arts. 833 a 836 do CPC")] == ["833","834","835","836"]


def test_lista_vira_varias():
    assert [(c.artigo, c.lei_id) for c in extrair_citacoes("arts. 27, 28 e 33 da Lei 8.245/91")] == [
        ("27", "lei-8245-1991"), ("28", "lei-8245-1991"), ("33", "lei-8245-1991")]


@pytest.mark.parametrize("texto,pid", [
    ("Súmula 7/STJ", "stj-sumula-7"), ("Súmula nº 7 do STJ", "stj-sumula-7"),
    ("SV 25", "stf-sv-25"), ("Súmula Vinculante 25", "stf-sv-25"),
    ("Tema 1235/STJ", "stj-tema-1235"), ("Tema Repetitivo 1.235 do STJ", "stj-tema-1235"),
    ("Súmula 381 do Superior Tribunal de Justiça", "stj-sumula-381"),
])
def test_extrai_precedente(texto, pid):
    assert extrair_citacoes(texto)[0].precedente_id == pid


def test_cada_artigo_fica_com_a_sua_lei():
    cs = extrair_citacoes("O art. 833 do CPC e o art. 28 da Lei 8.245/91 tratam de coisas diferentes.")
    assert [(c.artigo, c.lei_id) for c in cs] == [("833", "lei-13105-2015"), ("28", "lei-8245-1991")]


def test_lei_antes_do_artigo_na_mesma_frase():
    c = extrair_citacoes("A Lei 8.009/90, em seu art. 1º, protege o imóvel.")[0]
    assert (c.artigo, c.lei_id) == ("1", "lei-8009-1990")


def test_lei_de_outra_frase_nao_e_herdada():
    cs = extrair_citacoes("Veja o CPC. O art. 28 trata disso.")
    assert [(c.artigo, c.lei_id) for c in cs] == [("28", None)]


def test_abreviacao_inc_nao_quebra_a_frase():
    c = extrair_citacoes("art. 833, inc. X, do CPC")[0]
    assert c.lei_id == "lei-13105-2015"


def test_cf_minusculo_de_confira_nao_e_constituicao():
    assert all(c.lei_id != "cf-1988" for c in extrair_citacoes("Cf. art. 28 da Lei 8.245/91."))


def test_ordem_do_texto():
    cs = extrair_citacoes("Súmula 7/STJ; art. 833 do CPC; Tema 1235/STJ.")
    assert [c.tipo for c in cs] == ["precedente", "artigo", "precedente"]


def test_verifica_ok_e_inexistente(cfg_com_l8245):
    v = verificar_citacoes(cfg_com_l8245, "Ver art. 28 e art. 999 da Lei 8.245/91.")
    assert [x.status for x in v] == ["ok", "nao_encontrada"]


def test_fonte_ausente_sugere_baixar(tmp_cfg):
    v = verificar_citacoes(tmp_cfg, "art. 833 do CPC")[0]
    assert v.status == "fonte_ausente" and "baixar_lei" in v.sugestao


def test_precedente_ausente_sugere_baixar_precedente(tmp_cfg):
    v = verificar_citacoes(tmp_cfg, "Súmula 7/STJ")[0]
    assert v.status == "fonte_ausente" and "baixar_precedente" in v.sugestao


def test_revogado(cfg_com_artigo_revogado):
    assert verificar_citacoes(cfg_com_artigo_revogado, "art. 5 da Lei 1.234/2000")[0].status == "revogada"


def test_precedente_cancelado(cfg_com_sumula_cancelada):
    assert verificar_citacoes(cfg_com_sumula_cancelada, "Súmula 1/STJ")[0].status == "cancelada"


def test_precedente_nao_conferido_sai_com_verificar(tmp_cfg, fake_abrir_403):
    registrar_precedente(tmp_cfg, "STJ", "súmula", "7", "A pretensão de simples reexame de prova não enseja recurso especial.",
                         "https://scon.stj.jus.br/x", abrir=fake_abrir_403)
    v = verificar_citacoes(tmp_cfg, "Súmula 7/STJ")[0]
    assert v.status == "ok" and "[verificar]" in v.detalhe


def test_artigo_sem_lei_nao_passa(tmp_cfg):
    v = verificar_citacoes(tmp_cfg, "O art. 28 trata disso.")[0]
    assert v.status == "nao_encontrada" and "lei" in v.detalhe


def test_adct_e_cf(cfg_com_cf):
    assert [v.status for v in verificar_citacoes(cfg_com_cf, "art. 5º da CF e art. 10 do ADCT")] == ["ok", "ok"]


def test_texto_sem_citacao():
    assert extrair_citacoes("O locador quer vender o apartamento.") == []


def test_ponto_e_virgula_nao_separa_frase():
    cs = extrair_citacoes("Nos arts. 27 a 34 da Lei do Inquilinato está a preferência; o prazo é de 30 dias (art. 28).")
    assert (cs[-1].artigo, cs[-1].lei_id) == ("28", "lei-8245-1991")


def test_tema_sem_tribunal_herda_citacao_completa_do_texto():
    cs = extrair_citacoes("A poupança é protegida (Tema 1285/STJ). O acórdão do Tema 1285 foi publicado em novembro.")
    assert [c.precedente_id for c in cs] == ["stj-tema-1285", "stj-tema-1285"]


def test_artigo_sem_lei_herda_mesmo_artigo_citado_no_texto():
    cs = extrair_citacoes("O bloqueio segue o art. 854 do CPC. Houve manifestação no prazo do art. 854, § 3º?")
    assert [(c.artigo, c.lei_id) for c in cs] == [("854", "lei-13105-2015"), ("854", "lei-13105-2015")]


def test_artigo_ambiguo_no_texto_nao_herda():
    cs = extrair_citacoes("Ver o art. 5º da CF e o art. 5º do CDC. Depois, leia o art. 5º.")
    assert cs[-1].lei_id is None


@pytest.mark.parametrize("texto,ids", [
    ("dois repetitivos (Temas 1235 e 1285/STJ)", ["stj-tema-1235", "stj-tema-1285"]),
    ("Súmulas 7 e 83 do STJ", ["stj-sumula-7", "stj-sumula-83"]),
])
def test_lista_de_precedentes(texto, ids):
    assert [c.precedente_id for c in extrair_citacoes(texto)] == ids


def test_artigo_de_decreto():
    c = extrair_citacoes("art. 1º do Decreto 12.797/2025")[0]
    assert (c.lei_id, c.artigo) == ("dec-12797-2025", "1")


@pytest.mark.parametrize("texto,lei,art", [
    ("art. 1015 do CPC", "lei-13105-2015", "1015"),
    ("artigo 1228 do Código Civil", "lei-10406-2002", "1228"),
    ("art. 1.228 do Código Civil", "lei-10406-2002", "1228"),
])
def test_numero_de_quatro_digitos_sem_ponto(texto, lei, art):
    c = extrair_citacoes(texto)[0]
    assert (c.lei_id, c.artigo) == (lei, art)


@pytest.fixture
def cfg_com_8009(tmp_cfg):
    from base_juridica.modelos import Redacao

    salvar_lei(tmp_cfg, LeiDoc(
        id="lei-8009-1990", apelidos=[], titulo="Lei nº 8.009, de 1990", url="https://www.planalto.gov.br/l8009",
        capturado_em=datetime(2026, 11, 15, tzinfo=timezone.utc), sha256="0" * 64,
        artigos=[Artigo("3", "A impenhorabilidade é oponível, salvo se movido:\nII - pelo titular do crédito;\n"
                             "III – pelo credor da pensão alimentícia;\nParágrafo único. Texto.",
                        redacoes_anteriores=[Redacao("I - em razão dos créditos de trabalhadores;",
                                                     "Lei Complementar nº 150, de 2015", None)])],
    ))
    return tmp_cfg


@pytest.mark.parametrize("texto,status", [
    ("art. 3º, I, da Lei 8.009/90", "revogada"),
    ("art. 3º, inciso II, da Lei 8.009/90", "ok"),
    ("art. 3º, III, da Lei 8.009/90", "ok"),
    ("art. 3º, XV, da Lei 8.009/90", "nao_encontrada"),
    ("art. 3º, § 9º, da Lei 8.009/90", "nao_encontrada"),
    ("art. 3º, parágrafo único, da Lei 8.009/90", "ok"),
    ("art. 3º da Lei 8.009/90", "ok"),
])
def test_verifica_inciso_e_paragrafo(cfg_com_8009, texto, status):
    assert verificar_citacoes(cfg_com_8009, texto)[0].status == status


def test_inciso_do_cpc_real(cfg_com_cpc):
    assert [v.status for v in verificar_citacoes(cfg_com_cpc, "art. 833, X, do CPC e art. 833, § 2º, do CPC")] == ["ok", "ok"]


@pytest.mark.parametrize("texto,lei,art", [
    ("Conforme o CC, o art. 3º da Lei 14.905 alterou os juros.", None, "3"),
    ("art. 8º-A do DL 911/69", "dl-911-1969", "8-A"),
    ("art. 46 da LC 150/2015", "lc-150-2015", "46"),
    ("art. 1º da Lei Federal 8.245/91", "lei-8245-1991", "1"),
    ("art. 2º da Lei Estadual 1.234/2000", None, "2"),
])
def test_lei_nao_resolvida_e_fronteira(texto, lei, art):
    c = extrair_citacoes(texto)[0]
    assert (c.lei_id, c.artigo) == (lei, art)


def test_lei_nao_resolvida_nao_herda_de_outra_citacao():
    cs = extrair_citacoes("O art. 3º do CC trata disso. Já o art. 3º da Lei 14.905 alterou os juros.")
    assert [c.lei_id for c in cs] == ["lei-10406-2002", None]


@pytest.mark.parametrize("texto,status", [
    ("- A tese foi fixada no REsp 1.660.168/RS [STJ]", "fonte_ausente"),
    ("- A tese foi fixada no [REsp 1.660.168](https://processo.stj.jus.br/x) [STJ]", "ok"),
    ("- A tese foi fixada no REsp nº 1.660.168 [conhecimento do modelo — verificar]", "ok"),
    ("- O STF decidiu na ADI 7.600 [STF]", "fonte_ausente"),
])
def test_acordao_so_passa_com_url_oficial_ou_marcado(tmp_cfg, texto, status):
    v = [x for x in verificar_citacoes(tmp_cfg, texto) if x.citacao.tipo == "acordao"]
    assert len(v) == 1 and v[0].status == status


def test_paragrafo_sem_texto_e_revogado(tmp_cfg):
    salvar_lei(tmp_cfg, LeiDoc(
        id="lei-1234-2000", apelidos=[], titulo="Lei 1.234", url="https://www.planalto.gov.br/x",
        capturado_em=datetime(2026, 11, 15, tzinfo=timezone.utc), sha256="0" * 64,
        artigos=[Artigo("3", "Caput.\n§ 1º Vale.\n§ 3º", notas=["(Revogado pela Lei nº 2, de 2001)"])],
    ))
    assert [v.status for v in verificar_citacoes(tmp_cfg, "art. 3º, § 3º, da Lei 1.234/2000 e art. 3º, § 1º, da Lei 1.234/2000")] == ["revogada", "ok"]


def test_remencao_de_acordao_herda_url_de_outra_linha(tmp_cfg):
    texto = ("- Débito do mínimo é válido — REsp 1.626.997/RJ ([Informativo](https://processo.stj.jus.br/x)) [STJ]\n\n"
             "## Certeza: alta — o REsp 1.626.997/RJ condiciona o débito a cláusula expressa.\n"
             "- Outro julgado, o REsp 1.000.000/SP, diz o contrário.")
    v = [(x.citacao.trecho, x.status) for x in verificar_citacoes(tmp_cfg, texto) if x.citacao.tipo == "acordao"]
    assert v == [("REsp 1.626.997/RJ", "ok"), ("REsp 1.626.997/RJ", "ok"), ("REsp 1.000.000/SP", "fonte_ausente")]


def test_inciso_digitado_com_l_minusculo(tmp_cfg):
    # Planalto, Lei 7.347/85 art. 1º: "l - ao meio-ambiente;" e "ll - ao consumidor;"
    salvar_lei(tmp_cfg, LeiDoc(
        id="lei-7347-1985", apelidos=[], titulo="Lei 7.347", url="https://www.planalto.gov.br/x",
        capturado_em=datetime(2026, 11, 15, tzinfo=timezone.utc), sha256="0" * 64,
        artigos=[Artigo("1", "Regem-se:\nl - ao meio-ambiente;\nll - ao consumidor;\nIII – a bens;")],
    ))
    vs = verificar_citacoes(tmp_cfg, "art. 1º, I, da Lei 7.347/85; art. 1º, II, da Lei 7.347/85; art. 1º, IV, da Lei 7.347/85")
    assert [v.status for v in vs] == ["ok", "ok", "nao_encontrada"]
