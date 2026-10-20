from typing import NamedTuple

import psycopg


class Sessao(NamedTuple):
    usuario_id: int
    bd_id: int | None
    csrf: str


class Aberta(NamedTuple):
    id: int
    criada_em: str
    agente: str | None
    ip: str | None
    token_hash: str


def criar(
    conexao: psycopg.Connection,
    token_hash: str,
    usuario_id: int,
    csrf: str,
    criada_em: str,
    expira_em: str,
    agente: str | None = None,
    ip: str | None = None,
) -> None:
    conexao.execute(
        "INSERT INTO sessao (token_hash, usuario_id, csrf, criada_em, expira_em, agente, ip)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (token_hash, usuario_id, csrf, criada_em, expira_em, agente, ip),
    )
    conexao.commit()


def abertas_do_usuario(conexao: psycopg.Connection, usuario_id: int, agora: str) -> list[Aberta]:
    """As sessões não expiradas do usuário, da mais recente para a mais antiga."""
    linhas = conexao.execute(
        "SELECT id, criada_em, agente, ip, token_hash FROM sessao"
        " WHERE usuario_id = %s AND expira_em > %s ORDER BY criada_em DESC, id DESC",
        (usuario_id, agora),
    ).fetchall()
    return [Aberta(*linha) for linha in linhas]


def apagar_do_usuario(conexao: psycopg.Connection, usuario_id: int, sessao_id: int) -> bool:
    cursor = conexao.execute(
        "DELETE FROM sessao WHERE id = %s AND usuario_id = %s", (sessao_id, usuario_id)
    )
    conexao.commit()
    return cursor.rowcount > 0


def apagar_outras(conexao: psycopg.Connection, usuario_id: int, manter_token_hash: str) -> int:
    cursor = conexao.execute(
        "DELETE FROM sessao WHERE usuario_id = %s AND token_hash != %s",
        (usuario_id, manter_token_hash),
    )
    conexao.commit()
    return cursor.rowcount


def achar(conexao: psycopg.Connection, token_hash: str, agora: str) -> Sessao | None:
    linha = conexao.execute(
        "SELECT usuario_id, bd_id, csrf FROM sessao WHERE token_hash = %s AND expira_em > %s",
        (token_hash, agora),
    ).fetchone()
    return Sessao(*linha) if linha else None


def definir_bd(conexao: psycopg.Connection, token_hash: str, bd_id: int | None) -> None:
    conexao.execute("UPDATE sessao SET bd_id = %s WHERE token_hash = %s", (bd_id, token_hash))
    conexao.commit()


def apagar(conexao: psycopg.Connection, token_hash: str) -> None:
    conexao.execute("DELETE FROM sessao WHERE token_hash = %s", (token_hash,))
    conexao.commit()


def registrar_tentativa(conexao: psycopg.Connection, email: str, em: str) -> None:
    conexao.execute("INSERT INTO tentativa_login (email, em) VALUES (%s, %s)", (email, em))
    conexao.commit()


def contar_tentativas(conexao: psycopg.Connection, email: str, desde: str) -> int:
    return conexao.execute(
        "SELECT COUNT(*) FROM tentativa_login WHERE lower(email) = lower(%s) AND em >= %s",
        (email, desde),
    ).fetchone()[0]


def limpar_tentativas(conexao: psycopg.Connection, email: str) -> None:
    conexao.execute("DELETE FROM tentativa_login WHERE lower(email) = lower(%s)", (email,))
    conexao.commit()
