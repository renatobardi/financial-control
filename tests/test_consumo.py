from datetime import UTC, datetime

import pytest

from financeiro import consumo, fechamento, senha
from financeiro.store import acesso, cadastros, organizacao, pessoas, portfolio

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


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
    ini = portfolio.criar_iniciativa(conexao, bd, "I-1", "Ini")
    dem = portfolio.criar_demanda(conexao, bd, "D-1", ini, "Dem", "CAPEX", squad)
    tema = portfolio.criar_tema(conexao, bd, "T-1", dem, "Tema", agrup)
    pessoa = pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo, tema, "2025-01", None)
    conexao.execute(
        "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (?, ?, ?, '2026-01', 100)",
        (bd, pessoa, tema),
    )
    conexao.execute(
        "INSERT INTO compra (bd_id, numero, tipo, demanda_id, status) VALUES (?, 'OC1', 'OC', ?, 'emitida')",
        (bd, dem),
    )
    compra = conexao.execute("SELECT id FROM compra").fetchone()[0]
    conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (?, ?, '2026-01', 100000)",
        (bd, compra),
    )
    conexao.commit()
    return conexao, bd, usuario, cargo, ini


def test_lancamentos_do_mes_trazem_liquido_bruto_e_classificacao(base):
    conexao, bd, _, _, ini = base

    estado, linhas = consumo.do_mes(conexao, bd, "2026-01")

    assert estado == "forecast"
    pessoas_, compras = sorted(linhas, key=lambda x: x.origem, reverse=True)
    assert (pessoas_.origem, pessoas_.horas, pessoas_.liquido_centavos) == (
        "pessoas",
        100,
        1_930_000,
    )
    assert pessoas_.bruto_centavos == 2_123_000  # 100 × R$ 193,00 × 1,10
    assert (pessoas_.tipo, pessoas_.iniciativa_id) == ("CAPEX", ini)
    assert (compras.origem, compras.liquido_centavos, compras.bruto_centavos) == (
        "compras", 100_000, 110_000,
    )  # fmt: skip


def test_ao_fechar_o_mes_o_realizado_fica_congelado_com_a_classificacao_daquele_momento(base):
    conexao, bd, usuario, cargo, _ = base
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)
    cadastros.definir_tarifa(conexao, bd, cargo, 30000, "2026-02")  # não afeta jan
    conexao.execute("UPDATE demanda SET tipo = 'OPEX'")  # reclassificação posterior
    conexao.commit()

    estado, linhas = consumo.do_mes(conexao, bd, "2026-01")

    assert estado == "realizado"
    assert sum(linha.bruto_centavos for linha in linhas) == 2_123_000 + 110_000
    assert {linha.tipo for linha in linhas} == {"CAPEX"}


def test_reabrir_apaga_o_congelado_e_volta_a_calcular(base):
    conexao, bd, usuario, _, _ = base
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)

    fechamento.reabrir(conexao, bd, "2026-01", usuario, AGORA, "ajuste")

    assert conexao.execute("SELECT COUNT(*) FROM realizado_linha").fetchone()[0] == 0
    assert consumo.do_mes(conexao, bd, "2026-01")[0] == "forecast"
