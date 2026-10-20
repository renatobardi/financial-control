import threading
from decimal import Decimal

import psycopg
import pytest

from financeiro import store
from tests.banco import URL_TESTE


def test_abrir_fixa_o_schema_e_liga_as_chaves_estrangeiras(conexao, schema_de_teste):
    assert conexao.execute("SELECT current_schema()").fetchone()[0] == schema_de_teste
    conexao.execute("CREATE TABLE pai (id BIGINT PRIMARY KEY)")
    conexao.execute("CREATE TABLE filho (pai_id BIGINT NOT NULL REFERENCES pai (id))")

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conexao.execute("INSERT INTO filho (pai_id) VALUES (1)")


def test_soma_de_inteiros_volta_como_int_e_nao_como_decimal(conexao):
    conexao.execute("CREATE TABLE valor (centavos BIGINT NOT NULL)")
    grande = 3_000_000_000  # acima de 2^31: o INTEGER do Postgres não guardaria
    conexao.execute("INSERT INTO valor VALUES (%s), (%s)", (grande, grande))

    soma = conexao.execute("SELECT SUM(centavos) FROM valor").fetchone()[0]

    assert soma == 2 * grande
    assert type(soma) is int


def test_numerico_fracionario_continua_decimal(conexao):
    valor = conexao.execute("SELECT 1.5::numeric").fetchone()[0]

    assert valor == Decimal("1.5")


def test_pool_empresta_conexao_por_thread_e_devolve(schema_de_teste):
    pool = store.criar_pool(URL_TESTE, schema=schema_de_teste)
    pool.open()
    try:
        resultados = []

        def usar():
            with pool.connection() as conexao:
                resultados.append(conexao.execute("SELECT current_schema()").fetchone()[0])

        fios = [threading.Thread(target=usar) for _ in range(8)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join()
    finally:
        pool.close()

    assert resultados == [schema_de_teste] * 8
