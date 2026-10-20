from typing import NamedTuple

import psycopg


class Lancamento(NamedTuple):
    origem: str
    pessoa_id: int | None
    compra_id: int | None
    tema_id: int | None
    demanda_id: int
    iniciativa_id: int
    tipo: str
    agrupamento_id: int | None
    org_id: int | None
    empresa_id: int | None
    cargo_id: int | None
    horas: int
    liquido_centavos: int  # compras: valor líquido; pessoas: preenchido pelo serviço
    bruto_centavos: int


def alocacoes_do_mes(conexao: psycopg.Connection, bd_id: int, mes: str) -> list[tuple]:
    """(pessoa, tema, demanda, iniciativa, tipo, agrupamento, org, empresa, cargo, horas)."""
    return conexao.execute(
        "SELECT a.pessoa_id, a.tema_id, d.id, d.iniciativa_id, d.tipo, t.agrupamento_id,"
        " p.org_id, c.empresa_id, p.cargo_id, a.horas"
        " FROM alocacao a"
        " JOIN pessoa p ON p.bd_id = a.bd_id AND p.id = a.pessoa_id"
        " JOIN tema t ON t.bd_id = a.bd_id AND t.id = a.tema_id"
        " JOIN demanda d ON d.bd_id = t.bd_id AND d.id = t.demanda_id"
        " JOIN cargo c ON c.bd_id = p.bd_id AND c.id = p.cargo_id"
        " WHERE a.bd_id = %s AND a.mes = %s ORDER BY a.id",
        (bd_id, mes),
    ).fetchall()


def compras_do_mes(conexao: psycopg.Connection, bd_id: int, mes: str) -> list[tuple]:
    """(compra, demanda, iniciativa, tipo, squad da demanda, valor líquido), sem canceladas."""
    return conexao.execute(
        "SELECT m.compra_id, d.id, d.iniciativa_id, d.tipo, d.squad_id, m.valor_liquido_centavos"
        " FROM compra_mes m"
        " JOIN compra c ON c.bd_id = m.bd_id AND c.id = m.compra_id"
        " JOIN demanda d ON d.bd_id = c.bd_id AND d.id = c.demanda_id"
        " WHERE m.bd_id = %s AND m.mes = %s AND c.status != 'cancelada' ORDER BY m.id",
        (bd_id, mes),
    ).fetchall()


def gravar_realizado(
    conexao: psycopg.Connection, bd_id: int, mes: str, linhas: list[Lancamento]
) -> None:
    conexao.cursor().executemany(
        "INSERT INTO realizado_linha (bd_id, mes, origem, pessoa_id, compra_id, tema_id,"
        " demanda_id, iniciativa_id, tipo, agrupamento_id, org_id, empresa_id, cargo_id, horas,"
        " liquido_centavos, bruto_centavos)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        [(bd_id, mes, *linha) for linha in linhas],
    )


def apagar_realizado(conexao: psycopg.Connection, bd_id: int, mes: str) -> None:
    conexao.execute("DELETE FROM realizado_linha WHERE bd_id = %s AND mes = %s", (bd_id, mes))


def ler_realizado(conexao: psycopg.Connection, bd_id: int, mes: str) -> list[Lancamento]:
    linhas = conexao.execute(
        "SELECT origem, pessoa_id, compra_id, tema_id, demanda_id, iniciativa_id, tipo,"
        " agrupamento_id, org_id, empresa_id, cargo_id, horas, liquido_centavos, bruto_centavos"
        " FROM realizado_linha WHERE bd_id = %s AND mes = %s ORDER BY id",
        (bd_id, mes),
    ).fetchall()
    return [Lancamento(*linha) for linha in linhas]


def mes_esta_fechado(conexao: psycopg.Connection, bd_id: int, mes: str) -> bool:
    return (
        conexao.execute(
            "SELECT 1 FROM mes_fechado WHERE bd_id = %s AND mes = %s", (bd_id, mes)
        ).fetchone()
        is not None
    )


def horas_extras_aprovadas(conexao: psycopg.Connection, bd_id: int, ano: int) -> int:
    return conexao.execute(
        "SELECT COALESCE(SUM(horas), 0) FROM alocacao"
        " WHERE bd_id = %s AND extra = 1 AND mes LIKE %s",
        (bd_id, f"{ano:04d}-%"),
    ).fetchone()[0]


def ordens_previstas(conexao: psycopg.Connection, bd_id: int) -> int:
    return conexao.execute(
        "SELECT COUNT(*) FROM compra WHERE bd_id = %s AND status = 'prevista'", (bd_id,)
    ).fetchone()[0]


def ultima_carga_em(conexao: psycopg.Connection, bd_id: int) -> str | None:
    linha = conexao.execute(
        "SELECT MAX(em) FROM carga WHERE bd_id = %s AND estado = 'ativa'", (bd_id,)
    ).fetchone()
    return linha[0]
