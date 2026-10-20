"""Copia um `financeiro.db` (SQLite) para o schema Postgres do app. Uso único, do cutover da #68.

    uv run python scripts/sqlite_para_postgres.py ARQUIVO.db [--confirmar]

Lê `FINANCEIRO_DATABASE_URL` do ambiente, migra o esquema, copia as tabelas na ordem das chaves
estrangeiras, acerta as sequências e confere linha a linha (SQLite × Postgres). Sem `--confirmar`
faz tudo numa transação e desfaz no fim (ensaio). Não copia `sessao` nem `tentativa_login`:
são efêmeras (todo mundo entra de novo).
"""

import sqlite3
import sys
from pathlib import Path

import psycopg

from financeiro import config, store

# Efêmeras ou geridas pelo próprio app.
PULAR = {"sessao", "tentativa_login", "versao_esquema", "sqlite_sequence"}


def _tabelas(origem: sqlite3.Connection) -> list[str]:
    linhas = origem.execute(
        "SELECT name FROM sqlite_master"
        " WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [nome for (nome,) in linhas if nome not in PULAR]


def _dependencias(origem: sqlite3.Connection, tabela: str) -> set[str]:
    chaves = origem.execute(f"PRAGMA foreign_key_list({tabela})")
    return {linha[2] for linha in chaves if linha[2] != tabela}


def ordenar(origem: sqlite3.Connection) -> list[str]:
    """Tabelas com as referenciadas antes das que referenciam."""
    pendentes = {t: _dependencias(origem, t) & set(_tabelas(origem)) for t in _tabelas(origem)}
    ordem: list[str] = []
    while pendentes:
        prontas = sorted(t for t, deps in pendentes.items() if deps <= set(ordem))
        if not prontas:
            raise ValueError(f"ciclo de chaves estrangeiras entre {sorted(pendentes)}")
        ordem += prontas
        for t in prontas:
            del pendentes[t]
    return ordem


def _colunas_origem(origem: sqlite3.Connection, tabela: str) -> list[str]:
    return [linha[1] for linha in origem.execute(f"PRAGMA table_info({tabela})")]


def _colunas_destino(destino: psycopg.Connection, tabela: str) -> list[str]:
    linhas = destino.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position",
        (tabela,),
    )
    return [linha[0] for linha in linhas]


def _colunas_comuns(
    origem: sqlite3.Connection, destino: psycopg.Connection, tabela: str
) -> list[str]:
    no_destino = set(_colunas_destino(destino, tabela))
    return [c for c in _colunas_origem(origem, tabela) if c in no_destino]


def _autorreferencias(origem: sqlite3.Connection, tabela: str) -> list[str]:
    """Colunas que apontam para o `id` da própria tabela (ex.: org.pai_id).

    Numa chave composta como (bd_id, pai_id) → (bd_id, id), só `pai_id` conta: `bd_id` aponta para
    a coluna `bd_id` da mesma tabela, que nunca depende de outra linha.
    """
    return [
        linha[3]
        for linha in origem.execute(f"PRAGMA foreign_key_list({tabela})")
        if linha[2] == tabela and linha[4] == "id"
    ]


def _linhas_em_ordem(linhas: list[tuple], colunas: list[str], autorref: list[str]) -> list[tuple]:
    """Pais antes dos filhos nas tabelas que apontam para si mesmas."""
    if not autorref or "id" not in colunas:
        return linhas
    i_id = colunas.index("id")
    i_refs = [colunas.index(c) for c in autorref]
    ordenadas: list[tuple] = []
    presentes: set = set()
    restantes = list(linhas)
    while restantes:
        avancou = [r for r in restantes if all(r[i] is None or r[i] in presentes for i in i_refs)]
        if not avancou:
            raise ValueError("autorreferência sem raiz (ciclo)")
        ordenadas += avancou
        presentes |= {r[i_id] for r in avancou}
        restantes = [r for r in restantes if r not in avancou]
    return ordenadas


def copiar(origem: sqlite3.Connection, destino: psycopg.Connection) -> dict[str, int]:
    """Copia as tabelas e devolve as linhas copiadas por tabela."""
    copiadas: dict[str, int] = {}
    for tabela in ordenar(origem):
        colunas = _colunas_comuns(origem, destino, tabela)
        nomes = ", ".join(colunas)
        linhas = origem.execute(f"SELECT {nomes} FROM {tabela}").fetchall()
        autorref = [c for c in _autorreferencias(origem, tabela) if c in colunas]
        linhas = _linhas_em_ordem(linhas, colunas, autorref)
        if linhas:
            destino.cursor().executemany(
                f"INSERT INTO {tabela} ({nomes}) VALUES ({', '.join(['%s'] * len(colunas))})",
                linhas,
            )
        copiadas[tabela] = len(linhas)
    return copiadas


def acertar_sequencias(destino: psycopg.Connection) -> list[str]:
    """Depois de inserir com ids explícitos, o próximo id gerado tem de passar do maior copiado."""
    acertadas = []
    tabelas = destino.execute(
        "SELECT table_name FROM information_schema.columns"
        " WHERE table_schema = current_schema() AND column_name = 'id' AND is_identity = 'YES'"
    ).fetchall()
    for (tabela,) in tabelas:
        destino.execute(
            f"SELECT setval(pg_get_serial_sequence('{tabela}', 'id'),"
            f" COALESCE((SELECT MAX(id) FROM {tabela}), 1),"
            f" (SELECT MAX(id) FROM {tabela}) IS NOT NULL)"
        )
        acertadas.append(tabela)
    return acertadas


def conferir(origem: sqlite3.Connection, destino: psycopg.Connection) -> list[str]:
    """Compara, tabela a tabela, todas as linhas. Devolve as divergências (vazio = igual)."""
    problemas = []
    for tabela in ordenar(origem):
        colunas = _colunas_comuns(origem, destino, tabela)
        nomes = ", ".join(colunas)
        a = sorted(origem.execute(f"SELECT {nomes} FROM {tabela}").fetchall(), key=repr)
        b = sorted(destino.execute(f"SELECT {nomes} FROM {tabela}").fetchall(), key=repr)
        if a != b:
            problemas.append(
                f"{tabela}: origem {len(a)} linhas, destino {len(b)}, conteúdo diferente"
            )
    return problemas


def principal(argumentos: list[str]) -> int:
    if not argumentos or argumentos[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    arquivo, confirmar = Path(argumentos[0]), "--confirmar" in argumentos
    if not arquivo.is_file():
        print(f"arquivo não existe: {arquivo}", file=sys.stderr)
        return 2
    origem = sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True)
    destino = store.abrir(config.carregar().url_bd)
    try:
        store.migrar(destino, store.PASTA_MIGRACOES)
        if destino.execute("SELECT COUNT(*) FROM usuario").fetchone()[0]:
            print("o destino já tem dados: abortado, nada foi copiado", file=sys.stderr)
            return 1
        copiadas = copiar(origem, destino)
        acertar_sequencias(destino)
        problemas = conferir(origem, destino)
        for tabela, n in copiadas.items():
            print(f"  {tabela}: {n}")
        if problemas:
            destino.rollback()
            print("DIVERGÊNCIAS, desfeito:\n  " + "\n  ".join(problemas), file=sys.stderr)
            return 1
        if confirmar:
            destino.commit()
            print(f"OK: {sum(copiadas.values())} linhas copiadas e conferidas.")
        else:
            destino.rollback()
            total = sum(copiadas.values())
            print(f"ENSAIO OK: {total} linhas conferidas; desfeito (use --confirmar).")
        return 0
    finally:
        origem.close()
        destino.close()


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
