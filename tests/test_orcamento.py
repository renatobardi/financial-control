from datetime import UTC, datetime

import pytest

from financeiro import orcamento
from financeiro.store import acesso, cadastros, portfolio

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def base(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")
    ini_a = portfolio.criar_iniciativa(conexao, bd, "I-01", "Alfa")
    ini_b = portfolio.criar_iniciativa(conexao, bd, "I-02", "Beta")
    return conexao, bd, ini_a, ini_b


def test_primeira_revisao_e_a_original_em_rascunho(base):
    conexao, bd, _, _ = base

    revisao = orcamento.nova_revisao(conexao, bd, AGORA)

    assert (revisao.rotulo, revisao.estado) == ("Original", "rascunho")
    assert orcamento.vigente(conexao, bd) is None


def test_so_um_rascunho_por_vez_e_no_maximo_quatro_revisoes(base):
    conexao, bd, _, _ = base
    original = orcamento.nova_revisao(conexao, bd, AGORA)
    with pytest.raises(orcamento.OrcamentoInvalido):
        orcamento.nova_revisao(conexao, bd, AGORA)  # já há rascunho
    orcamento.aprovar(conexao, bd, original.id, AGORA)
    for rotulo in ("T1", "T2", "T3"):
        nova = orcamento.nova_revisao(conexao, bd, AGORA)
        assert nova.rotulo == rotulo
        orcamento.aprovar(conexao, bd, nova.id, AGORA)

    with pytest.raises(orcamento.OrcamentoInvalido):
        orcamento.nova_revisao(conexao, bd, AGORA)


def test_aprovar_congela_o_markup_da_hora_e_vira_a_vigente(base):
    conexao, bd, ini_a, _ = base
    original = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.definir_linha(conexao, bd, original.id, ini_a, "CAPEX", 110_500_000)

    aprovada = orcamento.aprovar(conexao, bd, original.id, AGORA)
    cadastros.definir_markup(conexao, bd, 1090, "2026-11")  # muda depois

    assert (aprovada.estado, aprovada.markup_centesimos_pct) == ("aprovada", 1050)
    assert orcamento.vigente(conexao, bd).id == original.id
    linhas = orcamento.linhas(conexao, bd, original.id, AGORA)
    assert linhas[0].bruto_centavos == 110_500_000
    assert linhas[0].liquido_centavos == 100_000_000  # 110.500.000 ÷ 1,105


def test_bruto_e_liquido_vezes_um_mais_o_markup_congelado_da_revisao(base):
    conexao, bd, ini_a, _ = base
    original = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.definir_linha(conexao, bd, original.id, ini_a, "OPEX", 110_500_000)
    orcamento.aprovar(conexao, bd, original.id, AGORA)
    cadastros.definir_markup(conexao, bd, 2000, "2026-11")  # markup vigente de hoje: 20%

    linha = orcamento.linhas(conexao, bd, original.id, AGORA)[0]

    from financeiro import custo

    assert custo.bruta(linha.liquido_centavos, 1050) == linha.bruto_centavos


def test_nova_revisao_parte_da_vigente_e_nao_mexe_na_aprovada(base):
    conexao, bd, ini_a, ini_b = base
    original = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.definir_linha(conexao, bd, original.id, ini_a, "CAPEX", 100_000)
    orcamento.aprovar(conexao, bd, original.id, AGORA)

    t1 = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.definir_linha(conexao, bd, t1.id, ini_a, "CAPEX", 120_000)
    orcamento.definir_linha(conexao, bd, t1.id, ini_b, "OPEX", 50_000)

    assert [x.bruto_centavos for x in orcamento.linhas(conexao, bd, original.id, AGORA)] == [
        100_000
    ]
    assert sorted(x.bruto_centavos for x in orcamento.linhas(conexao, bd, t1.id, AGORA)) == [
        50_000,
        120_000,
    ]


def test_revisao_aprovada_nao_aceita_edicao(base):
    conexao, bd, ini_a, _ = base
    original = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.aprovar(conexao, bd, original.id, AGORA)

    with pytest.raises(orcamento.OrcamentoInvalido):
        orcamento.definir_linha(conexao, bd, original.id, ini_a, "CAPEX", 1)
    with pytest.raises(orcamento.OrcamentoInvalido):
        orcamento.remover_linha(conexao, bd, original.id, ini_a, "CAPEX")
    with pytest.raises(orcamento.OrcamentoInvalido):
        orcamento.descartar(conexao, bd, original.id)


def test_descartar_rascunho_apaga_a_revisao_e_as_linhas(base):
    conexao, bd, ini_a, _ = base
    original = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.aprovar(conexao, bd, original.id, AGORA)
    t1 = orcamento.nova_revisao(conexao, bd, AGORA)
    orcamento.definir_linha(conexao, bd, t1.id, ini_a, "CAPEX", 5)

    orcamento.descartar(conexao, bd, t1.id)

    assert [r.rotulo for r in orcamento.revisoes(conexao, bd)] == ["Original"]
    assert orcamento.rascunho(conexao, bd) is None


def test_tipo_e_valor_invalidos_sao_recusados(base):
    conexao, bd, ini_a, _ = base
    original = orcamento.nova_revisao(conexao, bd, AGORA)

    with pytest.raises(orcamento.OrcamentoInvalido):
        orcamento.definir_linha(conexao, bd, original.id, ini_a, "INFRA", 1)
    with pytest.raises(orcamento.OrcamentoInvalido):
        orcamento.definir_linha(conexao, bd, original.id, ini_a, "CAPEX", -1)
    with pytest.raises(TypeError):
        orcamento.definir_linha(conexao, bd, original.id, ini_a, "CAPEX", 1.5)


def test_aprovar_sem_markup_vigente_e_recusado(conexao):
    bd = acesso.criar_bd(conexao, "Sem markup", "SM")
    original = orcamento.nova_revisao(conexao, bd, AGORA)

    with pytest.raises(orcamento.OrcamentoInvalido) as erro:
        orcamento.aprovar(conexao, bd, original.id, AGORA)

    assert "markup" in str(erro.value)


def test_gap_tem_sinal_unico_positivo_e_saldo_negativo_e_estouro():
    assert orcamento.gap(1_000_000, 800_000) == 200_000
    assert orcamento.gap(1_000_000, 1_200_000) == -200_000
    assert orcamento.gap(1_000_000, 1_000_000) == 0


def test_revisao_de_outro_bd_nao_e_acessivel(base):
    conexao, bd, ini_a, _ = base
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    original = orcamento.nova_revisao(conexao, bd, AGORA)

    with pytest.raises(orcamento.OrcamentoInvalido):
        orcamento.definir_linha(conexao, outro, original.id, ini_a, "CAPEX", 1)
    with pytest.raises(orcamento.OrcamentoInvalido):
        orcamento.aprovar(conexao, outro, original.id, AGORA)
