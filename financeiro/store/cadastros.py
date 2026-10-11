import sqlite3
from typing import NamedTuple

from financeiro import vigencia


class Empresa(NamedTuple):
    id: int
    nome: str
    tipo: str


class Cargo(NamedTuple):
    id: int
    empresa_id: int
    empresa: str
    nome: str
    nivel: str


class Tarifa(NamedTuple):
    id: int
    cargo_id: int
    liquida_centavos: int
    inicio: str
    fim: str | None


class Markup(NamedTuple):
    id: int
    centesimos_pct: int
    inicio: str
    fim: str | None


# ---- Empresa ----


def criar_empresa(conexao: sqlite3.Connection, bd_id: int, nome: str, tipo: str) -> int:
    cursor = conexao.execute(
        "INSERT INTO empresa (bd_id, nome, tipo) VALUES (?, ?, ?)", (bd_id, nome, tipo)
    )
    conexao.commit()
    return cursor.lastrowid


def listar_empresas(conexao: sqlite3.Connection, bd_id: int) -> list[Empresa]:
    linhas = conexao.execute(
        "SELECT id, nome, tipo FROM empresa WHERE bd_id = ? ORDER BY id", (bd_id,)
    ).fetchall()
    return [Empresa(*linha) for linha in linhas]


# ---- Cargo ----


def criar_cargo(
    conexao: sqlite3.Connection, bd_id: int, empresa_id: int, nome: str, nivel: str
) -> int:
    cursor = conexao.execute(
        "INSERT INTO cargo (bd_id, empresa_id, nome, nivel) VALUES (?, ?, ?, ?)",
        (bd_id, empresa_id, nome, nivel),
    )
    conexao.commit()
    return cursor.lastrowid


_SELECT_CARGO = (
    "SELECT c.id, c.empresa_id, e.nome, c.nome, c.nivel FROM cargo c"
    " JOIN empresa e ON e.bd_id = c.bd_id AND e.id = c.empresa_id"
)


def achar_cargo(conexao: sqlite3.Connection, bd_id: int, cargo_id: int) -> Cargo | None:
    linha = conexao.execute(
        _SELECT_CARGO + " WHERE c.bd_id = ? AND c.id = ?", (bd_id, cargo_id)
    ).fetchone()
    return Cargo(*linha) if linha else None


def listar_cargos(conexao: sqlite3.Connection, bd_id: int) -> list[Cargo]:
    linhas = conexao.execute(
        _SELECT_CARGO + " WHERE c.bd_id = ? ORDER BY c.id", (bd_id,)
    ).fetchall()
    return [Cargo(*linha) for linha in linhas]


# ---- Tarifa (vigência por cargo; o cargo já é o par cargo + empresa) ----


def tarifas_do_cargo(conexao: sqlite3.Connection, bd_id: int, cargo_id: int) -> list[Tarifa]:
    linhas = conexao.execute(
        "SELECT id, cargo_id, liquida_centavos, vigencia_ini, vigencia_fim FROM tarifa"
        " WHERE bd_id = ? AND cargo_id = ? ORDER BY vigencia_ini",
        (bd_id, cargo_id),
    ).fetchall()
    return [Tarifa(*linha) for linha in linhas]


def definir_tarifa(
    conexao: sqlite3.Connection, bd_id: int, cargo_id: int, liquida_centavos: int, a_partir_de: str
) -> int:
    """Nova tarifa vigente a partir do mês. A aberta é encerrada no mês anterior.

    Recusa início que não seja posterior a toda vigência já cadastrada do cargo.
    """
    vigencia.validar_mes(a_partir_de)
    existentes = tarifas_do_cargo(conexao, bd_id, cargo_id)
    if existentes and a_partir_de <= max(t.inicio for t in existentes):
        raise vigencia.VigenciaSobreposta(a_partir_de)
    conexao.execute(
        "UPDATE tarifa SET vigencia_fim = ?"
        " WHERE bd_id = ? AND cargo_id = ? AND vigencia_fim IS NULL",
        (vigencia.mes_anterior(a_partir_de), bd_id, cargo_id),
    )
    cursor = conexao.execute(
        "INSERT INTO tarifa (bd_id, cargo_id, liquida_centavos, vigencia_ini) VALUES (?, ?, ?, ?)",
        (bd_id, cargo_id, liquida_centavos, a_partir_de),
    )
    conexao.commit()
    return cursor.lastrowid


def tarifa_vigente(
    conexao: sqlite3.Connection, bd_id: int, cargo_id: int, mes: str
) -> Tarifa | None:
    linha = conexao.execute(
        "SELECT id, cargo_id, liquida_centavos, vigencia_ini, vigencia_fim FROM tarifa"
        " WHERE bd_id = ? AND cargo_id = ? AND vigencia_ini <= ?"
        " AND ? <= COALESCE(vigencia_fim, '9999-12')",
        (bd_id, cargo_id, mes, mes),
    ).fetchone()
    return Tarifa(*linha) if linha else None


# ---- Markup (vigência por BD) ----


def listar_markups(conexao: sqlite3.Connection, bd_id: int) -> list[Markup]:
    linhas = conexao.execute(
        "SELECT id, centesimos_pct, vigencia_ini, vigencia_fim FROM markup"
        " WHERE bd_id = ? ORDER BY vigencia_ini",
        (bd_id,),
    ).fetchall()
    return [Markup(*linha) for linha in linhas]


def definir_markup(
    conexao: sqlite3.Connection, bd_id: int, centesimos_pct: int, a_partir_de: str
) -> int:
    vigencia.validar_mes(a_partir_de)
    existentes = listar_markups(conexao, bd_id)
    if existentes and a_partir_de <= max(m.inicio for m in existentes):
        raise vigencia.VigenciaSobreposta(a_partir_de)
    conexao.execute(
        "UPDATE markup SET vigencia_fim = ? WHERE bd_id = ? AND vigencia_fim IS NULL",
        (vigencia.mes_anterior(a_partir_de), bd_id),
    )
    cursor = conexao.execute(
        "INSERT INTO markup (bd_id, centesimos_pct, vigencia_ini) VALUES (?, ?, ?)",
        (bd_id, centesimos_pct, a_partir_de),
    )
    conexao.commit()
    return cursor.lastrowid


def markup_vigente(conexao: sqlite3.Connection, bd_id: int, mes: str) -> Markup | None:
    linha = conexao.execute(
        "SELECT id, centesimos_pct, vigencia_ini, vigencia_fim FROM markup"
        " WHERE bd_id = ? AND vigencia_ini <= ? AND ? <= COALESCE(vigencia_fim, '9999-12')",
        (bd_id, mes, mes),
    ).fetchone()
    return Markup(*linha) if linha else None


def alterar_markup_vigente(conexao: sqlite3.Connection, bd_id: int, centesimos_pct: int) -> bool:
    """Troca o percentual do markup vigente (o de vigência aberta). False se não há vigente."""
    cursor = conexao.execute(
        "UPDATE markup SET centesimos_pct = ? WHERE bd_id = ? AND vigencia_fim IS NULL",
        (centesimos_pct, bd_id),
    )
    conexao.commit()
    return cursor.rowcount > 0
