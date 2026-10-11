import pytest

from financeiro import administracao, store
from financeiro.store import acesso


@pytest.fixture
def ana(conexao):
    return acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")


def test_usuario_cria_bd_e_vira_admin_so_dele(conexao, ana):
    outro_bd = acesso.criar_bd(conexao, "Mobility", "MO")
    bia = acesso.criar_usuario(conexao, "bia@empresa.com", "Bia", "h")
    acesso.adicionar_membro(conexao, outro_bd, bia, "Admin")

    bd = administracao.criar_bd_do_usuario(conexao, ana, "Crédito")

    assert acesso.papel_do(conexao, bd, ana) == "Admin"
    assert acesso.papel_do(conexao, outro_bd, ana) is None
    assert acesso.papel_do(conexao, bd, bia) is None
    novo = next(b for b in acesso.bds_do_usuario(conexao, ana) if b.id == bd)
    assert (novo.nome, novo.sigla, novo.papel) == ("Crédito", "CR", "Admin")


def test_nome_e_aparado_e_a_sigla_vai_em_maiuscula(conexao, ana):
    bd = administracao.criar_bd_do_usuario(conexao, ana, "  mobility  ")

    assert acesso.nome_do_bd(conexao, bd) == "mobility"
    assert acesso.bds_do_usuario(conexao, ana)[0].sigla == "MO"


@pytest.mark.parametrize("nome", ["", "   ", "x" * 61])
def test_nome_vazio_ou_longo_demais_e_recusado(conexao, ana, nome):
    with pytest.raises(administracao.NomeDeBdInvalido):
        administracao.criar_bd_do_usuario(conexao, ana, nome)

    assert acesso.bds_do_usuario(conexao, ana) == []


def test_nome_de_60_caracteres_e_aceito(conexao, ana):
    bd = administracao.criar_bd_do_usuario(conexao, ana, "x" * 60)

    assert acesso.papel_do(conexao, bd, ana) == "Admin"


def test_nome_repetido_e_recusado_sem_mudar_o_bd_existente(conexao, ana):
    existente = acesso.criar_bd(conexao, "Mobility", "MO")
    bia = acesso.criar_usuario(conexao, "bia@empresa.com", "Bia", "h")
    acesso.adicionar_membro(conexao, existente, bia, "Admin")

    with pytest.raises(administracao.NomeDeBdRepetido):
        administracao.criar_bd_do_usuario(conexao, ana, " Mobility ")

    assert acesso.papel_do(conexao, existente, ana) is None
    assert acesso.papel_do(conexao, existente, bia) == "Admin"


@pytest.mark.parametrize("nome", ["​", "Mo​bility", "Mo\x00bility", "Mo\nbility"])
def test_nome_com_caractere_invisivel_ou_de_controle_e_recusado(conexao, ana, nome):
    with pytest.raises(administracao.NomeDeBdInvalido):
        administracao.criar_bd_do_usuario(conexao, ana, nome)

    assert acesso.bds_do_usuario(conexao, ana) == []


def test_falha_ao_vincular_o_admin_nao_deixa_bd_orfao(conexao):
    with pytest.raises(store.ErroDeIntegridade):
        administracao.criar_bd_do_usuario(conexao, 9999, "Orfao")  # usuário inexistente

    assert acesso.achar_bd_por_nome(conexao, "Orfao") is None


def test_corrida_no_nome_vira_nome_repetido(conexao, ana, monkeypatch):
    acesso.criar_bd(conexao, "Mobility", "MO")
    monkeypatch.setattr(
        acesso, "achar_bd_por_nome", lambda *_: None
    )  # a outra criação chegou antes

    with pytest.raises(administracao.NomeDeBdRepetido):
        administracao.criar_bd_do_usuario(conexao, ana, "Mobility")
