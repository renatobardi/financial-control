from typing import NamedTuple

import psycopg


class Congelado(NamedTuple):
    horas: int
    pessoas_centavos: int
    compras_centavos: int


class EntradaLog(NamedTuple):
    mes: str
    acao: str
    autor: str
    em: str
    motivo: str
    valor_centavos: int | None


def meses_fechados(conexao: psycopg.Connection, bd_id: int) -> list[str]:
    linhas = conexao.execute(
        "SELECT mes FROM mes_fechado WHERE bd_id = %s ORDER BY mes", (bd_id,)
    ).fetchall()
    return [linha[0] for linha in linhas]


def congelado_do_mes(conexao: psycopg.Connection, bd_id: int, mes: str) -> Congelado | None:
    linha = conexao.execute(
        "SELECT horas, pessoas_centavos, compras_centavos FROM mes_fechado"
        " WHERE bd_id = %s AND mes = %s",
        (bd_id, mes),
    ).fetchone()
    return Congelado(*linha) if linha else None


def fechar_mes(
    conexao: psycopg.Connection, bd_id: int, mes: str, em: str, congelado: Congelado
) -> None:
    conexao.execute(
        "INSERT INTO mes_fechado (bd_id, mes, fechado_em, horas, pessoas_centavos,"
        " compras_centavos) VALUES (%s, %s, %s, %s, %s, %s)",
        (bd_id, mes, em, *congelado),
    )


def reabrir_mes(conexao: psycopg.Connection, bd_id: int, mes: str) -> None:
    conexao.execute("DELETE FROM mes_fechado WHERE bd_id = %s AND mes = %s", (bd_id, mes))


def registrar_log(
    conexao: psycopg.Connection,
    bd_id: int,
    mes: str,
    acao: str,
    usuario_id: int,
    em: str,
    motivo: str,
    valor_centavos: int | None = None,
) -> None:
    conexao.execute(
        "INSERT INTO fechamento_log (bd_id, mes, acao, usuario_id, em, motivo, valor_centavos)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (bd_id, mes, acao, usuario_id, em, motivo, valor_centavos),
    )


def listar_log(conexao: psycopg.Connection, bd_id: int) -> list[EntradaLog]:
    linhas = conexao.execute(
        "SELECT l.mes, l.acao, u.nome, l.em, l.motivo, l.valor_centavos FROM fechamento_log l"
        " JOIN usuario u ON u.id = l.usuario_id WHERE l.bd_id = %s ORDER BY l.id DESC",
        (bd_id,),
    ).fetchall()
    return [EntradaLog(*linha) for linha in linhas]


def primeiro_ano_com_dados(conexao: psycopg.Connection, bd_id: int) -> int | None:
    linha = conexao.execute(
        "SELECT MIN(ano) FROM ("
        " SELECT CAST(SUBSTR(mes, 1, 4) AS INTEGER) AS ano FROM alocacao WHERE bd_id = %s"
        " UNION ALL SELECT CAST(SUBSTR(mes, 1, 4) AS INTEGER) FROM compra_mes WHERE bd_id = %s"
        " UNION ALL SELECT ano FROM calendario_mes WHERE bd_id = %s)",
        (bd_id, bd_id, bd_id),
    ).fetchone()
    return linha[0]


def horas_por_cargo(conexao: psycopg.Connection, bd_id: int, mes: str) -> list[tuple[int, int]]:
    linhas = conexao.execute(
        "SELECT p.cargo_id, SUM(a.horas) FROM alocacao a"
        " JOIN pessoa p ON p.bd_id = a.bd_id AND p.id = a.pessoa_id"
        " WHERE a.bd_id = %s AND a.mes = %s GROUP BY p.cargo_id",
        (bd_id, mes),
    ).fetchall()
    return [(cargo, horas) for cargo, horas in linhas]


def compras_liquidas(conexao: psycopg.Connection, bd_id: int, mes: str) -> tuple[int, int]:
    """(valor líquido, número de ordens) das ordens não canceladas com valor no mês."""
    linha = conexao.execute(
        "SELECT COALESCE(SUM(m.valor_liquido_centavos), 0), COUNT(DISTINCT m.compra_id)"
        " FROM compra_mes m JOIN compra c ON c.bd_id = m.bd_id AND c.id = m.compra_id"
        " WHERE m.bd_id = %s AND m.mes = %s AND c.status != 'cancelada'",
        (bd_id, mes),
    ).fetchone()
    return linha[0], linha[1]


def pessoas_com_horas(conexao: psycopg.Connection, bd_id: int, mes: str) -> int:
    return conexao.execute(
        "SELECT COUNT(DISTINCT pessoa_id) FROM alocacao WHERE bd_id = %s AND mes = %s",
        (bd_id, mes),
    ).fetchone()[0]


def cargas_com_rejeicao_pendente(conexao: psycopg.Connection, bd_id: int) -> int:
    return conexao.execute(
        "SELECT COUNT(DISTINCT r.carga_id) FROM carga_rejeicao r"
        " JOIN carga c ON c.bd_id = r.bd_id AND c.id = r.carga_id"
        " WHERE r.bd_id = %s AND c.estado = 'ativa' AND r.aprovada = 0",
        (bd_id,),
    ).fetchone()[0]
