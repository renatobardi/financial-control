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
