from fastapi.testclient import TestClient

from financeiro import config
from financeiro.web.app import criar_app
from tests.banco import url_do_schema


def test_serve_a_fonte_inter_self_hosted(schema_de_teste):
    cfg = config.carregar({"FINANCEIRO_DATABASE_URL": url_do_schema(schema_de_teste)})

    with TestClient(criar_app(cfg)) as cliente:
        resposta = cliente.get("/static/fonts/InterVariable.woff2")

    assert resposta.status_code == 200
    assert resposta.content[:4] == b"wOF2"
