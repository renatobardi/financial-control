import re
import sqlite3
from pathlib import Path

from financeiro.store.backup import backup

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


def _copiar_antes(conexao: sqlite3.Connection, primeira: int) -> None:
    """Guarda `<banco>.antes-da-NNNN`. Banco em memória não tem arquivo para copiar."""
    arquivo = conexao.execute("PRAGMA database_list").fetchone()[2]
    if arquivo:
        backup(conexao, f"{arquivo}.antes-da-{primeira:04d}")


def versao_atual(conexao: sqlite3.Connection) -> int:
    """Versão do esquema aplicada no banco; 0 se nenhuma migração rodou."""
    existe = conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'versao_esquema'"
    ).fetchone()
    if existe is None:
        return 0
    return conexao.execute("SELECT COALESCE(MAX(versao), 0) FROM versao_esquema").fetchone()[0]


def migrar(conexao: sqlite3.Connection, pasta: Path) -> int:
    """Aplica as migrações `NNNN_nome.sql` pendentes e devolve a versão do esquema."""
    migracoes = _listar(pasta)
    conexao.execute("CREATE TABLE IF NOT EXISTS versao_esquema (versao INTEGER PRIMARY KEY)")
    atual = versao_atual(conexao)
    pendentes = [(versao, arquivo) for versao, arquivo in migracoes if versao > atual]
    if pendentes and atual > 0:
        _copiar_antes(conexao, pendentes[0][0])
    for versao, arquivo in pendentes:
        try:
            conexao.executescript("BEGIN;\n" + arquivo.read_text())
            conexao.execute("INSERT INTO versao_esquema (versao) VALUES (?)", (versao,))
            conexao.commit()
        except Exception:
            conexao.rollback()
            raise
        atual = versao
    return atual
