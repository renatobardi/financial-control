import datetime as dt

import pytest

from financeiro import calendario
from financeiro.store import acesso

# Dias úteis de 2026 conferidos à mão contra o calendário (Páscoa em 5/abr/2026):
# jan..dez = 21 18 22 20 20 21 23 21 21 21 19 22.
DIAS_UTEIS_2026 = [21, 18, 22, 20, 20, 21, 23, 21, 21, 21, 19, 22]


def test_pascoa_de_alguns_anos():
    assert calendario.pascoa(2025) == dt.date(2025, 4, 20)
    assert calendario.pascoa(2026) == dt.date(2026, 4, 5)
    assert calendario.pascoa(2027) == dt.date(2027, 3, 28)


def test_feriados_nacionais_e_bancarios_de_2026():
    feriados = calendario.feriados_nacionais(2026)

    assert feriados[dt.date(2026, 2, 16)] == "Carnaval"
    assert feriados[dt.date(2026, 4, 3)] == "Sexta-feira Santa"
    assert feriados[dt.date(2026, 6, 4)] == "Corpus Christi"
    assert feriados[dt.date(2026, 11, 20)] == "Consciência Negra"
    assert len(feriados) == 13


def test_dias_uteis_do_ano():
    obtido = [calendario.dias_uteis(2026, m) for m in range(1, 13)]

    assert obtido == DIAS_UTEIS_2026


def test_feriado_do_bd_tira_um_dia_util():
    extra = {dt.date(2026, 1, 20)}  # terça

    assert calendario.dias_uteis(2026, 1, extra) == 20


def test_feriado_do_bd_em_fim_de_semana_nao_muda_nada():
    extra = {dt.date(2026, 1, 3)}  # sábado

    assert calendario.dias_uteis(2026, 1, extra) == 21


@pytest.fixture
def bd(conexao):
    return acesso.criar_bd(conexao, "BD", "B")


def test_gerar_o_ano_grava_8h_por_dia_util(conexao, bd):
    calendario.gerar(conexao, bd, 2026)

    horas = [calendario.horas_do_mes(conexao, bd, 2026, m) for m in range(1, 13)]
    assert horas == [n * 8 for n in DIAS_UTEIS_2026]


def test_gerar_considera_feriado_do_bd(conexao, bd):
    calendario.adicionar_feriado(conexao, bd, dt.date(2026, 1, 20), "São Sebastião")

    calendario.gerar(conexao, bd, 2026)

    assert calendario.horas_do_mes(conexao, bd, 2026, 1) == 20 * 8


def test_ajuste_manual_sobrevive_a_gerar_de_novo(conexao, bd):
    calendario.gerar(conexao, bd, 2026)
    calendario.ajustar(conexao, bd, 2026, 3, 160)

    calendario.gerar(conexao, bd, 2026)

    assert calendario.horas_do_mes(conexao, bd, 2026, 3) == 160
    assert calendario.horas_do_mes(conexao, bd, 2026, 4) == 20 * 8


def test_horas_de_um_bd_nao_aparecem_em_outro(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    calendario.gerar(conexao, bd, 2026)

    assert calendario.horas_do_mes(conexao, outro, 2026, 1) is None


def test_ajuste_invalido_e_recusado(conexao, bd):
    with pytest.raises(ValueError):
        calendario.ajustar(conexao, bd, 2026, 13, 160)
    with pytest.raises(ValueError):
        calendario.ajustar(conexao, bd, 2026, 3, -8)
