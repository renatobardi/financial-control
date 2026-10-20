from fastapi.testclient import TestClient

from financeiro import config, store
from financeiro.web.app import criar_app
from tests.banco import url_do_schema


def test_healthz_informa_commit_e_versao_do_esquema(schema_de_teste):
    cfg = config.carregar(
        {"FINANCEIRO_DATABASE_URL": url_do_schema(schema_de_teste), "FINANCEIRO_COMMIT": "abc1234"}
    )

    with TestClient(criar_app(cfg)) as cliente:
        resposta = cliente.get("/healthz")

    assert resposta.status_code == 200
    migracoes = len(list(store.PASTA_MIGRACOES.glob("*.sql")))
    assert resposta.json() == {"commit": "abc1234", "esquema": migracoes}
