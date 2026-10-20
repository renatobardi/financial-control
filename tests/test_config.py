from financeiro import config


def test_padroes_sem_ambiente():
    cfg = config.carregar({})

    assert cfg.url_bd == config.URL_BD_PADRAO
    assert cfg.commit == "desconhecido"


def test_le_do_ambiente_recebido():
    cfg = config.carregar(
        {"FINANCEIRO_DATABASE_URL": "postgresql://app@db/x", "FINANCEIRO_COMMIT": "abc1234"}
    )

    assert cfg.url_bd == "postgresql://app@db/x"
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


def test_url_do_banco_nao_aparece_no_repr():
    cfg = config.carregar({"FINANCEIRO_DATABASE_URL": "postgresql://app:senha-secreta@db/x"})

    assert "senha-secreta" not in repr(cfg)
