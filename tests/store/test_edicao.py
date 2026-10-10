import pytest

from financeiro.store import acesso, cadastros, edicao, portfolio


@pytest.fixture
def bd(conexao):
    return acesso.criar_bd(conexao, "BD", "B")


def test_renomear_altera_so_o_registro_do_bd_informado(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    a = portfolio.criar_iniciativa(conexao, bd, "I-01", "Antigo")
    b = portfolio.criar_iniciativa(conexao, outro, "I-01", "Antigo")

    edicao.renomear(conexao, "iniciativa", bd, a, "Novo")

    assert portfolio.listar_iniciativas(conexao, bd)[0].nome == "Novo"
    assert portfolio.listar_iniciativas(conexao, outro)[0].nome == "Antigo"
    assert b


@pytest.mark.parametrize(
    "tabela", ["empresa", "cargo", "iniciativa", "demanda", "tema", "agrupamento", "fornecedor"]
)
def test_tabelas_renomeaveis(tabela):
    assert tabela in edicao.RENOMEAVEIS


def test_tabela_fora_da_lista_e_recusada(conexao, bd):
    with pytest.raises(ValueError):
        edicao.renomear(conexao, "usuario", bd, 1, "x")


def test_alterar_nivel_do_cargo(conexao, bd):
    empresa = cadastros.criar_empresa(conexao, bd, "NTT", "consultoria")
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Dev", "N8")

    edicao.alterar_nivel_cargo(conexao, bd, cargo, "N9")

    assert cadastros.achar_cargo(conexao, bd, cargo).nivel == "N9"
