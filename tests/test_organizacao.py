import pytest

from financeiro import organizacao
from financeiro.store import acesso


@pytest.fixture
def bd(conexao):
    return acesso.criar_bd(conexao, "BD Mobility", "BM")


def test_arvore_bd_tribo_squad(conexao, bd):
    dc = organizacao.criar_tribo(conexao, bd, "Tribo D&C", "Renato", "2025-01")
    organizacao.criar_squad(conexao, bd, "Squad Engines", dc, "Gestora A", "2025-03")
    organizacao.criar_squad(conexao, bd, "Squad Core", dc, "Gestor B", "2025-01")

    arvore = organizacao.arvore(conexao, bd)

    assert [(t.nome, [s.nome for s in t.squads]) for t in arvore] == [
        ("Tribo D&C", ["Squad Engines", "Squad Core"])
    ]


def test_squad_exige_uma_tribo_do_mesmo_bd(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    tribo_outro = organizacao.criar_tribo(conexao, outro, "Tribo X", "G", "2025-01")
    dc = organizacao.criar_tribo(conexao, bd, "Tribo D&C", "G", "2025-01")
    squad = organizacao.criar_squad(conexao, bd, "Squad A", dc, "G", "2025-01")

    with pytest.raises(organizacao.OrganizacaoInvalida):
        organizacao.criar_squad(conexao, bd, "Squad B", tribo_outro, "G", "2025-01")
    with pytest.raises(organizacao.OrganizacaoInvalida):
        organizacao.criar_squad(conexao, bd, "Squad C", squad, "G", "2025-01")


def test_reorganizar_squad_muda_a_tribo_e_deixa_historico(conexao, bd):
    dc = organizacao.criar_tribo(conexao, bd, "Tribo D&C", "G", "2025-01")
    pay = organizacao.criar_tribo(conexao, bd, "Tribo Payments", "G", "2025-01")
    squad = organizacao.criar_squad(conexao, bd, "Squad Risk", pay, "G", "2025-01")

    organizacao.reorganizar(conexao, bd, squad, dc, "2026-07")

    arvore = {t.nome: [s.nome for s in t.squads] for t in organizacao.arvore(conexao, bd)}
    assert arvore == {"Tribo D&C": ["Squad Risk"], "Tribo Payments": []}
    assert organizacao.historico(conexao, bd, squad) == [
        ("2026-07", "reorganização: veio de Tribo Payments para Tribo D&C")
    ]


def test_so_squad_e_reorganizado_e_nao_para_a_mesma_tribo(conexao, bd):
    dc = organizacao.criar_tribo(conexao, bd, "Tribo D&C", "G", "2025-01")
    squad = organizacao.criar_squad(conexao, bd, "Squad A", dc, "G", "2025-01")

    with pytest.raises(organizacao.OrganizacaoInvalida):
        organizacao.reorganizar(conexao, bd, dc, dc, "2026-07")
    with pytest.raises(organizacao.OrganizacaoInvalida):
        organizacao.reorganizar(conexao, bd, squad, dc, "2026-07")


def test_trocar_gestor_registra_no_historico(conexao, bd):
    dc = organizacao.criar_tribo(conexao, bd, "Tribo D&C", "Renato", "2025-01")

    organizacao.trocar_gestor(conexao, bd, dc, "Marina", "2026-08")

    assert organizacao.arvore(conexao, bd)[0].gestor == "Marina"
    assert organizacao.historico(conexao, bd, dc) == [("2026-08", "gestor: Renato para Marina")]


def test_nome_repetido_no_bd_e_recusado(conexao, bd):
    organizacao.criar_tribo(conexao, bd, "Tribo D&C", "G", "2025-01")

    with pytest.raises(organizacao.OrganizacaoInvalida):
        organizacao.criar_tribo(conexao, bd, "Tribo D&C", "G", "2025-01")


def test_org_de_outro_bd_nao_e_mexida(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    tribo = organizacao.criar_tribo(conexao, outro, "Tribo X", "G", "2025-01")

    with pytest.raises(organizacao.OrganizacaoInvalida):
        organizacao.trocar_gestor(conexao, bd, tribo, "Invasor", "2026-08")
    assert organizacao.arvore(conexao, outro)[0].gestor == "G"
