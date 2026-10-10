import sqlite3
from typing import NamedTuple


class Compra(NamedTuple):
    id: int
    numero: str
    tipo: str
    fornecedor_id: int | None
    fornecedor: str | None
    demanda_id: int
    demanda: str
    status: str
    descricao: str

    @property
    def sem_numero(self) -> bool:
        return self.numero.startswith("PREV-")


class Historico(NamedTuple):
    em: str
    autor: str
    texto: str


_SELECT = (
    "SELECT c.id, c.numero, c.tipo, c.fornecedor_id, f.nome, c.demanda_id, d.nome, c.status,"
    " c.descricao FROM compra c"
    " JOIN demanda d ON d.bd_id = c.bd_id AND d.id = c.demanda_id"
    " LEFT JOIN fornecedor f ON f.bd_id = c.bd_id AND f.id = c.fornecedor_id"
)


def proximo_numero_previsto(conexao: sqlite3.Connection, bd_id: int) -> str:
    total = conexao.execute(
        "SELECT COUNT(*) FROM compra WHERE bd_id = ? AND numero LIKE 'PREV-%'", (bd_id,)
    ).fetchone()[0]
    return f"PREV-{total + 1:04d}"


def criar_compra(
    conexao: sqlite3.Connection,
    bd_id: int,
    numero: str,
    tipo: str,
    fornecedor_id: int | None,
    demanda_id: int,
    status: str,
    descricao: str,
) -> int:
    cursor = conexao.execute(
        "INSERT INTO compra (bd_id, numero, tipo, fornecedor_id, demanda_id, status, descricao)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (bd_id, numero, tipo, fornecedor_id, demanda_id, status, descricao),
    )
    return cursor.lastrowid


def achar_compra(conexao: sqlite3.Connection, bd_id: int, compra_id: int) -> Compra | None:
    linha = conexao.execute(
        _SELECT + " WHERE c.bd_id = ? AND c.id = ?", (bd_id, compra_id)
    ).fetchone()
    return Compra(*linha) if linha else None


def listar_compras(conexao: sqlite3.Connection, bd_id: int) -> list[Compra]:
    linhas = conexao.execute(_SELECT + " WHERE c.bd_id = ? ORDER BY c.id", (bd_id,)).fetchall()
    return [Compra(*linha) for linha in linhas]


def atualizar_compra(
    conexao: sqlite3.Connection,
    bd_id: int,
    compra_id: int,
    numero: str,
    tipo: str,
    fornecedor_id: int | None,
    demanda_id: int,
    status: str,
    descricao: str,
) -> None:
    conexao.execute(
        "UPDATE compra SET numero = ?, tipo = ?, fornecedor_id = ?, demanda_id = ?, status = ?,"
        " descricao = ? WHERE bd_id = ? AND id = ?",
        (numero, tipo, fornecedor_id, demanda_id, status, descricao, bd_id, compra_id),
    )


def valores_liquidos(conexao: sqlite3.Connection, bd_id: int, compra_id: int) -> dict[str, int]:
    linhas = conexao.execute(
        "SELECT mes, valor_liquido_centavos FROM compra_mes WHERE bd_id = ? AND compra_id = ?",
        (bd_id, compra_id),
    ).fetchall()
    return dict(linhas)


def meses_com_valor(conexao: sqlite3.Connection, bd_id: int, compra_id: int) -> list[str]:
    return sorted(valores_liquidos(conexao, bd_id, compra_id))


def gravar_valor(
    conexao: sqlite3.Connection, bd_id: int, compra_id: int, mes: str, liquido: int
) -> None:
    if liquido == 0:
        conexao.execute(
            "DELETE FROM compra_mes WHERE bd_id = ? AND compra_id = ? AND mes = ?",
            (bd_id, compra_id, mes),
        )
        return
    conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT (bd_id, compra_id, mes)"
        " DO UPDATE SET valor_liquido_centavos = excluded.valor_liquido_centavos",
        (bd_id, compra_id, mes, liquido),
    )


def registrar_historico(
    conexao: sqlite3.Connection, bd_id: int, compra_id: int, em: str, usuario_id: int, texto: str
) -> None:
    conexao.execute(
        "INSERT INTO compra_historico (bd_id, compra_id, em, usuario_id, texto)"
        " VALUES (?, ?, ?, ?, ?)",
        (bd_id, compra_id, em, usuario_id, texto),
    )


def listar_historico(conexao: sqlite3.Connection, bd_id: int, compra_id: int) -> list[Historico]:
    linhas = conexao.execute(
        "SELECT h.em, u.nome, h.texto FROM compra_historico h"
        " JOIN usuario u ON u.id = h.usuario_id"
        " WHERE h.bd_id = ? AND h.compra_id = ? ORDER BY h.id DESC",
        (bd_id, compra_id),
    ).fetchall()
    return [Historico(*linha) for linha in linhas]


def valores_congelados(
    conexao: sqlite3.Connection, bd_id: int, compra_id: int
) -> dict[str, tuple[int, int]]:
    """{mês: (líquido, bruto)} do que foi congelado no fechamento para a ordem."""
    linhas = conexao.execute(
        "SELECT mes, SUM(liquido_centavos), SUM(bruto_centavos) FROM realizado_linha"
        " WHERE bd_id = ? AND compra_id = ? GROUP BY mes",
        (bd_id, compra_id),
    ).fetchall()
    return {mes: (liq, bru) for mes, liq, bru in linhas}
