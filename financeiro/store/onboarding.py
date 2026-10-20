import psycopg

# Cada contagem conta registros do BD; a chave é a que `financeiro.onboarding` usa.
_CONTAGENS = {
    "squad": "SELECT COUNT(*) FROM org WHERE bd_id = %(bd)s AND tipo = 'Squad'",
    "iniciativa": "SELECT COUNT(*) FROM iniciativa WHERE bd_id = %(bd)s",
    "demanda": "SELECT COUNT(*) FROM demanda WHERE bd_id = %(bd)s",
    "agrupamento": "SELECT COUNT(*) FROM agrupamento WHERE bd_id = %(bd)s",
    "tema": "SELECT COUNT(*) FROM tema WHERE bd_id = %(bd)s",
    "cargo": "SELECT COUNT(*) FROM cargo WHERE bd_id = %(bd)s",
    "tarifa": "SELECT COUNT(*) FROM tarifa WHERE bd_id = %(bd)s",
    "markup": "SELECT COUNT(*) FROM markup WHERE bd_id = %(bd)s",
    "pessoa": "SELECT COUNT(*) FROM pessoa WHERE bd_id = %(bd)s",
    "revisao": "SELECT COUNT(*) FROM pdd_revisao WHERE bd_id = %(bd)s",
    "compra": "SELECT COUNT(*) FROM compra WHERE bd_id = %(bd)s",
    "calendario": (
        "SELECT (SELECT COUNT(*) FROM calendario_mes WHERE bd_id = %(bd)s)"
        " + (SELECT COUNT(*) FROM feriado_bd WHERE bd_id = %(bd)s)"
    ),
}


# Registros que falta completar, um nome por linha. Só quem tem filho a menos entra.
_PENDENCIAS = {
    "tribo_sem_squad": (
        "SELECT t.nome FROM org t WHERE t.bd_id = %(bd)s AND t.tipo = 'Tribo'"
        " AND NOT EXISTS (SELECT 1 FROM org s WHERE s.bd_id = t.bd_id AND s.pai_id = t.id"
        " AND s.tipo = 'Squad') ORDER BY t.nome"
    ),
    "iniciativa_sem_demanda": (
        "SELECT i.codigo || ' ' || i.nome FROM iniciativa i WHERE i.bd_id = %(bd)s"
        " AND NOT EXISTS (SELECT 1 FROM demanda d WHERE d.bd_id = i.bd_id"
        " AND d.iniciativa_id = i.id) ORDER BY i.codigo"
    ),
    "demanda_sem_tema": (
        "SELECT d.codigo || ' ' || d.nome FROM demanda d WHERE d.bd_id = %(bd)s"
        " AND NOT EXISTS (SELECT 1 FROM tema t WHERE t.bd_id = d.bd_id"
        " AND t.demanda_id = d.id) ORDER BY d.codigo"
    ),
    "cargo_sem_tarifa": (
        "SELECT c.nome || ' (' || e.nome || ')' FROM cargo c"
        " JOIN empresa e ON e.bd_id = c.bd_id AND e.id = c.empresa_id"
        " WHERE c.bd_id = %(bd)s AND NOT EXISTS (SELECT 1 FROM tarifa t WHERE t.bd_id = c.bd_id"
        " AND t.cargo_id = c.id) ORDER BY e.nome, c.nome"
    ),
}


def pendencias(conexao: psycopg.Connection, bd_id: int) -> dict[str, tuple[str, ...]]:
    """Os registros do BD a que falta o filho que a regra de completude pede."""
    return {
        chave: tuple(nome for (nome,) in conexao.execute(sql, {"bd": bd_id}))
        for chave, sql in _PENDENCIAS.items()
    }


def contagens(conexao: psycopg.Connection, bd_id: int) -> dict[str, int]:
    """Quantos registros o BD tem de cada cadastro que o onboarding confere."""
    resultado = {}
    for chave, sql in _CONTAGENS.items():
        resultado[chave] = conexao.execute(sql, {"bd": bd_id}).fetchone()[0]
    return resultado


def dispensados(conexao: psycopg.Connection, bd_id: int) -> set[str]:
    linhas = conexao.execute(
        "SELECT passo FROM onboarding_dispensa WHERE bd_id = %(bd)s", {"bd": bd_id}
    ).fetchall()
    return {passo for (passo,) in linhas}


def dispensar(conexao: psycopg.Connection, bd_id: int, passo: str) -> None:
    conexao.execute(
        "INSERT INTO onboarding_dispensa (bd_id, passo) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (bd_id, passo),
    )
    conexao.commit()


def desfazer_dispensa(conexao: psycopg.Connection, bd_id: int, passo: str) -> None:
    conexao.execute(
        "DELETE FROM onboarding_dispensa WHERE bd_id = %s AND passo = %s", (bd_id, passo)
    )
    conexao.commit()


def marcar_aberto(conexao: psycopg.Connection, bd_id: int) -> bool:
    """Marca o BD como já aberto. Devolve True só para quem fez a marca (atômico)."""
    cursor = conexao.execute(
        "UPDATE bd SET onboarding_aberto = 1 WHERE id = %s AND onboarding_aberto = 0", (bd_id,)
    )
    conexao.commit()
    return cursor.rowcount == 1
