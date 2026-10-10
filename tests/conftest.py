import pytest

from financeiro import store


@pytest.fixture
def conexao():
    """Banco em memória com o esquema real migrado."""
    c = store.abrir(":memory:")
    store.migrar(c, store.PASTA_MIGRACOES)
    return c
