import sqlite3
from typing import NamedTuple


class Sessao(NamedTuple):
    usuario_id: int
    bd_id: int | None
    csrf: str


def criar(
    conexao: sqlite3.Connection,
    token_hash: str,
    usuario_id: int,
    csrf: str,
    criada_em: str,
    expira_em: str,
) -> None:
    conexao.execute(
        "INSERT INTO sessao (token_hash, usuario_id, csrf, criada_em, expira_em)"
        " VALUES (?, ?, ?, ?, ?)",
        (token_hash, usuario_id, csrf, criada_em, expira_em),
    )
    conexao.commit()


def achar(conexao: sqlite3.Connection, token_hash: str, agora: str) -> Sessao | None:
    linha = conexao.execute(
        "SELECT usuario_id, bd_id, csrf FROM sessao WHERE token_hash = ? AND expira_em > ?",
        (token_hash, agora),
    ).fetchone()
    return Sessao(*linha) if linha else None


def definir_bd(conexao: sqlite3.Connection, token_hash: str, bd_id: int | None) -> None:
    conexao.execute("UPDATE sessao SET bd_id = ? WHERE token_hash = ?", (bd_id, token_hash))
    conexao.commit()


def apagar(conexao: sqlite3.Connection, token_hash: str) -> None:
    conexao.execute("DELETE FROM sessao WHERE token_hash = ?", (token_hash,))
    conexao.commit()


def registrar_tentativa(conexao: sqlite3.Connection, email: str, em: str) -> None:
    conexao.execute("INSERT INTO tentativa_login (email, em) VALUES (?, ?)", (email, em))
    conexao.commit()


def contar_tentativas(conexao: sqlite3.Connection, email: str, desde: str) -> int:
    return conexao.execute(
        "SELECT COUNT(*) FROM tentativa_login WHERE email = ? AND em >= ?", (email, desde)
    ).fetchone()[0]


def limpar_tentativas(conexao: sqlite3.Connection, email: str) -> None:
    conexao.execute("DELETE FROM tentativa_login WHERE email = ?", (email,))
    conexao.commit()
