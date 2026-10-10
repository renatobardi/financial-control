import re
import sqlite3
from pathlib import Path

_NOME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class MigracaoInvalida(Exception):
    """A pasta de migrações não segue a numeração 0001, 0002, ... sem buracos."""


def _listar(pasta: Path) -> list[tuple[int, Path]]:
    migracoes = []
    for arquivo in sorted(pasta.glob("*.sql")):
        achado = _NOME.match(arquivo.name)
        if achado is None:
            raise MigracaoInvalida(f"nome fora do padrão NNNN_nome.sql: {arquivo.name}")
        migracoes.append((int(achado.group(1)), arquivo))
    for esperado, (versao, arquivo) in enumerate(migracoes, start=1):
        if versao != esperado:
            raise MigracaoInvalida(f"esperava a migração {esperado:04d}, achou {arquivo.name}")
    return migracoes


def migrar(conexao: sqlite3.Connection, pasta: Path) -> int:
    """Aplica as migrações `NNNN_nome.sql` pendentes e devolve a versão do esquema."""
    migracoes = _listar(pasta)
    conexao.execute("CREATE TABLE IF NOT EXISTS versao_esquema (versao INTEGER PRIMARY KEY)")
    atual = conexao.execute("SELECT COALESCE(MAX(versao), 0) FROM versao_esquema").fetchone()[0]
    for versao, arquivo in migracoes:
        if versao <= atual:
            continue
        conexao.executescript(arquivo.read_text())
        conexao.execute("INSERT INTO versao_esquema (versao) VALUES (?)", (versao,))
        conexao.commit()
        atual = versao
    return atual
