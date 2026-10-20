from datetime import UTC, datetime

import pytest

from financeiro import cenarios, fechamento, forecast, orcamento, senha, visao_geral
from financeiro.store import acesso, cadastros, organizacao, pessoas, portfolio

AGORA = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)  # em abril: jan a mar já poderiam estar fechados


@pytest.fixture
def base(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    usuario = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", senha.gerar_hash("x"))
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "T", None, "G", "2025-01")
    squad = organizacao.criar_org(conexao, bd, "Squad", "S", tribo, "G", "2025-01")
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Sênior", "N9")
    cadastros.definir_tarifa(conexao, bd, cargo, 19300, "2026-01")
    cadastros.definir_markup(conexao, bd, 1000, "2026-01")
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    alfa = portfolio.criar_iniciativa(conexao, bd, "I-1", "Alfa")
    beta = portfolio.criar_iniciativa(conexao, bd, "I-2", "Beta")
    d_alfa = portfolio.criar_demanda(conexao, bd, "D-1", alfa, "Dem A", "CAPEX", squad)
    portfolio.criar_demanda(conexao, bd, "D-2", beta, "Dem B", "OPEX", squad)
    tema = portfolio.criar_tema(conexao, bd, "T-1", d_alfa, "Tema", agrup)
    pessoa = pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo, tema, "2025-01", None)
    for mes in (1, 2, 3):
        conexao.execute(
            "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (%s, %s, %s, %s, 100)",
            (bd, pessoa, tema, f"2026-{mes:02d}"),
        )
    conexao.commit()
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)
    fechamento.fechar(conexao, bd, "2026-02", usuario, AGORA)
    rev = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.definir_linha(conexao, bd, rev.id, alfa, "CAPEX", 12_000_000)
    orcamento.definir_linha(conexao, bd, rev.id, beta, "OPEX", 1_200_000)
    orcamento.aprovar(conexao, bd, rev.id, AGORA)
    cenario = cenarios.achar(conexao, bd, cenarios.criar(conexao, bd, "Base", 10000, 10000))
    return conexao, bd, cenario


def test_kpis_fecham_com_o_resumo_do_forecast(base):
    conexao, bd, cenario = base

    v = visao_geral.visao(conexao, bd, 2026, cenario, "bruto", AGORA)

    r = forecast.resumo(conexao, bd, 2026, cenario, "bruto", AGORA)
    assert (v.realizado, v.forecast, v.orcamento, v.gap) == (
        r.realizado, r.forecast, r.orcamento, r.gap,
    )  # fmt: skip
    assert v.total_ano == r.realizado + r.forecast


def test_curva_acumulada_termina_no_total_e_o_budget_e_linear(base):
    conexao, bd, cenario = base

    v = visao_geral.visao(conexao, bd, 2026, cenario, "bruto", AGORA)

    assert v.curva_budget[-1] == v.orcamento
    assert v.curva_budget[0] == v.orcamento // 12
    assert v.curva_realizado[1] == 2 * 100 * 21_230  # jan e fev fechados
    assert v.curva_realizado[2] is None  # março ainda aberto: não é realizado
    assert v.curva_forecast[-1] == v.total_ano  # acumulado do ano inteiro
    assert v.curva_forecast[0] is None


def test_top_iniciativas_em_risco_por_menor_saldo(base):
    conexao, bd, cenario = base

    v = visao_geral.visao(conexao, bd, 2026, cenario, "bruto", AGORA)

    nomes = [r.nome for r in v.risco]
    assert nomes[0] == "Alfa"  # gasta pessoas e tem o menor saldo
    alfa = v.risco[0]
    assert alfa.saldo == alfa.orcamento - (alfa.realizado + alfa.forecast)
    assert v.risco[-1].nome == "Beta" and v.risco[-1].saldo == 1_200_000


def test_composicao_do_gasto_soma_o_total_do_ano(base):
    conexao, bd, cenario = base

    v = visao_geral.visao(conexao, bd, 2026, cenario, "bruto", AGORA)

    assert sum(valor for _, valor in v.composicao) == v.total_ano


def test_alertas_avisam_mes_para_fechar_e_estouro(base):
    conexao, bd, cenario = base
    rev = orcamento.rascunho(conexao, bd)
    assert rev is None
    nova = orcamento.nova_revisao(conexao, bd, AGORA)
    alfa = portfolio.listar_iniciativas(conexao, bd)[0].id
    orcamento.definir_linha(conexao, bd, nova.id, alfa, "CAPEX", 1_000)  # estoura
    orcamento.aprovar(conexao, bd, nova.id, AGORA)

    v = visao_geral.visao(conexao, bd, 2026, cenario, "bruto", AGORA)

    chaves = [a.chave for a in v.alertas]
    assert "mes_para_fechar" in chaves  # março terminou e está aberto
    assert "iniciativa_estourada" in chaves
    estouro = next(a for a in v.alertas if a.chave == "iniciativa_estourada")
    assert estouro.params["nome"] == "Alfa"


def test_sem_orcamento_o_gap_e_o_risco_ficam_vazios(conexao):
    bd = acesso.criar_bd(conexao, "Sem PDD", "SP")
    cenario = cenarios.achar(conexao, bd, cenarios.criar(conexao, bd, "Base", 10000, 10000))

    v = visao_geral.visao(conexao, bd, 2026, cenario, "bruto", AGORA)

    assert v.orcamento is None and v.gap is None and v.risco == []
