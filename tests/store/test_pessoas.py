import pytest

from financeiro.store import acesso, cadastros, organizacao, pessoas, portfolio
from tests.banco import recusa_do_banco


@pytest.fixture
def base(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "Tribo", None, "G", "2025-01")
    squad = organizacao.criar_org(conexao, bd, "Squad", "Squad", tribo, "G", "2025-01")
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Sênior", "N9")
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-01", "Ini")
    dem = portfolio.criar_demanda(conexao, bd, "D-1", ini, "Dem", "OPEX", squad)
    tema = portfolio.criar_tema(conexao, bd, "T-1", dem, "Tema", agrup)
    return conexao, bd, squad, cargo, tema


def test_pessoa_com_matricula_organizacao_cargo_e_tema(base):
    conexao, bd, squad, cargo, tema = base

    pessoa = pessoas.criar_pessoa(
        conexao, bd, "F0101", "Ana Lima", squad, cargo, tema, "2025-01", None
    )

    achada = pessoas.achar_pessoa(conexao, bd, pessoa)
    assert (achada.matricula, achada.nome, achada.org, achada.cargo, achada.tema) == (
        "F0101",
        "Ana Lima",
        "Squad",
        "Sênior",
        "T-1",
    )


def test_matricula_repetida_no_bd_e_recusada(base):
    conexao, bd, squad, cargo, tema = base
    pessoas.criar_pessoa(conexao, bd, "F0101", "Ana", squad, cargo, tema, "2025-01", None)

    with recusa_do_banco(conexao):
        pessoas.criar_pessoa(conexao, bd, "F0101", "Outra", squad, cargo, tema, "2025-02", None)


def test_desligamento_antes_da_admissao_e_recusado(base):
    conexao, bd, squad, cargo, tema = base

    with recusa_do_banco(conexao):
        pessoas.criar_pessoa(conexao, bd, "F0101", "Ana", squad, cargo, tema, "2025-06", "2025-05")


def test_pessoa_nao_liga_a_cargo_de_outro_bd(base):
    conexao, bd, squad, _, tema = base
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    empresa = cadastros.criar_empresa(conexao, outro, "NTT", "consultoria")
    cargo_outro = cadastros.criar_cargo(conexao, outro, empresa, "Dev", "N8")

    with recusa_do_banco(conexao):
        pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo_outro, tema, "2025-01", None)


def test_vaga_abre_preenche_e_cancela(base):
    conexao, bd, squad, cargo, tema = base
    pessoa = pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo, tema, "2026-09", None)
    v1 = pessoas.abrir_vaga(conexao, bd, "V-01", squad, tema, cargo, "2026-08")
    v2 = pessoas.abrir_vaga(conexao, bd, "V-02", squad, tema, cargo, "2026-08")

    pessoas.preencher_vaga(conexao, bd, v1, pessoa)
    pessoas.cancelar_vaga(conexao, bd, v2)

    estados = {v.codigo: (v.estado, v.pessoa_id) for v in pessoas.listar_vagas(conexao, bd)}
    assert estados == {"V-01": ("preenchida", pessoa), "V-02": ("cancelada", None)}


def test_vaga_que_nao_esta_aberta_nao_muda(base):
    conexao, bd, squad, cargo, tema = base
    pessoa = pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo, tema, "2026-09", None)
    vaga = pessoas.abrir_vaga(conexao, bd, "V-01", squad, tema, cargo, "2026-08")
    pessoas.cancelar_vaga(conexao, bd, vaga)

    with pytest.raises(pessoas.VagaNaoAberta):
        pessoas.preencher_vaga(conexao, bd, vaga, pessoa)
    with pytest.raises(pessoas.VagaNaoAberta):
        pessoas.cancelar_vaga(conexao, bd, vaga)


def test_vaga_nao_e_preenchida_por_pessoa_de_outro_bd(base):
    conexao, bd, squad, cargo, tema = base
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    org = organizacao.criar_org(conexao, outro, "Tribo", "T", None, "G", "2025-01")
    empresa = cadastros.criar_empresa(conexao, outro, "X", "propria")
    cargo_o = cadastros.criar_cargo(conexao, outro, empresa, "Dev", "N8")
    agrup = portfolio.criar_agrupamento(conexao, outro, "A")
    ini = portfolio.criar_iniciativa(conexao, outro, "I-1", "I")
    dem = portfolio.criar_demanda(conexao, outro, "D-1", ini, "D", "OPEX", None)
    tema_o = portfolio.criar_tema(conexao, outro, "T-1", dem, "T", agrup)
    pessoa_outro = pessoas.criar_pessoa(
        conexao, outro, "X1", "Zé", org, cargo_o, tema_o, "2025-01", None
    )
    vaga = pessoas.abrir_vaga(conexao, bd, "V-01", squad, tema, cargo, "2026-08")

    with pytest.raises(pessoas.VagaNaoAberta):
        pessoas.preencher_vaga(conexao, bd, vaga, pessoa_outro)
    assert pessoas.listar_vagas(conexao, bd)[0].estado == "aberta"
