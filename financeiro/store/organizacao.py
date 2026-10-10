import sqlite3
from typing import NamedTuple


class Org(NamedTuple):
    id: int
    tipo: str
    nome: str
    pai_id: int | None
    gestor: str
    inicio: str
    fim: str | None


_COLUNAS = "id, tipo, nome, pai_id, gestor, vigencia_ini, vigencia_fim"


def criar_org(
    conexao: sqlite3.Connection,
    bd_id: int,
    tipo: str,
    nome: str,
    pai_id: int | None,
    gestor: str,
    inicio: str,
) -> int:
    cursor = conexao.execute(
        "INSERT INTO org (bd_id, tipo, nome, pai_id, gestor, vigencia_ini)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (bd_id, tipo, nome, pai_id, gestor, inicio),
    )
    conexao.commit()
    return cursor.lastrowid


def achar_org(conexao: sqlite3.Connection, bd_id: int, org_id: int) -> Org | None:
    linha = conexao.execute(
        f"SELECT {_COLUNAS} FROM org WHERE bd_id = ? AND id = ?", (bd_id, org_id)
    ).fetchone()
    return Org(*linha) if linha else None


def listar_orgs(conexao: sqlite3.Connection, bd_id: int) -> list[Org]:
    linhas = conexao.execute(
        f"SELECT {_COLUNAS} FROM org WHERE bd_id = ? ORDER BY id", (bd_id,)
    ).fetchall()
    return [Org(*linha) for linha in linhas]


def mover_org(conexao: sqlite3.Connection, bd_id: int, org_id: int, novo_pai_id: int) -> None:
    conexao.execute(
        "UPDATE org SET pai_id = ? WHERE bd_id = ? AND id = ?", (novo_pai_id, bd_id, org_id)
    )
    conexao.commit()


def alterar_gestor(conexao: sqlite3.Connection, bd_id: int, org_id: int, gestor: str) -> None:
    conexao.execute("UPDATE org SET gestor = ? WHERE bd_id = ? AND id = ?", (gestor, bd_id, org_id))
    conexao.commit()


def registrar_historico(
    conexao: sqlite3.Connection, bd_id: int, org_id: int, em: str, texto: str
) -> None:
    conexao.execute(
        "INSERT INTO org_historico (bd_id, org_id, em, texto) VALUES (?, ?, ?, ?)",
        (bd_id, org_id, em, texto),
    )
    conexao.commit()


def historico(conexao: sqlite3.Connection, bd_id: int, org_id: int) -> list[tuple[str, str]]:
    linhas = conexao.execute(
        "SELECT em, texto FROM org_historico WHERE bd_id = ? AND org_id = ? ORDER BY id",
        (bd_id, org_id),
    ).fetchall()
    return [(em, texto) for em, texto in linhas]
