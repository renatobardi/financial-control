from typing import NamedTuple

import psycopg


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
    conexao: psycopg.Connection,
    bd_id: int,
    tipo: str,
    nome: str,
    pai_id: int | None,
    gestor: str,
    inicio: str,
) -> int:
    cursor = conexao.execute(
        "INSERT INTO org (bd_id, tipo, nome, pai_id, gestor, vigencia_ini)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (bd_id, tipo, nome, pai_id, gestor, inicio),
    )
    conexao.commit()
    return cursor.fetchone()[0]


def achar_org(conexao: psycopg.Connection, bd_id: int, org_id: int) -> Org | None:
    linha = conexao.execute(
        f"SELECT {_COLUNAS} FROM org WHERE bd_id = %s AND id = %s", (bd_id, org_id)
    ).fetchone()
    return Org(*linha) if linha else None


def listar_orgs(conexao: psycopg.Connection, bd_id: int) -> list[Org]:
    linhas = conexao.execute(
        f"SELECT {_COLUNAS} FROM org WHERE bd_id = %s ORDER BY id", (bd_id,)
    ).fetchall()
    return [Org(*linha) for linha in linhas]


def mover_org(conexao: psycopg.Connection, bd_id: int, org_id: int, novo_pai_id: int) -> None:
    conexao.execute(
        "UPDATE org SET pai_id = %s WHERE bd_id = %s AND id = %s", (novo_pai_id, bd_id, org_id)
    )
    conexao.commit()


def alterar_gestor(conexao: psycopg.Connection, bd_id: int, org_id: int, gestor: str) -> None:
    conexao.execute(
        "UPDATE org SET gestor = %s WHERE bd_id = %s AND id = %s", (gestor, bd_id, org_id)
    )
    conexao.commit()


def registrar_historico(
    conexao: psycopg.Connection, bd_id: int, org_id: int, em: str, texto: str
) -> None:
    conexao.execute(
        "INSERT INTO org_historico (bd_id, org_id, em, texto) VALUES (%s, %s, %s, %s)",
        (bd_id, org_id, em, texto),
    )
    conexao.commit()


def historico(conexao: psycopg.Connection, bd_id: int, org_id: int) -> list[tuple[str, str]]:
    linhas = conexao.execute(
        "SELECT em, texto FROM org_historico WHERE bd_id = %s AND org_id = %s ORDER BY id",
        (bd_id, org_id),
    ).fetchall()
    return [(em, texto) for em, texto in linhas]
