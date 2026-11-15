"""Configuração do servidor: onde fica a pasta de dados do usuário.

A pasta de dados guarda `base/` (leis, precedentes, categorias), `perfil.md`
e `casos/`. Ela vem de DIREITO_LEGAL_DADOS; sem a variável, é
~/direito-legal-dados (criada na primeira vez). BASE_DIR, se definido,
aponta direto para a `base/` (testes e instalações antigas).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

VARIAVEL = "DIREITO_LEGAL_DADOS"


class ConfigError(Exception):
    """Pasta de dados ou BASE_DIR ausente ou inválido."""


@dataclass(frozen=True)
class Config:
    base_dir: Path
    stale_days: int = 30

    @property
    def dados_dir(self) -> Path:
        """A pasta de dados: a que contém `base/`, `perfil.md` e `casos/`."""
        return self.base_dir.parent


def pasta_padrao() -> Path:
    return Path.home() / "direito-legal-dados"


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    if env.get("BASE_DIR"):
        base_dir = Path(env["BASE_DIR"])
        if not base_dir.is_dir():
            raise ConfigError(f"BASE_DIR não é um diretório existente: {base_dir}")
        return Config(base_dir=base_dir)
    if env.get(VARIAVEL):
        dados = Path(env[VARIAVEL]).expanduser()
        if not dados.is_dir():
            # Erro de digitação na variável não pode criar uma base vazia noutro lugar.
            raise ConfigError(f"{VARIAVEL} não é um diretório existente: {dados}")
    else:
        dados = pasta_padrao()
    base_dir = dados / "base"
    base_dir.mkdir(parents=True, exist_ok=True)
    return Config(base_dir=base_dir)
