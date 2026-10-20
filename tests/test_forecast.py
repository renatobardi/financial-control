from datetime import UTC, datetime

import pytest

from financeiro import cenarios, fechamento, forecast, orcamento, senha
from financeiro.store import acesso, cadastros, organizacao, pessoas, portfolio

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def base(conexao):
    """Ana (R$ 193,00/h, 10%) com 100 h em jan (fechado) e 50 h em fev; Bia ativa sem
    lançamento; uma vaga aberta; uma compra de R$ 1.000 em fev. Capacidade: 168 h/mês."""
    bd = acesso.criar_bd(conexao, "BD", "B")
    usuario = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", senha.gerar_hash("x"))
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "Tribo", None, "G", "2025-01")
    squad = organizacao.criar_org(conexao, bd, "Squad", "Squad", tribo, "G", "2025-01")
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Sênior", "N9")
    cadastros.definir_tarifa(conexao, bd, cargo, 19300, "2026-01")
    cadastros.definir_markup(conexao, bd, 1000, "2026-01")
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-1", "Alfa")
    dem = portfolio.criar_demanda(conexao, bd, "D-1", ini, "Dem", "CAPEX", squad)
    tema = portfolio.criar_tema(conexao, bd, "T-1", dem, "Tema", agrup)
    ana = pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo, tema, "2025-01", None)
    pessoas.criar_pessoa(conexao, bd, "F2", "Bia", squad, cargo, tema, "2026-03", "2026-03")
    vaga = pessoas.abrir_vaga(conexao, bd, "V-1", squad, tema, cargo, "2026-01")
    for mes, horas in (("2026-01", 100), ("2026-02", 50)):
        conexao.execute(
            "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (%s, %s, %s, %s, %s)",
            (bd, ana, tema, mes, horas),
        )
    conexao.execute(
        "INSERT INTO compra (bd_id, numero, tipo, demanda_id, status) VALUES (%s, 'OC1', 'OC', %s, 'emitida')",
        (bd, dem),
    )
    compra = conexao.execute("SELECT id FROM compra").fetchone()[0]
    conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (%s, %s, '2026-02', 100000)",
        (bd, compra),
    )
    conexao.commit()
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)
    return conexao, bd, ini, vaga, usuario


def _mes(atomos, mes, origem):
    return sum(a.valor_centavos for a in atomos if a.mes == mes and a.origem == origem)


def test_cenario_padrao_cria_base_otimista_e_pessimista(base):
    conexao, bd, *_ = base

    cenarios.garantir_padrao(conexao, bd)

    assert [(c.nome, c.fator_pessoas, c.fator_compras) for c in cenarios.listar(conexao, bd)] == [
        ("Base", 10000, 10000),
        ("Otimista", 9700, 9000),
        ("Pessimista", 10500, 11500),
    ]


def test_limite_de_20_cenarios_por_bd(base):
    conexao, bd, *_ = base
    for i in range(20):
        cenarios.criar(conexao, bd, f"C{i}", 10000, 10000)

    with pytest.raises(cenarios.CenarioInvalido):
        cenarios.criar(conexao, bd, "C21", 10000, 10000)


def test_realizado_de_mes_fechado_nao_recebe_fator(base):
    conexao, bd, *_ = base
    pess = cenarios.criar(conexao, bd, "Pessimista", 10500, 11500)
    c = cenarios.achar(conexao, bd, pess)

    atomos = forecast.atomos(conexao, bd, 2026, c, AGORA)

    jan = [a for a in atomos if a.mes == "2026-01"]
    assert all(a.realizado for a in jan)
    assert _mes(atomos, "2026-01", "pessoas") == 100 * 21_230  # sem fator


def test_forecast_de_mes_aberto_aplica_o_fator_do_cenario(base):
    conexao, bd, *_ = base
    pess = cenarios.criar(conexao, bd, "Pessimista", 10500, 11500)
    c = cenarios.achar(conexao, bd, pess)

    atomos = forecast.atomos(conexao, bd, 2026, c, AGORA)

    fev_pessoas = 50 * 21_230  # 50 h lançadas
    assert _mes(atomos, "2026-02", "pessoas") == fev_pessoas * 105 // 100
    assert _mes(atomos, "2026-02", "compras") == 110_000 * 115 // 100


def test_pessoa_ativa_sem_lancamento_entra_com_a_capacidade_do_mes(base):
    conexao, bd, *_ = base
    c = cenarios.achar(conexao, bd, cenarios.criar(conexao, bd, "Base", 10000, 10000))

    atomos = forecast.atomos(conexao, bd, 2026, c, AGORA)

    # março: Ana (sem lançamento) e Bia (ativa só em março) com 168 h (21 dias úteis × 8 h)...
    capacidade_marco = 22 * 8  # mar/2026 tem 22 dias úteis
    esperado = 2 * capacidade_marco * 21_230
    assert _mes(atomos, "2026-03", "pessoas") == esperado


def test_vaga_aberta_entra_a_partir_do_inicio_do_cenario(base):
    conexao, bd, _, vaga, _ = base
    base_id = cenarios.criar(conexao, bd, "Base", 10000, 10000)
    otim_id = cenarios.criar(conexao, bd, "Otimista", 9700, 9000)
    cenarios.definir_inicio_vaga(conexao, bd, base_id, vaga, "2026-06")
    cenarios.definir_inicio_vaga(conexao, bd, otim_id, vaga, "2026-09")

    na_base = forecast.atomos(conexao, bd, 2026, cenarios.achar(conexao, bd, base_id), AGORA)
    na_otim = forecast.atomos(conexao, bd, 2026, cenarios.achar(conexao, bd, otim_id), AGORA)

    assert _mes(na_base, "2026-05", "vagas") == 0
    assert _mes(na_base, "2026-06", "vagas") > 0
    assert _mes(na_otim, "2026-06", "vagas") == 0
    assert _mes(na_otim, "2026-09", "vagas") > 0


def test_vaga_cancelada_ou_preenchida_nao_entra_como_vaga(base):
    conexao, bd, _, vaga, _ = base
    pessoas.cancelar_vaga(conexao, bd, vaga)
    c = cenarios.achar(conexao, bd, cenarios.criar(conexao, bd, "Base", 10000, 10000))

    atomos = forecast.atomos(conexao, bd, 2026, c, AGORA)

    assert [a for a in atomos if a.origem == "vagas"] == []


def test_totais_e_gap_do_cenario_com_o_orcamento_vigente(base):
    conexao, bd, ini, _, _ = base
    rev = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.definir_linha(conexao, bd, rev.id, ini, "CAPEX", 100_000_000)
    orcamento.aprovar(conexao, bd, rev.id, AGORA)
    c = cenarios.achar(conexao, bd, cenarios.criar(conexao, bd, "Base", 10000, 10000))

    resumo = forecast.resumo(conexao, bd, 2026, c, "bruto", AGORA)

    atomos = forecast.atomos(conexao, bd, 2026, c, AGORA)
    assert resumo.realizado == sum(a.valor_centavos for a in atomos if a.realizado)
    assert resumo.forecast == sum(a.valor_centavos for a in atomos if not a.realizado)
    assert resumo.orcamento == 100_000_000
    assert resumo.gap == orcamento.gap(100_000_000, resumo.realizado + resumo.forecast)


def test_cenarios_diferentes_dao_totais_diferentes_e_o_mesmo_cenario_o_mesmo_total(base):
    conexao, bd, *_ = base
    a = cenarios.achar(conexao, bd, cenarios.criar(conexao, bd, "Base", 10000, 10000))
    b = cenarios.achar(conexao, bd, cenarios.criar(conexao, bd, "Pessimista", 10500, 11500))

    primeiro = forecast.resumo(conexao, bd, 2026, a, "bruto", AGORA)
    repetido = forecast.resumo(conexao, bd, 2026, a, "bruto", AGORA)
    pessimista = forecast.resumo(conexao, bd, 2026, b, "bruto", AGORA)

    assert primeiro == repetido
    assert pessimista.forecast > primeiro.forecast
    assert pessimista.realizado == primeiro.realizado


def test_cenario_de_outro_bd_nao_e_acessivel(base):
    conexao, bd, *_ = base
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    cid = cenarios.criar(conexao, bd, "Base", 10000, 10000)

    assert cenarios.achar(conexao, outro, cid) is None
    assert cenarios.listar(conexao, outro) == []


# ---- composição do treemap ----


def _quinquenal(conexao, bd):
    """Uma segunda iniciativa/agrupamento para ter mais de um elemento."""
    squad = organizacao.listar_orgs(conexao, bd)[1].id
    agrup = portfolio.criar_agrupamento(conexao, bd, "Gravity")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-2", "Beta")
    dem = portfolio.criar_demanda(conexao, bd, "D-2", ini, "Dem 2", "OPEX", squad)
    portfolio.criar_tema(conexao, bd, "T-2", dem, "Tema 2", agrup)
    conexao.execute(
        "INSERT INTO compra (bd_id, numero, tipo, demanda_id, status) VALUES (%s, 'OC2', 'OC', %s, 'emitida')",
        (bd, dem),
    )
    compra = conexao.execute("SELECT id FROM compra WHERE numero = 'OC2'").fetchone()[0]
    conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (%s, %s, '2026-02', 300000)",
        (bd, compra),
    )
    conexao.commit()


def test_elementos_por_agrupamento_com_realizado_e_forecast(base):
    conexao, bd, *_ = base
    _quinquenal(conexao, bd)
    cid = cenarios.criar(conexao, bd, "Q1", 10000, 10000, trimestres=1)  # só jan a mar

    comp = forecast.composicao(conexao, bd, 2026, cenarios.achar(conexao, bd, cid), "bruto", AGORA)

    por_nome = {e.nome: e for e in comp.elementos}
    assert por_nome["RTB"].realizado == 100 * 21_230  # jan fechado
    assert por_nome["Gravity"].forecast == 330_000  # compra de R$ 3.000 em fev × 1,10
    assert comp.meses == ["2026-01", "2026-02", "2026-03"]


def test_so_cabe_no_cenario_o_que_cabe_na_escala(base):
    conexao, bd, *_ = base
    _quinquenal(conexao, bd)
    cid = cenarios.criar(
        conexao, bd, "Escala", 10000, 10000, trimestres=1,
        escala_valor=400_000, elemento_tipo="Agrupamento",
    )  # fmt: skip
    c = cenarios.achar(conexao, bd, cid)

    forecast.incluir(
        conexao, bd, 2026, c, "0" if False else _chave(conexao, bd, c, "Gravity"), "bruto", AGORA
    )
    with pytest.raises(cenarios.CenarioInvalido) as erro:
        forecast.incluir(
            conexao, bd, 2026, cenarios.achar(conexao, bd, cid),
            _chave(conexao, bd, c, "RTB"), "bruto", AGORA,
        )  # fmt: skip

    assert "Não cabe" in str(erro.value) and "Faltam" in str(erro.value)
    assert cenarios.achar(conexao, bd, cid).incluidos == [_chave(conexao, bd, c, "Gravity")]


def _chave(conexao, bd, cenario, nome):
    comp = forecast.composicao(conexao, bd, 2026, cenario, "bruto", AGORA)
    return next(e.chave for e in comp.elementos if e.nome == nome)


def test_a_area_do_bloco_e_proporcional_ao_valor_na_composicao(base):
    conexao, bd, *_ = base
    _quinquenal(conexao, bd)
    cid = cenarios.criar(
        conexao, bd, "Todos", 10000, 10000, trimestres=15, escala_valor=5_000_000_000
    )
    c = cenarios.achar(conexao, bd, cid)
    for e in forecast.composicao(conexao, bd, 2026, c, "bruto", AGORA).elementos:
        forecast.incluir(
            conexao, bd, 2026, cenarios.achar(conexao, bd, cid), e.chave, "bruto", AGORA
        )

    comp = forecast.composicao(conexao, bd, 2026, cenarios.achar(conexao, bd, cid), "bruto", AGORA)

    area_total = forecast.LARGURA_TREEMAP * forecast.ALTURA_TREEMAP
    por_chave = {b.chave: b for b in comp.blocos}
    for e in comp.incluidos:
        b = por_chave[e.chave]
        assert b.largura * b.altura / area_total == pytest.approx(e.total / 5_000_000_000, rel=1e-9)
    assert "__saldo" in por_chave  # o que sobra da escala


def test_retirar_do_cenario(base):
    conexao, bd, *_ = base
    cid = cenarios.criar(conexao, bd, "R", 10000, 10000, incluidos=["1"])

    forecast.retirar(conexao, bd, cenarios.achar(conexao, bd, cid), "1")

    assert cenarios.achar(conexao, bd, cid).incluidos == []
