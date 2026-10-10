from pathlib import Path

from financeiro import config


def test_padroes_sem_ambiente():
    cfg = config.carregar({})

    assert cfg.caminho_bd == Path("dados/financeiro.db")
    assert cfg.commit == "desconhecido"


def test_le_do_ambiente_recebido():
    cfg = config.carregar({"FINANCEIRO_BD": "/var/lib/fin/f.db", "FINANCEIRO_COMMIT": "abc1234"})

    assert cfg.caminho_bd == Path("/var/lib/fin/f.db")
    assert cfg.commit == "abc1234"


def test_sessao_e_login_tem_padrao_seguro():
    cfg = config.carregar({})

    assert cfg.segredo is None
    assert cfg.cookie_seguro is True
    assert cfg.max_tentativas == 5


def test_le_segredo_cookie_e_limite_do_ambiente():
    cfg = config.carregar(
        {
            "FINANCEIRO_SEGREDO": "s3gr3d0",
            "FINANCEIRO_COOKIE_SEGURO": "0",
            "FINANCEIRO_MAX_TENTATIVAS": "3",
        }
    )

    assert cfg.segredo == b"s3gr3d0"
    assert cfg.cookie_seguro is False
    assert cfg.max_tentativas == 3
