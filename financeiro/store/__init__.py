"""Acesso ao SQLite. Todo o SQL do app mora aqui (AGENTS.md)."""

from pathlib import Path

from financeiro.store.backup import backup
from financeiro.store.conexao import abrir
from financeiro.store.migracoes import MigracaoInvalida, migrar, versao_atual

PASTA_MIGRACOES = Path(__file__).parent / "migracoes"

__all__ = ["PASTA_MIGRACOES", "MigracaoInvalida", "abrir", "backup", "migrar", "versao_atual"]
