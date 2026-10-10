import pytest

from financeiro import custo
from financeiro.store import acesso, cadastros


def test_bruta_aplica_o_markup_e_arredonda_para_cima_no_meio():
    # R$ 193,00 com 10,9% = 21.404 centavos (19.300 + 2.103,7 arredondado)
    assert custo.bruta(19300, 1090) == 21404
    assert custo.bruta(10000, 1050) == 11050
    assert custo.bruta(0, 1050) == 0
    # meio centavo sobe: 1 centavo a 50% = 1,5 -> 2
    assert custo.bruta(1, 5000) == 2
    assert custo.bruta(12345, 0) == 12345


def test_bruta_recusa_float():
    with pytest.raises(TypeError):
        custo.bruta(193.0, 1090)


@pytest.fixture
def cenario(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    empresa = cadastros.criar_empresa(conexao, bd, "NTT", "consultoria")
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Developer Specialist II", "N11")
    cadastros.definir_tarifa(conexao, bd, cargo, 19656, "2025-01")  # R$ 196,56
    cadastros.definir_tarifa(conexao, bd, cargo, 20475, "2026-02")  # R$ 204,75
    cadastros.definir_markup(conexao, bd, 1050, "2025-01")
    cadastros.definir_markup(conexao, bd, 1090, "2026-02")
    return conexao, bd, cargo


def test_custo_hora_usa_a_tarifa_e_o_markup_vigentes_na_data(cenario):
    conexao, bd, cargo = cenario

    antes = custo.custo_hora(conexao, bd, cargo, "2025-06")
    depois = custo.custo_hora(conexao, bd, cargo, "2026-03")

    assert (antes.liquida_centavos, antes.markup_centesimos_pct) == (19656, 1050)
    assert antes.bruta_centavos == 21720  # 19.656 x 1,105
    assert (depois.liquida_centavos, depois.markup_centesimos_pct) == (20475, 1090)
    assert depois.bruta_centavos == 22707  # 20.475 x 1,109 = 22.706,8


def test_custo_hora_sem_tarifa_ou_sem_markup_na_data_falha_com_motivo(cenario):
    conexao, bd, cargo = cenario

    with pytest.raises(custo.SemTarifa):
        custo.custo_hora(conexao, bd, cargo, "2024-12")
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    with pytest.raises(custo.SemTarifa):
        custo.custo_hora(conexao, outro, cargo, "2025-06")
