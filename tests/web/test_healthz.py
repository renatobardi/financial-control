from fastapi.testclient import TestClient

from financeiro import config
from financeiro.web.app import criar_app


def test_healthz_informa_commit_e_versao_do_esquema(tmp_path):
    cfg = config.carregar({"FINANCEIRO_BD": str(tmp_path / "f.db"), "FINANCEIRO_COMMIT": "abc1234"})

    with TestClient(criar_app(cfg)) as cliente:
        resposta = cliente.get("/healthz")

    assert resposta.status_code == 200
    assert resposta.json() == {"commit": "abc1234", "esquema": 0}
