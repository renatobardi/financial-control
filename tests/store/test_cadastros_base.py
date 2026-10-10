import sqlite3

import pytest

from financeiro import vigencia
from financeiro.store import acesso, cadastros


@pytest.fixture
def bd(conexao):
    return acesso.criar_bd(conexao, "BD Mobility", "BM")


def test_empresa_tem_tipo_e_nome_unico_por_bd(conexao, bd):
    cadastros.criar_empresa(conexao, bd, "Própria", "propria")

    with pytest.raises(sqlite3.IntegrityError):
        cadastros.criar_empresa(conexao, bd, "Própria", "consultoria")
    with pytest.raises(sqlite3.IntegrityError):
        cadastros.criar_empresa(conexao, bd, "NTT", "terceiro")


def test_mesmo_nome_de_empresa_em_bds_diferentes_e_permitido(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    cadastros.criar_empresa(conexao, bd, "NTT", "consultoria")
    cadastros.criar_empresa(conexao, outro, "NTT", "consultoria")

    assert [e.nome for e in cadastros.listar_empresas(conexao, bd)] == ["NTT"]
    assert [e.nome for e in cadastros.listar_empresas(conexao, outro)] == ["NTT"]


def test_cargo_com_nivel_valido_na_empresa(conexao, bd):
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")

    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Sênior", "N9")

    achado = cadastros.achar_cargo(conexao, bd, cargo)
    assert (achado.nome, achado.nivel, achado.empresa) == ("Sênior", "N9", "Própria")
    with pytest.raises(sqlite3.IntegrityError):
        cadastros.criar_cargo(conexao, bd, empresa, "Mestre", "N13")


def test_cargo_nao_aceita_empresa_de_outro_bd(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    empresa_outro = cadastros.criar_empresa(conexao, outro, "NTT", "consultoria")

    with pytest.raises(sqlite3.IntegrityError):
        cadastros.criar_cargo(conexao, bd, empresa_outro, "Dev", "N8")


def _cargo(conexao, bd):
    empresa = cadastros.criar_empresa(conexao, bd, "NTT", "consultoria")
    return cadastros.criar_cargo(conexao, bd, empresa, "Developer Pleno", "N8")


def test_tarifa_nova_encerra_a_anterior_no_mes_anterior(conexao, bd):
    cargo = _cargo(conexao, bd)
    cadastros.definir_tarifa(conexao, bd, cargo, 12960, "2025-01")

    cadastros.definir_tarifa(conexao, bd, cargo, 13500, "2026-02")

    historico = [
        (t.liquida_centavos, t.inicio, t.fim)
        for t in cadastros.tarifas_do_cargo(conexao, bd, cargo)
    ]
    assert historico == [(12960, "2025-01", "2026-01"), (13500, "2026-02", None)]


def test_tarifa_retroativa_e_recusada(conexao, bd):
    cargo = _cargo(conexao, bd)
    cadastros.definir_tarifa(conexao, bd, cargo, 13500, "2026-02")

    with pytest.raises(vigencia.VigenciaSobreposta):
        cadastros.definir_tarifa(conexao, bd, cargo, 12000, "2026-01")
    with pytest.raises(vigencia.VigenciaSobreposta):
        cadastros.definir_tarifa(conexao, bd, cargo, 12000, "2026-02")


def test_tarifa_vigente_na_data(conexao, bd):
    cargo = _cargo(conexao, bd)
    cadastros.definir_tarifa(conexao, bd, cargo, 12960, "2025-01")
    cadastros.definir_tarifa(conexao, bd, cargo, 13500, "2026-02")

    assert cadastros.tarifa_vigente(conexao, bd, cargo, "2025-06").liquida_centavos == 12960
    assert cadastros.tarifa_vigente(conexao, bd, cargo, "2026-01").liquida_centavos == 12960
    assert cadastros.tarifa_vigente(conexao, bd, cargo, "2026-02").liquida_centavos == 13500
    assert cadastros.tarifa_vigente(conexao, bd, cargo, "2024-12") is None


def test_banco_recusa_vigencias_sobrepostas_mesmo_por_fora_do_store(conexao, bd):
    cargo = _cargo(conexao, bd)
    cadastros.definir_tarifa(conexao, bd, cargo, 12960, "2025-01")

    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute(
            "INSERT INTO tarifa (bd_id, cargo_id, liquida_centavos, vigencia_ini, vigencia_fim)"
            " VALUES (?, ?, 1, '2025-06', '2025-08')",
            (bd, cargo),
        )


def test_tarifa_do_mesmo_cargo_vale_so_para_o_bd_dele(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    cargo = _cargo(conexao, bd)
    cadastros.definir_tarifa(conexao, bd, cargo, 12960, "2025-01")

    assert cadastros.tarifa_vigente(conexao, outro, cargo, "2025-06") is None


def test_markup_com_vigencia_sem_sobreposicao(conexao, bd):
    cadastros.definir_markup(conexao, bd, 1050, "2025-01")
    cadastros.definir_markup(conexao, bd, 1090, "2026-02")

    assert cadastros.markup_vigente(conexao, bd, "2025-12").centesimos_pct == 1050
    assert cadastros.markup_vigente(conexao, bd, "2026-02").centesimos_pct == 1090
    assert [(m.inicio, m.fim) for m in cadastros.listar_markups(conexao, bd)] == [
        ("2025-01", "2026-01"),
        ("2026-02", None),
    ]
    with pytest.raises(vigencia.VigenciaSobreposta):
        cadastros.definir_markup(conexao, bd, 900, "2026-01")


def test_mes_de_vigencia_invalido_e_recusado(conexao, bd):
    cargo = _cargo(conexao, bd)

    with pytest.raises(ValueError):
        cadastros.definir_tarifa(conexao, bd, cargo, 100, "2026-13")
