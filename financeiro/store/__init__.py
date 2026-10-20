"""Acesso ao Postgres. Todo o SQL do app mora aqui (AGENTS.md)."""

from pathlib import Path

import psycopg

from financeiro.store.conexao import abrir, criar_pool
from financeiro.store.migracoes import MigracaoInvalida, migrar, versao_atual

# Tipo da conexão, para quem está fora de store/ anotar sem importar o driver.
Conexao = psycopg.Connection
# Violação de restrição do banco (nome repetido, FK, CHECK), para tratar fora de store/.
ErroDeIntegridade = psycopg.errors.IntegrityError

PASTA_MIGRACOES = Path(__file__).parent / "migracoes"

__all__ = [
    "PASTA_MIGRACOES",
    "Conexao",
    "ErroDeIntegridade",
    "MigracaoInvalida",
    "abrir",
    "criar_pool",
    "migrar",
    "versao_atual",
]
