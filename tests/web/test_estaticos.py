from fastapi.testclient import TestClient

from financeiro import config
from financeiro.web.app import criar_app


def test_serve_a_fonte_inter_self_hosted(tmp_path):
    cfg = config.carregar({"FINANCEIRO_BD": str(tmp_path / "f.db")})

    with TestClient(criar_app(cfg)) as cliente:
        resposta = cliente.get("/static/fonts/InterVariable.woff2")

    assert resposta.status_code == 200
    assert resposta.content[:4] == b"wOF2"
