from datetime import UTC, datetime

import pytest

from financeiro import fechamento, orcamento, realizado, senha
from financeiro.store import acesso, cadastros, organizacao, pessoas, portfolio

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def base(conexao):
    """Duas iniciativas. Jan: Ana 100 h no tema da Alfa (CAPEX) e compra de R$ 1.000 na Beta
    (OPEX). Fev: Ana 50 h. Jan fechado; fev aberto (forecast). R$ 193,00/h, markup 10%."""
    bd = acesso.criar_bd(conexao, "BD", "B")
    usuario = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", senha.gerar_hash("x"))
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "Tribo D&C", None, "G", "2025-01")
    squad = organizacao.criar_org(conexao, bd, "Squad", "Squad A", tribo, "G", "2025-01")
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Sênior", "N9")
    cadastros.definir_tarifa(conexao, bd, cargo, 19300, "2026-01")
    cadastros.definir_markup(conexao, bd, 1000, "2026-01")
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    alfa = portfolio.criar_iniciativa(conexao, bd, "I-01", "Alfa")
    beta = portfolio.criar_iniciativa(conexao, bd, "I-02", "Beta")
    d_alfa = portfolio.criar_demanda(conexao, bd, "D-1", alfa, "Dem Alfa", "CAPEX", squad)
    d_beta = portfolio.criar_demanda(conexao, bd, "D-2", beta, "Dem Beta", "OPEX", squad)
    tema = portfolio.criar_tema(conexao, bd, "T-1", d_alfa, "Tema", agrup)
    pessoa = pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo, tema, "2025-01", None)
    for mes, horas in (("2026-01", 100), ("2026-02", 50)):
        conexao.execute(
            "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (?, ?, ?, ?, ?)",
            (bd, pessoa, tema, mes, horas),
        )
    conexao.execute(
        "INSERT INTO compra (bd_id, numero, tipo, demanda_id, status) VALUES (?, 'OC1', 'OC', ?, 'emitida')",
        (bd, d_beta),
    )
    compra = conexao.execute("SELECT id FROM compra").fetchone()[0]
    conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (?, ?, '2026-01', 100000)",
        (bd, compra),
    )
    conexao.commit()
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)
    return conexao, bd, alfa, beta


def _linha(tabela, rotulo):
    return next(linha for linha in tabela.linhas if linha.rotulo == rotulo)


def test_realizado_so_de_mes_fechado_e_forecast_do_mes_aberto(base):
    conexao, bd, _, _ = base

    tabela = realizado.consultar(conexao, bd, 2026, "iniciativa", "todas", "bruto", AGORA)

    alfa = _linha(tabela, "Alfa")
    assert alfa.meses[0] == 2_123_000  # jan fechado: 100 h × R$ 193,00 × 1,10
    assert alfa.meses[1] is None  # fev aberto: não é realizado
    assert alfa.realizado == 2_123_000
    assert alfa.forecast == 50 * 21_230  # fev: 50 h, ainda forecast
    assert alfa.total_ano == alfa.realizado + alfa.forecast


def test_agrupa_por_tipo_e_por_origem(base):
    conexao, bd, _, _ = base

    por_tipo = realizado.consultar(conexao, bd, 2026, "tipo", "todas", "bruto", AGORA)
    por_origem = realizado.consultar(conexao, bd, 2026, "origem", "todas", "bruto", AGORA)

    assert _linha(por_tipo, "CAPEX").realizado == 2_123_000
    assert _linha(por_tipo, "OPEX").realizado == 110_000
    assert _linha(por_origem, "Pessoas").realizado == 2_123_000
    assert _linha(por_origem, "Compras").realizado == 110_000


def test_base_liquida_usa_o_valor_liquido(base):
    conexao, bd, _, _ = base

    tabela = realizado.consultar(conexao, bd, 2026, "origem", "todas", "liquido", AGORA)

    assert _linha(tabela, "Pessoas").realizado == 1_930_000  # 100 h × R$ 193,00
    assert _linha(tabela, "Compras").realizado == 100_000


def test_filtro_de_origem_mostra_so_a_origem_e_a_nota_diz_o_que_ficou_de_fora(base):
    conexao, bd, _, _ = base

    tabela = realizado.consultar(conexao, bd, 2026, "iniciativa", "pessoas", "bruto", AGORA)

    assert _linha(tabela, "Alfa").realizado == 2_123_000
    assert all(linha.realizado == 0 for linha in tabela.linhas if linha.rotulo == "Beta")
    assert tabela.nota is not None and "R$ 1.100,00" in tabela.nota


def test_sem_filtro_a_soma_da_tabela_fecha_com_o_total_do_fechamento(base):
    conexao, bd, _, _ = base

    tabela = realizado.consultar(conexao, bd, 2026, "iniciativa", "todas", "bruto", AGORA)

    total_fechamento = fechamento.totais_do_mes(conexao, bd, "2026-01").total_centavos
    assert sum(linha.meses[0] or 0 for linha in tabela.linhas) == total_fechamento
    assert tabela.nota is None


def test_gap_com_sinal_unico_positivo_saldo_e_negativo_estouro(base):
    conexao, bd, alfa, beta = base
    rev = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.definir_linha(conexao, bd, rev.id, alfa, "CAPEX", 4_000_000)  # total ano 3.184.500
    orcamento.definir_linha(conexao, bd, rev.id, beta, "OPEX", 100_000)  # total ano 110.000
    orcamento.aprovar(conexao, bd, rev.id, AGORA)

    tabela = realizado.consultar(conexao, bd, 2026, "iniciativa", "todas", "bruto", AGORA)

    a, b = _linha(tabela, "Alfa"), _linha(tabela, "Beta")
    assert a.total_ano == 3_184_500
    assert a.orcamento == 4_000_000 and a.gap == 815_500  # saldo: positivo
    assert b.orcamento == 100_000 and b.gap == -10_000  # estouro: negativo
    assert a.gap == orcamento.gap(a.orcamento, a.total_ano)


def test_iniciativa_so_com_orcamento_aparece_na_tabela(base):
    conexao, bd, _, _ = base
    gama = portfolio.criar_iniciativa(conexao, bd, "I-03", "Gama")
    rev = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.definir_linha(conexao, bd, rev.id, gama, "CAPEX", 500_000)
    orcamento.aprovar(conexao, bd, rev.id, AGORA)

    tabela = realizado.consultar(conexao, bd, 2026, "iniciativa", "todas", "bruto", AGORA)

    g = _linha(tabela, "Gama")
    assert (g.realizado, g.forecast, g.orcamento, g.gap) == (0, 0, 500_000, 500_000)


def test_lancamento_sem_classificacao_vai_para_a_linha_sem_agrupamento(base):
    conexao, bd, _, _ = base

    tabela = realizado.consultar(conexao, bd, 2026, "agrupamento", "todas", "bruto", AGORA)

    assert _linha(tabela, "RTB").realizado == 2_123_000
    assert _linha(tabela, "Sem agrupamento").realizado == 110_000  # a compra não tem tema


def test_dimensao_desconhecida_e_recusada(base):
    conexao, bd, _, _ = base

    with pytest.raises(ValueError):
        realizado.consultar(conexao, bd, 2026, "cor", "todas", "bruto", AGORA)


def test_total_da_tabela_nao_inclui_outro_bd(base):
    conexao, bd, _, _ = base
    outro = acesso.criar_bd(conexao, "Outro", "OT")

    tabela = realizado.consultar(conexao, outro, 2026, "iniciativa", "todas", "bruto", AGORA)

    assert tabela.linhas == []
