"""Acesso ao SQLite. Todo o SQL do app mora aqui (AGENTS.md)."""

from financeiro.store.conexao import abrir
from financeiro.store.migracoes import MigracaoInvalida, migrar

__all__ = ["MigracaoInvalida", "abrir", "migrar"]
