import os
import threading
import time

import pytest

from base_juridica.arquivos import TravaOcupada, gravar_atomico, trava
from base_juridica.categorias import integrar, ler_categoria

PLANALTO = "https://www.planalto.gov.br/ccivil_03/leis/l8245.htm"


def test_trava_exclui_outra_thread(tmp_cfg):
    ordem = []

    def outra():
        with trava(tmp_cfg.base_dir):
            ordem.append("outra")

    with trava(tmp_cfg.base_dir):
        t = threading.Thread(target=outra)
        t.start()
        time.sleep(0.2)
        ordem.append("primeira")
    t.join()
    assert ordem == ["primeira", "outra"]


def test_trava_reentrante_na_mesma_thread(tmp_cfg):
    with trava(tmp_cfg.base_dir):
        with trava(tmp_cfg.base_dir):
            pass
    assert not (tmp_cfg.base_dir / ".trava").exists()


def test_trava_de_outro_processo_espera_e_desiste(tmp_cfg):
    (tmp_cfg.base_dir / ".trava").write_text("99999")
    with pytest.raises(TravaOcupada):
        with trava(tmp_cfg.base_dir, espera_s=0.3):
            pass


def test_trava_velha_e_removida(tmp_cfg):
    velha = tmp_cfg.base_dir / ".trava"
    velha.write_text("99999")
    antigo = time.time() - 3600
    os.utime(velha, (antigo, antigo))
    with trava(tmp_cfg.base_dir, espera_s=0.3):
        pass


def test_integrar_concorrente_nao_perde_entrada(tmp_cfg):
    integrar(tmp_cfg, "Locação residencial", "guia", "inicial", [PLANALTO])
    threads = [threading.Thread(target=integrar, args=(tmp_cfg, "Locação residencial", "perguntas", f"pergunta {i}", [PLANALTO]))
               for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    perguntas = ler_categoria(tmp_cfg, "locacao-residencial")["perguntas"]
    assert all(f"pergunta {i}" in perguntas for i in range(8))


def test_gravar_atomico_tenta_de_novo_quando_arquivo_ocupado(tmp_path, monkeypatch):
    real = os.replace
    falhas = {"n": 0}

    def replace_ocupado(a, b):
        if falhas["n"] < 2:
            falhas["n"] += 1
            raise PermissionError("arquivo aberto por outro processo")
        return real(a, b)

    monkeypatch.setattr(os, "replace", replace_ocupado)
    destino = gravar_atomico(tmp_path / "x.md", "conteúdo")
    assert destino.read_text(encoding="utf-8") == "conteúdo" and falhas["n"] == 2
