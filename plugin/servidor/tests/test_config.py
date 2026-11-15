import pytest

from base_juridica import config
from base_juridica.config import ConfigError, load_config


def test_load_config_le_base_dir(tmp_path):
    cfg = load_config({"BASE_DIR": str(tmp_path)})
    assert cfg.base_dir == tmp_path and cfg.stale_days == 30


def test_load_config_base_dir_inexistente(tmp_path):
    with pytest.raises(ConfigError):
        load_config({"BASE_DIR": str(tmp_path / "nao-existe")})


def test_pasta_de_dados_pela_variavel(tmp_path):
    cfg = load_config({"DIREITO_LEGAL_DADOS": str(tmp_path)})
    assert cfg.base_dir == tmp_path / "base" and cfg.base_dir.is_dir()
    assert cfg.dados_dir == tmp_path


def test_pasta_de_dados_inexistente_e_erro(tmp_path):
    # Erro de digitação na variável não pode criar uma base vazia em outro lugar.
    with pytest.raises(ConfigError, match="DIREITO_LEGAL_DADOS"):
        load_config({"DIREITO_LEGAL_DADOS": str(tmp_path / "nao-existe")})


def test_sem_variavel_usa_pasta_padrao_e_cria(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "pasta_padrao", lambda: tmp_path / "direito-legal-dados")
    cfg = load_config({})
    assert cfg.dados_dir == tmp_path / "direito-legal-dados" and cfg.base_dir.is_dir()
