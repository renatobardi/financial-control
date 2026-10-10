import sqlite3
from typing import NamedTuple


class Simples(NamedTuple):
    id: int
    nome: str


class Iniciativa(NamedTuple):
    id: int
    codigo: str
    nome: str


class Demanda(NamedTuple):
    id: int
    codigo: str
    iniciativa_id: int
    iniciativa: str
    nome: str
    tipo: str
    squad_id: int | None


class Tema(NamedTuple):
    id: int
    codigo: str
    demanda_id: int
    demanda: str
    iniciativa: str
    tipo: str
    nome: str
    agrupamento_id: int
    agrupamento: str


def _inserir(conexao: sqlite3.Connection, sql: str, parametros: tuple) -> int:
    cursor = conexao.execute(sql, parametros)
    conexao.commit()
    return cursor.lastrowid


def criar_agrupamento(conexao: sqlite3.Connection, bd_id: int, nome: str) -> int:
    return _inserir(conexao, "INSERT INTO agrupamento (bd_id, nome) VALUES (?, ?)", (bd_id, nome))


def listar_agrupamentos(conexao: sqlite3.Connection, bd_id: int) -> list[Simples]:
    linhas = conexao.execute(
        "SELECT id, nome FROM agrupamento WHERE bd_id = ? ORDER BY id", (bd_id,)
    ).fetchall()
    return [Simples(*linha) for linha in linhas]


def criar_fornecedor(conexao: sqlite3.Connection, bd_id: int, nome: str) -> int:
    return _inserir(conexao, "INSERT INTO fornecedor (bd_id, nome) VALUES (?, ?)", (bd_id, nome))


def listar_fornecedores(conexao: sqlite3.Connection, bd_id: int) -> list[Simples]:
    linhas = conexao.execute(
        "SELECT id, nome FROM fornecedor WHERE bd_id = ? ORDER BY id", (bd_id,)
    ).fetchall()
    return [Simples(*linha) for linha in linhas]


def criar_iniciativa(conexao: sqlite3.Connection, bd_id: int, codigo: str, nome: str) -> int:
    return _inserir(
        conexao,
        "INSERT INTO iniciativa (bd_id, codigo, nome) VALUES (?, ?, ?)",
        (bd_id, codigo, nome),
    )


def listar_iniciativas(conexao: sqlite3.Connection, bd_id: int) -> list[Iniciativa]:
    linhas = conexao.execute(
        "SELECT id, codigo, nome FROM iniciativa WHERE bd_id = ? ORDER BY id", (bd_id,)
    ).fetchall()
    return [Iniciativa(*linha) for linha in linhas]


def criar_demanda(
    conexao: sqlite3.Connection,
    bd_id: int,
    codigo: str,
    iniciativa_id: int,
    nome: str,
    tipo: str,
    squad_id: int | None,
) -> int:
    return _inserir(
        conexao,
        "INSERT INTO demanda (bd_id, codigo, iniciativa_id, nome, tipo, squad_id)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (bd_id, codigo, iniciativa_id, nome, tipo, squad_id),
    )


def listar_demandas(conexao: sqlite3.Connection, bd_id: int) -> list[Demanda]:
    linhas = conexao.execute(
        "SELECT d.id, d.codigo, d.iniciativa_id, i.nome, d.nome, d.tipo, d.squad_id"
        " FROM demanda d JOIN iniciativa i ON i.bd_id = d.bd_id AND i.id = d.iniciativa_id"
        " WHERE d.bd_id = ? ORDER BY d.id",
        (bd_id,),
    ).fetchall()
    return [Demanda(*linha) for linha in linhas]


def criar_tema(
    conexao: sqlite3.Connection,
    bd_id: int,
    codigo: str,
    demanda_id: int,
    nome: str,
    agrupamento_id: int,
) -> int:
    return _inserir(
        conexao,
        "INSERT INTO tema (bd_id, codigo, demanda_id, nome, agrupamento_id) VALUES (?, ?, ?, ?, ?)",
        (bd_id, codigo, demanda_id, nome, agrupamento_id),
    )


def listar_temas(conexao: sqlite3.Connection, bd_id: int) -> list[Tema]:
    linhas = conexao.execute(
        "SELECT t.id, t.codigo, t.demanda_id, d.nome, i.nome, d.tipo, t.nome, a.id, a.nome"
        " FROM tema t"
        " JOIN demanda d ON d.bd_id = t.bd_id AND d.id = t.demanda_id"
        " JOIN iniciativa i ON i.bd_id = d.bd_id AND i.id = d.iniciativa_id"
        " JOIN agrupamento a ON a.bd_id = t.bd_id AND a.id = t.agrupamento_id"
        " WHERE t.bd_id = ? ORDER BY t.id",
        (bd_id,),
    ).fetchall()
    return [Tema(*linha) for linha in linhas]
