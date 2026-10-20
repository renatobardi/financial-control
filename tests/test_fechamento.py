from datetime import UTC, datetime

import pytest

from financeiro import fechamento, senha
from financeiro.store import acesso, cadastros, organizacao, pessoas, portfolio

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def base(conexao):
    """Uma pessoa com 100 h em set/2026 (R$ 193,00/h, markup 10%) e uma compra de R$ 1.000,00."""
    bd = acesso.criar_bd(conexao, "BD", "B")
    usuario = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", senha.gerar_hash("x"))
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "T", None, "G", "2025-01")
    squad = organizacao.criar_org(conexao, bd, "Squad", "S", tribo, "G", "2025-01")
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Sênior", "N9")
    cadastros.definir_tarifa(conexao, bd, cargo, 19300, "2026-01")
    cadastros.definir_markup(conexao, bd, 1000, "2026-01")
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-1", "Ini")
    dem = portfolio.criar_demanda(conexao, bd, "D-1", ini, "Dem", "OPEX", squad)
    tema = portfolio.criar_tema(conexao, bd, "T-1", dem, "Tema", agrup)
    pessoa = pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo, tema, "2025-01", None)
    conexao.execute(
        "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (%s, %s, %s, '2026-09', 100)",
        (bd, pessoa, tema),
    )
    conexao.execute(
        "INSERT INTO compra (bd_id, numero, tipo, demanda_id, status) VALUES (%s, 'OC1', 'OC', %s, 'emitida')",
        (bd, dem),
    )
    compra = conexao.execute("SELECT id FROM compra").fetchone()[0]
    conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (%s, %s, '2026-09', 100000)",
        (bd, compra),
    )
    conexao.commit()
    return conexao, bd, usuario, cargo


def _fechar_ate(conexao, bd, usuario, ate):
    for mes in range(1, ate + 1):
        fechamento.fechar(conexao, bd, f"2026-{mes:02d}", usuario, AGORA)


def test_mes_aberto_e_forecast_com_valor_pelas_tarifas_vigentes(base):
    conexao, bd, _, _ = base

    t = fechamento.totais_do_mes(conexao, bd, "2026-09")

    assert t.estado == "forecast"
    assert t.horas == 100
    assert t.pessoas_centavos == 2_123_000  # 100 h × R$ 193,00 × 1,10
    assert t.compras_centavos == 110_000  # R$ 1.000,00 × 1,10
    assert t.total_centavos == 2_233_000


def test_nao_fecha_mes_sem_o_anterior_fechado(base):
    conexao, bd, usuario, _ = base

    with pytest.raises(fechamento.MesAnteriorAberto) as erro:
        fechamento.fechar(conexao, bd, "2026-03", usuario, AGORA)

    assert "2026-02" in str(erro.value) or "fev/2026" in str(erro.value)
    assert fechamento.meses_fechados(conexao, bd) == []


def test_primeiro_mes_do_ano_inicial_pode_fechar(base):
    conexao, bd, usuario, _ = base

    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)

    assert fechamento.meses_fechados(conexao, bd) == ["2026-01"]
    with pytest.raises(fechamento.MesAnteriorAberto):
        fechamento.fechar(conexao, bd, "2025-12", usuario, AGORA)  # antes do início


def test_mes_ja_fechado_nao_fecha_de_novo(base):
    conexao, bd, usuario, _ = base
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)

    with pytest.raises(fechamento.MesJaFechado):
        fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)


def test_fechar_e_reabrir_deixa_os_totais_iguais(base):
    conexao, bd, usuario, _ = base
    antes = fechamento.totais_do_mes(conexao, bd, "2026-09")
    _fechar_ate(conexao, bd, usuario, 9)

    fechado = fechamento.totais_do_mes(conexao, bd, "2026-09")
    fechamento.reabrir(conexao, bd, "2026-09", usuario, AGORA, "correção de horas")
    depois = fechamento.totais_do_mes(conexao, bd, "2026-09")

    assert fechado.estado == "realizado"
    assert (antes.estado, depois.estado) == ("forecast", "forecast")
    assert (fechado.total_centavos, depois.total_centavos) == (antes.total_centavos,) * 2
    assert (fechado.horas, depois.horas) == (antes.horas,) * 2


def test_mes_fechado_fica_congelado_diante_de_mudanca_de_tarifa(base):
    conexao, bd, usuario, cargo = base
    _fechar_ate(conexao, bd, usuario, 9)
    cadastros.definir_tarifa(conexao, bd, cargo, 25000, "2026-09")  # vale a partir de set

    fechado = fechamento.totais_do_mes(conexao, bd, "2026-09")
    fechamento.reabrir(conexao, bd, "2026-09", usuario, AGORA, "recalcular")
    reaberto = fechamento.totais_do_mes(conexao, bd, "2026-09")

    assert fechado.pessoas_centavos == 2_123_000  # congelado na tarifa de quando fechou
    assert reaberto.pessoas_centavos == 100 * 27_500  # 25.000 × 1,10 por hora


def test_so_o_ultimo_mes_fechado_pode_ser_reaberto_e_o_motivo_e_obrigatorio(base):
    conexao, bd, usuario, _ = base
    _fechar_ate(conexao, bd, usuario, 3)

    with pytest.raises(fechamento.ReaberturaInvalida):
        fechamento.reabrir(conexao, bd, "2026-02", usuario, AGORA, "x")
    with pytest.raises(fechamento.ReaberturaInvalida):
        fechamento.reabrir(conexao, bd, "2026-03", usuario, AGORA, "   ")
    with pytest.raises(fechamento.ReaberturaInvalida):
        fechamento.reabrir(conexao, bd, "2026-04", usuario, AGORA, "ainda aberto")

    fechamento.reabrir(conexao, bd, "2026-03", usuario, AGORA, "ajuste")
    assert fechamento.meses_fechados(conexao, bd) == ["2026-01", "2026-02"]


def test_log_registra_cada_fechamento_e_reabertura_com_autor_hora_e_motivo(base):
    conexao, bd, usuario, _ = base
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)
    fechamento.reabrir(conexao, bd, "2026-01", usuario, AGORA, "erro de carga")

    log = fechamento.log(conexao, bd)

    assert [(e.mes, e.acao, e.autor, e.motivo, e.em) for e in log] == [
        ("2026-01", "reabriu", "Ana", "erro de carga", "2026-10-10T12:00:00Z"),
        ("2026-01", "fechou", "Ana", "", "2026-10-10T12:00:00Z"),
    ]


def test_situacao_do_ano_indica_o_que_pode_fechar_e_reabrir(base):
    conexao, bd, usuario, _ = base
    _fechar_ate(conexao, bd, usuario, 2)

    meses = fechamento.situacao(conexao, bd, 2026)

    assert [(m.mes, m.estado, m.pode_fechar, m.pode_reabrir) for m in meses[:4]] == [
        ("2026-01", "fechado", False, False),
        ("2026-02", "fechado", False, True),
        ("2026-03", "aberto", True, False),
        ("2026-04", "aberto", False, False),
    ]


def test_bd_nao_enxerga_fechamento_de_outro_bd(base):
    conexao, bd, usuario, _ = base
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)

    assert fechamento.meses_fechados(conexao, outro) == []
    assert fechamento.log(conexao, outro) == []
