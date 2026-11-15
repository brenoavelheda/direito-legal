from pathlib import Path

import pytest

from base_juridica.planalto import ParseVazio, normalizar_numero, parse_lei

FIX = Path(__file__).parent / "fixtures"


def _ler(nome: str) -> str:
    return (FIX / nome).read_bytes().decode("cp1252")


@pytest.fixture(scope="module")
def l8245():
    return _ler("planalto-l8245.htm")


@pytest.fixture(scope="module")
def l13105():
    return _ler("planalto-l13105.htm")


@pytest.fixture(scope="module")
def sintetico():
    return (FIX / "sintetico-redacoes.htm").read_text(encoding="utf-8")


def artigo(lista, numero):
    return next(a for a in lista if a.numero == numero)


def test_l8245_art28_texto_vigente(l8245):
    art = artigo(parse_lei(l8245), "28")
    assert art.texto.startswith("O direito de preferência do locatário caducará se não manifestada")
    assert "no prazo de trinta dias" in art.texto and not art.revogado


def test_l8245_art4_tres_redacoes(l8245):
    art = artigo(parse_lei(l8245), "4")
    assert "54-A" in art.texto
    assert len(art.redacoes_anteriores) == 2
    assert any("art. 924 do Código Civil" in r.texto for r in art.redacoes_anteriores)
    assert any(r.alterado_por == "Lei nº 12.112, de 2009" for r in art.redacoes_anteriores)


def test_l8245_art54A_numeracao(l8245):
    assert artigo(parse_lei(l8245), "54-A").texto.startswith("Na locação não residencial")


def test_cpc_833_inciso_x(l13105):
    art = artigo(parse_lei(l13105), "833")
    assert "X - a quantia depositada em caderneta de poupança, até o limite de 40 (quarenta) salários-mínimos;" in art.texto


def test_cpc_1015_numeracao(l13105):
    assert artigo(parse_lei(l13105), "1015").texto.startswith("Cabe agravo de instrumento")


def test_cpc_contagem_artigos(l13105):
    assert len({a.numero for a in parse_lei(l13105)}) >= 1072


def test_notas_preservadas(l8245):
    assert any("Redação dada pela Lei nº 12.744, de 2012" in n for n in artigo(parse_lei(l8245), "4").notas)


@pytest.mark.parametrize("bruto,esperado", [("4º", "4"), ("1o", "1"), ("1°", "1"), ("1.015", "1015"), ("8º-A", "8-A"), ("54-A", "54-A")])
def test_normalizar_numero(bruto, esperado):
    assert normalizar_numero(bruto) == esperado


def test_sintetico_line_through_vira_redacao_anterior(sintetico):
    art = artigo(parse_lei(sintetico), "8-A")
    assert art.redacoes_anteriores and "texto antigo" in art.redacoes_anteriores[0].texto
    assert art.texto.startswith("Texto novo do oito-A")


def test_sintetico_ordinais(sintetico):
    nums = [a.numero for a in parse_lei(sintetico)]
    assert nums[:4] == ["1", "2", "3", "4"]


def test_sintetico_revogado_e_assinatura_ignorada(sintetico):
    arts = parse_lei(sintetico)
    nove = artigo(arts, "9")
    assert nove.revogado and nove.texto == ""
    assert all("Brasília" not in a.texto and "FULANO" not in a.texto for a in arts)


def test_titulos_centralizados_nao_entram_no_texto(l8245):
    assert "Do direito de preferência" not in artigo(parse_lei(l8245), "26").texto


def test_parse_vazio():
    with pytest.raises(ParseVazio):
        parse_lei("<html><body><p>sem artigos</p></body></html>")


def test_adct_numeracao_separada():
    html = (
        "<p>Art. 10. Texto do corpo da Constituição.</p>"
        "<p align=\"center\">ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS</p>"
        "<p>Art. 10. Texto transitório.</p>"
    )
    arts = parse_lei(html)
    assert artigo(arts, "10").texto == "Texto do corpo da Constituição."
    assert artigo(arts, "ADCT-10").texto == "Texto transitório."


def test_aviso_dou_no_meio_nao_interrompe():
    html = (
        "<p>Art. 1º Corpo.</p>"
        "<p>Este texto não substitui o publicado no D.O.U. de 5.10.1988.</p>"
        "<p align=\"center\">ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS</p>"
        "<p>Art. 1º Transitório.</p>"
    )
    arts = parse_lei(html)
    assert artigo(arts, "1").texto == "Corpo."
    assert artigo(arts, "ADCT-1").texto == "Transitório."


def test_texto_fora_de_p_e_art_sem_ponto():
    html = (
        "<html><body>"
        "<p>Art. 81. Primeiro.</p>"
        "<font><strike>Art\r\n82. Texto antigo do oitenta e dois.</strike></font><br>"
        "<font>Art. 82. Texto novo do oitenta e dois: <a>(Redação dada pela Lei nº 9.008, de 21.3.1995)</a></font><br>"
        "<font>I - o Ministério Público;</font>"
        "<p>Art. 83. Terceiro.</p>"
        "</body></html>"
    )
    arts = parse_lei(html)
    a82 = artigo(arts, "82")
    assert a82.texto.startswith("Texto novo do oitenta e dois:")
    assert "I - o Ministério Público;" in a82.texto
    assert a82.redacoes_anteriores[0].texto.startswith("Texto antigo")
    assert a82.redacoes_anteriores[0].alterado_por == "Lei nº 9.008, de 21.3.1995"
    assert [a.numero for a in arts] == ["81", "82", "83"]


def test_dois_artigos_na_mesma_linha_sao_separados():
    arts = parse_lei("<body><font>Art. 1º Um. Art. 2º Dois; e “Art. 3º citado” não.</font></body>")
    assert [a.numero for a in arts] == ["1", "2"]


def test_caput_so_com_nota_de_revogacao():
    arts = parse_lei("<p>Art. 1º Vale.</p><p>Art. 2º (Revogado pela Lei nº 9.999, de 2010)</p>")
    assert artigo(arts, "2").revogado and not artigo(arts, "1").revogado


def test_titulo_da_pagina():
    from base_juridica.planalto import titulo_da_pagina

    html = _ler("planalto-l8245.htm")
    assert titulo_da_pagina(html).upper().startswith("LEI Nº 8.245, DE 18 DE OUTUBRO DE 1991")
    assert titulo_da_pagina("<p>nada aqui</p>") is None


def test_hifen_separador_nao_vira_letra_do_artigo():
    # CLT e leis antigas: "Art. 839 - A reclamação..." (o "A" é artigo definido, não 839-A).
    html = (
        "<html><body>"
        "<p>Art. 839 - A reclamação poderá ser apresentada:</p>"
        "<p>Art. 830 - O documento em cópia oferecido para prova poderá ser declarado autêntico.</p>"
        "<p>Art. 611-A. A convenção coletiva tem prevalência sobre a lei.</p>"
        "<p>Art. 5º-A A lei disporá sobre isso.</p>"
        "<p>Art. 6º -A Texto com hífen colado na letra.</p>"
        "</body></html>"
    )
    arts = parse_lei(html)
    assert [a.numero for a in arts] == ["839", "830", "611-A", "5-A", "6-A"]
    assert artigo(arts, "839").texto.startswith("A reclamação poderá")
    assert artigo(arts, "830").texto.startswith("O documento em cópia")
    assert artigo(arts, "611-A").texto.startswith("A convenção coletiva")


def test_link_vigencia_encerrada_nao_vaza_texto_riscado():
    html = ("<html><body><p>Art. 1.225. São direitos reais:</p>"
            "<p><strike>XII - a concessão de direito real de uso; e (Redação dada pela Medida Provisória nº 700, de 2015)"
            "</strike> <a href='#'>Vigência encerrada</a></p>"
            "<p>XII - a concessão de direito real de uso; (Redação dada pela Lei nº 14.620, de 2023)</p>"
            "</body></html>")
    art = artigo(parse_lei(html), "1225")
    assert art.texto.count("XII -") == 1 and "Vigência" not in art.texto
    assert len(art.redacoes_anteriores) == 1 and art.redacoes_anteriores[0].alterado_por == "Lei nº 14.620, de 2023"


def test_link_marcador_sai_do_texto_mas_link_de_lei_fica():
    html = ("<html><body><p>Art. 2º Aplica-se a <a href='#'>Lei nº 9.999, de 2010</a>. <a href='#'>Vigência</a></p>"
            "</body></html>")
    art = artigo(parse_lei(html), "2")
    assert art.texto == "Aplica-se a Lei nº 9.999, de 2010." and "(Vigência)" in art.notas


def test_nota_de_revogacao_do_bloco_riscado_vira_alterado_por():
    html = ("<html><body><p>Art. 3º A impenhorabilidade é oponível, salvo se movido:</p>"
            "<p><strike>I - em razão dos créditos de trabalhadores;</strike> (Revogado pela Lei Complementar nº 150, de 2015)</p>"
            "<p>II - pelo titular do crédito;</p></body></html>")
    art = artigo(parse_lei(html), "3")
    r = art.redacoes_anteriores[0]
    assert (r.alterado_por, r.data.year) == ("Lei Complementar nº 150, de 2015", 2015)
    assert "(Revogado pela Lei Complementar nº 150, de 2015)" in art.notas


def test_inciso_com_travessao():
    html = ("<html><body><p>Art. 3º Caput:</p><p><strike>III – pelo credor de pensão;</strike></p>"
            "<p>III – pelo credor de pensão alimentícia; (Redação dada pela Lei nº 13.144, de 2015)</p></body></html>")
    r = artigo(parse_lei(html), "3").redacoes_anteriores[0]
    assert r.alterado_por == "Lei nº 13.144, de 2015"


def test_nota_em_link_colada_ao_link_vigencia_encerrada():
    # HTML real do CC art. 1.225: a nota "(Redação dada…)" também é link, e só
    # espaço a separa do link "Vigência encerrada" fora do <strike>.
    html = ("<html><body><p>Art. 1.225. São direitos reais:</p>"
            "<p><span><strike>XII - a concessão de direito real de uso; e\r\n "
            "<a href='mpv700.htm'>(Redação dada pela Medida Provisória nº 700, de 2015)</a></strike></span>\r\n "
            "<a href='adc-023.htm'>Vigência encerrada</a></p>"
            "<p>XII - a concessão de direito real de uso; <a href='l14620.htm'>(Redação dada pela Lei nº 14.620, de 2023)</a></p>"
            "</body></html>")
    art = artigo(parse_lei(html), "1225")
    assert art.texto.count("XII -") == 1 and "Vigência" not in art.texto
    assert [r.alterado_por for r in art.redacoes_anteriores] == ["Lei nº 14.620, de 2023"]


@pytest.mark.parametrize("linha,esperado", [
    ("l - ao meio-ambiente;", "i-"), ("ll - ao consumidor;", "ii-"), ("lV - a qualquer", "iv-"),
    ("L - às presidiárias", "l-"), ("XL - a lei penal", "xl-"), ("l) alínea ele", "l)"),
])
def test_rotulo_de_inciso_com_l_minusculo_no_lugar_de_i(linha, esperado):
    from base_juridica.planalto import rotulo
    assert rotulo(linha) == esperado
