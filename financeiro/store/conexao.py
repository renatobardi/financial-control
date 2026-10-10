import sqlite3
from pathlib import Path


def abrir(caminho: Path | str) -> sqlite3.Connection:
    """Abre o banco em WAL, com chaves estrangeiras ligadas."""
    conexao = sqlite3.connect(caminho)
    conexao.execute("PRAGMA journal_mode = WAL")
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao
