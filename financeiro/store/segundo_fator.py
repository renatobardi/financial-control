import sqlite3
from typing import NamedTuple


class SegundoFator(NamedTuple):
    segredo: str
    ativo: bool
    ultimo_passo: int


def obter(conexao: sqlite3.Connection, usuario_id: int) -> SegundoFator | None:
    linha = conexao.execute(
        "SELECT segredo, ativo, ultimo_passo FROM segundo_fator WHERE usuario_id = ?",
        (usuario_id,),
    ).fetchone()
    return SegundoFator(linha[0], bool(linha[1]), linha[2]) if linha else None


def iniciar(conexao: sqlite3.Connection, usuario_id: int, segredo: str) -> None:
    """Guarda um segredo ainda não confirmado (ativo = 0), trocando o que houver."""
    conexao.execute(
        "INSERT INTO segundo_fator (usuario_id, segredo, ativo, ultimo_passo) VALUES (?, ?, 0, 0)"
        " ON CONFLICT (usuario_id) DO UPDATE SET segredo = excluded.segredo, ativo = 0,"
        " ultimo_passo = 0",
        (usuario_id, segredo),
    )
    conexao.commit()


def ativar(
    conexao: sqlite3.Connection, usuario_id: int, passo: int, hashes_dos_codigos: list[str]
) -> None:
    conexao.execute(
        "UPDATE segundo_fator SET ativo = 1, ultimo_passo = ? WHERE usuario_id = ?",
        (passo, usuario_id),
    )
    conexao.execute("DELETE FROM codigo_recuperacao WHERE usuario_id = ?", (usuario_id,))
    conexao.executemany(
        "INSERT INTO codigo_recuperacao (usuario_id, codigo_hash) VALUES (?, ?)",
        [(usuario_id, h) for h in hashes_dos_codigos],
    )
    conexao.commit()


def registrar_passo(conexao: sqlite3.Connection, usuario_id: int, passo: int) -> None:
    conexao.execute(
        "UPDATE segundo_fator SET ultimo_passo = ? WHERE usuario_id = ?", (passo, usuario_id)
    )
    conexao.commit()


def consumir_codigo(conexao: sqlite3.Connection, usuario_id: int, codigo_hash: str) -> bool:
    cursor = conexao.execute(
        "DELETE FROM codigo_recuperacao WHERE usuario_id = ? AND codigo_hash = ?",
        (usuario_id, codigo_hash),
    )
    conexao.commit()
    return cursor.rowcount > 0


def codigos_restantes(conexao: sqlite3.Connection, usuario_id: int) -> int:
    return conexao.execute(
        "SELECT COUNT(*) FROM codigo_recuperacao WHERE usuario_id = ?", (usuario_id,)
    ).fetchone()[0]


def desativar(conexao: sqlite3.Connection, usuario_id: int) -> None:
    conexao.execute("DELETE FROM codigo_recuperacao WHERE usuario_id = ?", (usuario_id,))
    conexao.execute("DELETE FROM segundo_fator WHERE usuario_id = ?", (usuario_id,))
    conexao.commit()
