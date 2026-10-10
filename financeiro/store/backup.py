import sqlite3
from pathlib import Path


def backup(conexao: sqlite3.Connection, destino: Path | str) -> None:
    """Copia o banco com a API de backup do SQLite, consistente com o app escrevendo."""
    copia = sqlite3.connect(destino)
    try:
        conexao.backup(copia)
    finally:
        copia.close()
