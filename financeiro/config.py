"""Única leitura de variável de ambiente do app (AGENTS.md)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    caminho_bd: Path
    commit: str


def carregar(ambiente: Mapping[str, str] | None = None) -> Config:
    """Lê a configuração do ambiente (ou do mapa passado, nos testes)."""
    ambiente = os.environ if ambiente is None else ambiente
    return Config(
        caminho_bd=Path(ambiente.get("FINANCEIRO_BD", "dados/financeiro.db")),
        commit=ambiente.get("FINANCEIRO_COMMIT", "desconhecido"),
    )
