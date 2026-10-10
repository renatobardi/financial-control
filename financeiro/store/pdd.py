import sqlite3
from typing import NamedTuple


class Revisao(NamedTuple):
    id: int
    rotulo: str
    estado: str
    markup_centesimos_pct: int | None
    criada_em: str
    aprovada_em: str | None


class LinhaPdd(NamedTuple):
    id: int
    iniciativa_id: int
    codigo: str
    iniciativa: str
    tipo: str
    bruto_centavos: int


_REVISAO = "id, rotulo, estado, markup_centesimos_pct, criada_em, aprovada_em"


def listar_revisoes(conexao: sqlite3.Connection, bd_id: int) -> list[Revisao]:
    linhas = conexao.execute(
        f"SELECT {_REVISAO} FROM pdd_revisao WHERE bd_id = ? ORDER BY id", (bd_id,)
    ).fetchall()
    return [Revisao(*linha) for linha in linhas]


def achar_revisao(conexao: sqlite3.Connection, bd_id: int, revisao_id: int) -> Revisao | None:
    linha = conexao.execute(
        f"SELECT {_REVISAO} FROM pdd_revisao WHERE bd_id = ? AND id = ?", (bd_id, revisao_id)
    ).fetchone()
    return Revisao(*linha) if linha else None


def criar_revisao(conexao: sqlite3.Connection, bd_id: int, rotulo: str, criada_em: str) -> int:
    cursor = conexao.execute(
        "INSERT INTO pdd_revisao (bd_id, rotulo, criada_em) VALUES (?, ?, ?)",
        (bd_id, rotulo, criada_em),
    )
    return cursor.lastrowid


def copiar_linhas(conexao: sqlite3.Connection, bd_id: int, de_id: int, para_id: int) -> None:
    conexao.execute(
        "INSERT INTO pdd_linha (bd_id, revisao_id, iniciativa_id, tipo, valor_bruto_centavos)"
        " SELECT bd_id, ?, iniciativa_id, tipo, valor_bruto_centavos FROM pdd_linha"
        " WHERE bd_id = ? AND revisao_id = ?",
        (para_id, bd_id, de_id),
    )


def linhas_da_revisao(conexao: sqlite3.Connection, bd_id: int, revisao_id: int) -> list[LinhaPdd]:
    linhas = conexao.execute(
        "SELECT l.id, l.iniciativa_id, i.codigo, i.nome, l.tipo, l.valor_bruto_centavos"
        " FROM pdd_linha l JOIN iniciativa i ON i.bd_id = l.bd_id AND i.id = l.iniciativa_id"
        " WHERE l.bd_id = ? AND l.revisao_id = ? ORDER BY i.codigo, l.tipo",
        (bd_id, revisao_id),
    ).fetchall()
    return [LinhaPdd(*linha) for linha in linhas]


def definir_linha(
    conexao: sqlite3.Connection,
    bd_id: int,
    revisao_id: int,
    iniciativa_id: int,
    tipo: str,
    bruto_centavos: int,
) -> None:
    conexao.execute(
        "INSERT INTO pdd_linha (bd_id, revisao_id, iniciativa_id, tipo, valor_bruto_centavos)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT (bd_id, revisao_id, iniciativa_id, tipo)"
        " DO UPDATE SET valor_bruto_centavos = excluded.valor_bruto_centavos",
        (bd_id, revisao_id, iniciativa_id, tipo, bruto_centavos),
    )


def remover_linha(
    conexao: sqlite3.Connection, bd_id: int, revisao_id: int, iniciativa_id: int, tipo: str
) -> None:
    conexao.execute(
        "DELETE FROM pdd_linha WHERE bd_id = ? AND revisao_id = ? AND iniciativa_id = ?"
        " AND tipo = ?",
        (bd_id, revisao_id, iniciativa_id, tipo),
    )


def aprovar_revisao(
    conexao: sqlite3.Connection, bd_id: int, revisao_id: int, markup: int, em: str
) -> None:
    conexao.execute(
        "UPDATE pdd_revisao SET estado = 'aprovada', markup_centesimos_pct = ?, aprovada_em = ?"
        " WHERE bd_id = ? AND id = ?",
        (markup, em, bd_id, revisao_id),
    )


def descartar_revisao(conexao: sqlite3.Connection, bd_id: int, revisao_id: int) -> None:
    conexao.execute("DELETE FROM pdd_linha WHERE bd_id = ? AND revisao_id = ?", (bd_id, revisao_id))
    conexao.execute("DELETE FROM pdd_revisao WHERE bd_id = ? AND id = ?", (bd_id, revisao_id))
