import sqlite3
from typing import NamedTuple

from financeiro.store.escopo import entre_bds


class Usuario(NamedTuple):
    id: int
    email: str
    nome: str
    senha_hash: str | None
    tema: str
    formato_valor: str
    tela_inicial: str
    bd_padrao_id: int | None


class BdDoUsuario(NamedTuple):
    id: int
    nome: str
    sigla: str
    papel: str


class Membro(NamedTuple):
    usuario_id: int
    email: str
    nome: str
    papel: str
    pendente: bool


def criar_bd(conexao: sqlite3.Connection, nome: str, sigla: str) -> int:
    cursor = conexao.execute("INSERT INTO bd (nome, sigla) VALUES (?, ?)", (nome, sigla))
    conexao.commit()
    return cursor.lastrowid


def criar_usuario(
    conexao: sqlite3.Connection, email: str, nome: str, senha_hash: str | None
) -> int:
    cursor = conexao.execute(
        "INSERT INTO usuario (email, nome, senha_hash) VALUES (?, ?, ?)", (email, nome, senha_hash)
    )
    conexao.commit()
    return cursor.lastrowid


def achar_usuario_por_email(conexao: sqlite3.Connection, email: str) -> Usuario | None:
    linha = conexao.execute(
        "SELECT id, email, nome, senha_hash, tema, formato_valor, tela_inicial, bd_padrao_id"
        " FROM usuario WHERE email = ?",
        (email,),
    ).fetchone()
    return Usuario(*linha) if linha else None


def achar_usuario(conexao: sqlite3.Connection, usuario_id: int) -> Usuario | None:
    linha = conexao.execute(
        "SELECT id, email, nome, senha_hash, tema, formato_valor, tela_inicial, bd_padrao_id"
        " FROM usuario WHERE id = ?",
        (usuario_id,),
    ).fetchone()
    return Usuario(*linha) if linha else None


def nome_do_bd(conexao: sqlite3.Connection, bd_id: int) -> str | None:
    linha = conexao.execute("SELECT nome FROM bd WHERE id = ?", (bd_id,)).fetchone()
    return linha[0] if linha else None


def adicionar_membro(conexao: sqlite3.Connection, bd_id: int, usuario_id: int, papel: str) -> None:
    conexao.execute(
        "INSERT INTO membro (bd_id, usuario_id, papel) VALUES (?, ?, ?)",
        (bd_id, usuario_id, papel),
    )
    conexao.commit()


def papel_do(conexao: sqlite3.Connection, bd_id: int, usuario_id: int) -> str | None:
    linha = conexao.execute(
        "SELECT papel FROM membro WHERE bd_id = ? AND usuario_id = ?", (bd_id, usuario_id)
    ).fetchone()
    return linha[0] if linha else None


def membros_do_bd(conexao: sqlite3.Connection, bd_id: int) -> list[Membro]:
    linhas = conexao.execute(
        "SELECT u.id, u.email, u.nome, m.papel, u.senha_hash IS NULL"
        " FROM membro m JOIN usuario u ON u.id = m.usuario_id"
        " WHERE m.bd_id = ? ORDER BY u.nome",
        (bd_id,),
    ).fetchall()
    return [Membro(i, e, n, p, bool(pend)) for i, e, n, p, pend in linhas]


def alterar_papel(conexao: sqlite3.Connection, bd_id: int, usuario_id: int, papel: str) -> None:
    conexao.execute(
        "UPDATE membro SET papel = ? WHERE bd_id = ? AND usuario_id = ?",
        (papel, bd_id, usuario_id),
    )
    conexao.commit()


def remover_membro(conexao: sqlite3.Connection, bd_id: int, usuario_id: int) -> None:
    conexao.execute("DELETE FROM membro WHERE bd_id = ? AND usuario_id = ?", (bd_id, usuario_id))
    conexao.commit()


@entre_bds
def bds_do_usuario(conexao: sqlite3.Connection, usuario_id: int) -> list[BdDoUsuario]:
    """Os BDs a que o usuário pertence, para escolher o BD ao entrar."""
    linhas = conexao.execute(
        "SELECT b.id, b.nome, b.sigla, m.papel"
        " FROM membro m JOIN bd b ON b.id = m.bd_id"
        " WHERE m.usuario_id = ? ORDER BY b.id",
        (usuario_id,),
    ).fetchall()
    return [BdDoUsuario(*linha) for linha in linhas]
