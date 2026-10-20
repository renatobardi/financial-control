import psycopg


def gravar_horas(
    conexao: psycopg.Connection, bd_id: int, ano: int, mes: int, horas: int, ajustado: bool
) -> None:
    conexao.execute(
        "INSERT INTO calendario_mes (bd_id, ano, mes, horas, ajustado) VALUES (%s, %s, %s, %s, %s)"
        " ON CONFLICT (bd_id, ano, mes) DO UPDATE SET horas = excluded.horas,"
        " ajustado = excluded.ajustado",
        (bd_id, ano, mes, horas, int(ajustado)),
    )
    conexao.commit()


def horas_do_mes(conexao: psycopg.Connection, bd_id: int, ano: int, mes: int) -> int | None:
    linha = conexao.execute(
        "SELECT horas FROM calendario_mes WHERE bd_id = %s AND ano = %s AND mes = %s",
        (bd_id, ano, mes),
    ).fetchone()
    return linha[0] if linha else None


def mes_ajustado(conexao: psycopg.Connection, bd_id: int, ano: int, mes: int) -> bool:
    linha = conexao.execute(
        "SELECT ajustado FROM calendario_mes WHERE bd_id = %s AND ano = %s AND mes = %s",
        (bd_id, ano, mes),
    ).fetchone()
    return bool(linha and linha[0])


def adicionar_feriado(conexao: psycopg.Connection, bd_id: int, data: str, nome: str) -> None:
    conexao.execute(
        "INSERT INTO feriado_bd (bd_id, data, nome) VALUES (%s, %s, %s)"
        " ON CONFLICT (bd_id, data) DO UPDATE SET nome = excluded.nome",
        (bd_id, data, nome),
    )
    conexao.commit()


def feriados_do_ano(conexao: psycopg.Connection, bd_id: int, ano: int) -> list[tuple[str, str]]:
    linhas = conexao.execute(
        "SELECT data, nome FROM feriado_bd WHERE bd_id = %s AND data LIKE %s ORDER BY data",
        (bd_id, f"{ano:04d}-%"),
    ).fetchall()
    return [(data, nome) for data, nome in linhas]


def mes_tem_carga(conexao: psycopg.Connection, bd_id: int, mes: str) -> bool:
    """O mês (AAAA-MM) já tem horas lançadas, por carga ou por qualquer outro caminho."""
    return (
        conexao.execute(
            "SELECT 1 FROM alocacao WHERE bd_id = %s AND mes = %s LIMIT 1", (bd_id, mes)
        ).fetchone()
        is not None
    )
