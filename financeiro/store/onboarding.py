import sqlite3

# Cada contagem conta registros do BD; a chave é a que `financeiro.onboarding` usa.
_CONTAGENS = {
    "squad": "SELECT COUNT(*) FROM org WHERE bd_id = ? AND tipo = 'Squad'",
    "iniciativa": "SELECT COUNT(*) FROM iniciativa WHERE bd_id = ?",
    "demanda": "SELECT COUNT(*) FROM demanda WHERE bd_id = ?",
    "agrupamento": "SELECT COUNT(*) FROM agrupamento WHERE bd_id = ?",
    "tema": "SELECT COUNT(*) FROM tema WHERE bd_id = ?",
    "cargo": "SELECT COUNT(*) FROM cargo WHERE bd_id = ?",
    "tarifa": "SELECT COUNT(*) FROM tarifa WHERE bd_id = ?",
    "markup": "SELECT COUNT(*) FROM markup WHERE bd_id = ?",
    "pessoa": "SELECT COUNT(*) FROM pessoa WHERE bd_id = ?",
    "revisao": "SELECT COUNT(*) FROM pdd_revisao WHERE bd_id = ?",
    "compra": "SELECT COUNT(*) FROM compra WHERE bd_id = ?",
    "calendario": (
        "SELECT (SELECT COUNT(*) FROM calendario_mes WHERE bd_id = :bd)"
        " + (SELECT COUNT(*) FROM feriado_bd WHERE bd_id = :bd)"
    ),
}


def contagens(conexao: sqlite3.Connection, bd_id: int) -> dict[str, int]:
    """Quantos registros o BD tem de cada cadastro que o onboarding confere."""
    resultado = {}
    for chave, sql in _CONTAGENS.items():
        parametros = {"bd": bd_id} if ":bd" in sql else (bd_id,)
        resultado[chave] = conexao.execute(sql, parametros).fetchone()[0]
    return resultado


def dispensados(conexao: sqlite3.Connection, bd_id: int) -> set[str]:
    linhas = conexao.execute(
        "SELECT passo FROM onboarding_dispensa WHERE bd_id = ?", (bd_id,)
    ).fetchall()
    return {passo for (passo,) in linhas}


def dispensar(conexao: sqlite3.Connection, bd_id: int, passo: str) -> None:
    conexao.execute(
        "INSERT OR IGNORE INTO onboarding_dispensa (bd_id, passo) VALUES (?, ?)", (bd_id, passo)
    )
    conexao.commit()


def desfazer_dispensa(conexao: sqlite3.Connection, bd_id: int, passo: str) -> None:
    conexao.execute("DELETE FROM onboarding_dispensa WHERE bd_id = ? AND passo = ?", (bd_id, passo))
    conexao.commit()


def marcar_aberto(conexao: sqlite3.Connection, bd_id: int) -> bool:
    """Marca o BD como já aberto. Devolve True só para quem fez a marca (atômico)."""
    cursor = conexao.execute(
        "UPDATE bd SET onboarding_aberto = 1 WHERE id = ? AND onboarding_aberto = 0", (bd_id,)
    )
    conexao.commit()
    return cursor.rowcount == 1
