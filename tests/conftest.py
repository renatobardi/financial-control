import pytest

from financeiro import store
from tests.banco import URL_TESTE, schema_descartavel


@pytest.fixture
def schema_de_teste():
    with schema_descartavel() as nome:
        yield nome


@pytest.fixture
def conexao(schema_de_teste):
    """Conexão no schema do teste, com o esquema real migrado."""
    c = store.abrir(URL_TESTE, schema=schema_de_teste)
    store.migrar(c, store.PASTA_MIGRACOES)
    yield c
    c.close()


@pytest.fixture
def conexao_vazia(schema_de_teste):
    """Conexão num schema novo, sem nenhuma migração aplicada."""
    c = store.abrir(URL_TESTE, schema=schema_de_teste)
    yield c
    c.close()
