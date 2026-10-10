import sqlite3

import pytest

from financeiro.store import acesso, portfolio


@pytest.fixture
def bd(conexao):
    return acesso.criar_bd(conexao, "BD", "B")


def test_iniciativa_demanda_tema_com_agrupamento(conexao, bd):
    agrup = portfolio.criar_agrupamento(conexao, bd, "Regulatório")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-01", "Plataforma de decisão")
    dem = portfolio.criar_demanda(conexao, bd, "D-101", ini, "Motor de regras", "CAPEX", None)
    portfolio.criar_tema(conexao, bd, "T-10", dem, "Regras de crédito", agrup)

    temas = portfolio.listar_temas(conexao, bd)

    assert [(t.codigo, t.demanda, t.iniciativa, t.tipo, t.agrupamento) for t in temas] == [
        ("T-10", "Motor de regras", "Plataforma de decisão", "CAPEX", "Regulatório")
    ]


def test_demanda_so_aceita_capex_ou_opex(conexao, bd):
    ini = portfolio.criar_iniciativa(conexao, bd, "I-01", "Plataforma")

    with pytest.raises(sqlite3.IntegrityError):
        portfolio.criar_demanda(conexao, bd, "D-1", ini, "X", "INFRA", None)


def test_codigo_repetido_no_bd_e_recusado_mas_vale_em_outro_bd(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    portfolio.criar_iniciativa(conexao, bd, "I-01", "A")

    with pytest.raises(sqlite3.IntegrityError):
        portfolio.criar_iniciativa(conexao, bd, "I-01", "B")
    portfolio.criar_iniciativa(conexao, outro, "I-01", "C")


def test_tema_nao_liga_a_demanda_de_outro_bd(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    ini = portfolio.criar_iniciativa(conexao, outro, "I-01", "A")
    dem = portfolio.criar_demanda(conexao, outro, "D-1", ini, "X", "OPEX", None)
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")

    with pytest.raises(sqlite3.IntegrityError):
        portfolio.criar_tema(conexao, bd, "T-1", dem, "Y", agrup)


def test_fornecedor_unico_por_bd(conexao, bd):
    portfolio.criar_fornecedor(conexao, bd, "Fornecedor A")

    with pytest.raises(sqlite3.IntegrityError):
        portfolio.criar_fornecedor(conexao, bd, "Fornecedor A")
    assert [f.nome for f in portfolio.listar_fornecedores(conexao, bd)] == ["Fornecedor A"]
