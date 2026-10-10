"""Acesso ao SQLite. Todo o SQL do app mora aqui (AGENTS.md)."""

import sqlite3
from pathlib import Path

from financeiro.store.backup import backup
from financeiro.store.conexao import abrir
from financeiro.store.migracoes import MigracaoInvalida, migrar, versao_atual

# Tipo da conexão, para quem está fora de store/ anotar sem importar sqlite3.
Conexao = sqlite3.Connection
# Violação de restrição do banco (nome repetido, FK, CHECK), para tratar fora de store/.
ErroDeIntegridade = sqlite3.IntegrityError

PASTA_MIGRACOES = Path(__file__).parent / "migracoes"

__all__ = [
    "PASTA_MIGRACOES",
    "Conexao",
    "ErroDeIntegridade",
    "MigracaoInvalida",
    "abrir",
    "backup",
    "migrar",
    "versao_atual",
]
