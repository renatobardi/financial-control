import sqlite3

# Cada contagem conta registros do BD; a chave é a que `financeiro.onboarding` usa.
_CONTAGENS = {
    "squad": "SELECT COUNT(*) FROM org WHERE bd_id = :bd AND tipo = 'Squad'",
    "iniciativa": "SELECT COUNT(*) FROM iniciativa WHERE bd_id = :bd",
    "demanda": "SELECT COUNT(*) FROM demanda WHERE bd_id = :bd",
    "agrupamento": "SELECT COUNT(*) FROM agrupamento WHERE bd_id = :bd",
    "tema": "SELECT COUNT(*) FROM tema WHERE bd_id = :bd",
    "cargo": "SELECT COUNT(*) FROM cargo WHERE bd_id = :bd",
    "tarifa": "SELECT COUNT(*) FROM tarifa WHERE bd_id = :bd",
    "markup": "SELECT COUNT(*) FROM markup WHERE bd_id = :bd",
    "pessoa": "SELECT COUNT(*) FROM pessoa WHERE bd_id = :bd",
    "revisao": "SELECT COUNT(*) FROM pdd_revisao WHERE bd_id = :bd",
    "compra": "SELECT COUNT(*) FROM compra WHERE bd_id = :bd",
    "calendario": (
        "SELECT (SELECT COUNT(*) FROM calendario_mes WHERE bd_id = :bd)"
        " + (SELECT COUNT(*) FROM feriado_bd WHERE bd_id = :bd)"
    ),
}


def contagens(conexao: sqlite3.Connection, bd_id: int) -> dict[str, int]:
    """Quantos registros o BD tem de cada cadastro que o onboarding confere."""
    resultado = {}
    for chave, sql in _CONTAGENS.items():
        resultado[chave] = conexao.execute(sql, {"bd": bd_id}).fetchone()[0]
    return resultado


def dispensados(conexao: sqlite3.Connection, bd_id: int) -> set[str]:
    linhas = conexao.execute(
        "SELECT passo FROM onboarding_dispensa WHERE bd_id = :bd", {"bd": bd_id}
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
