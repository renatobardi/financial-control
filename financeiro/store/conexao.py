import sqlite3
from pathlib import Path


def abrir(caminho: Path | str) -> sqlite3.Connection:
    """Abre o banco em WAL, com chaves estrangeiras ligadas.

    Uma conexão por requisição, usada em sequência: o FastAPI pode abri-la numa thread e usá-la
    noutra, então a checagem de thread do sqlite3 fica desligada.
    """
    conexao = sqlite3.connect(caminho, check_same_thread=False)
    conexao.execute("PRAGMA journal_mode = WAL")
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao
