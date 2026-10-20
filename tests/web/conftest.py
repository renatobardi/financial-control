from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from financeiro import config, store
from financeiro.web.app import criar_app
from tests.banco import URL_TESTE, url_do_schema


class Relogio:
    """Relógio de teste: fixo até alguém avançar."""

    def __init__(self):
        self.agora = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, **delta) -> None:
        self.agora += timedelta(**delta)


@pytest.fixture
def ambiente(schema_de_teste):
    cfg = config.carregar(
        {
            "FINANCEIRO_DATABASE_URL": url_do_schema(schema_de_teste),
            "FINANCEIRO_SEGREDO": "segredo-de-teste",
            "FINANCEIRO_MAX_TENTATIVAS": "3",
        }
    )
    relogio = Relogio()
    app = criar_app(cfg, agora=relogio)
    with TestClient(app, base_url="https://testserver", follow_redirects=False) as cliente:
        conexao = store.abrir(URL_TESTE, schema=schema_de_teste)
        yield SimpleNamespace(cliente=cliente, cfg=cfg, relogio=relogio, conexao=conexao)
        conexao.close()
