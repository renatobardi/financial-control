import os
from contextlib import contextmanager
from urllib.parse import quote
from uuid import uuid4

import psycopg
import pytest


@contextmanager
def recusa_do_banco(conexao):
    """O banco recusa o comando (violação de restrição) e a conexão segue usável.

    No Postgres a violação aborta a transação; sem o rollback o próximo comando também falharia.
    """
    with pytest.raises(psycopg.errors.IntegrityError):
        yield
    conexao.rollback()


# Postgres 17 só dos testes (superusuário, para criar schemas descartáveis). Local: `make db`.
URL_TESTE = os.environ.get(
    "FINANCEIRO_TESTE_URL_BD", "postgresql://postgres:teste@127.0.0.1:55439/postgres"
)


@contextmanager
def schema_descartavel():
    """Um schema só para o uso, derrubado ao final: nada vaza de um teste para o outro."""
    nome = f"t_{uuid4().hex[:12]}"
    admin = psycopg.connect(URL_TESTE, autocommit=True)
    admin.execute(f"CREATE SCHEMA {nome}")
    try:
        yield nome
    finally:
        admin.execute(f"DROP SCHEMA {nome} CASCADE")
        admin.close()


def url_do_schema(schema: str) -> str:
    """URL do Postgres de teste com o `search_path` no schema (o que a role do app tem em produção)."""
    return f"{URL_TESTE}?options={quote(f'-c search_path={schema}')}"
