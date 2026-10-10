from datetime import UTC, datetime

import pytest

from financeiro import compras, fechamento, senha
from financeiro.store import acesso, cadastros, organizacao, portfolio

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def base(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    usuario = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", senha.gerar_hash("x"))
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "T", None, "G", "2025-01")
    squad = organizacao.criar_org(conexao, bd, "Squad", "S", tribo, "G", "2025-01")
    cadastros.definir_markup(conexao, bd, 1000, "2026-01")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-1", "Ini")
    dem = portfolio.criar_demanda(conexao, bd, "D-1", ini, "Dem", "OPEX", squad)
    forn = portfolio.criar_fornecedor(conexao, bd, "Fornecedor A")
    return conexao, bd, usuario, dem, forn


def test_nova_ordem_prevista_nasce_sem_numero_e_com_historico(base):
    conexao, bd, usuario, dem, _ = base

    ordem = compras.criar_prevista(conexao, bd, "OS", dem, "Extensão de escopo", usuario, AGORA)

    achada = compras.achar(conexao, bd, ordem)
    assert (achada.status, achada.tipo, achada.sem_numero) == ("prevista", "OS", True)
    assert [h.texto for h in compras.historico(conexao, bd, ordem)] == [
        "criada como prevista por Ana"
    ]


def test_emitir_exige_numero_e_fornecedor(base):
    conexao, bd, usuario, dem, forn = base
    ordem = compras.criar_prevista(conexao, bd, "OC", dem, "Licenças", usuario, AGORA)

    with pytest.raises(compras.ComprasInvalido):
        compras.editar(conexao, bd, ordem, usuario, AGORA, status="emitida")
    compras.editar(
        conexao, bd, ordem, usuario, AGORA,
        status="emitida", numero="OC0042", fornecedor_id=forn,
    )  # fmt: skip

    achada = compras.achar(conexao, bd, ordem)
    assert (achada.status, achada.numero, achada.fornecedor) == (
        "emitida", "OC0042", "Fornecedor A",
    )  # fmt: skip
    assert "emitida" in compras.historico(conexao, bd, ordem)[0].texto


def test_numero_repetido_e_recusado(base):
    conexao, bd, usuario, dem, forn = base
    a = compras.criar_prevista(conexao, bd, "OC", dem, "A", usuario, AGORA)
    b = compras.criar_prevista(conexao, bd, "OC", dem, "B", usuario, AGORA)
    compras.editar(
        conexao, bd, a, usuario, AGORA, status="emitida", numero="OC1", fornecedor_id=forn
    )

    with pytest.raises(compras.ComprasInvalido):
        compras.editar(
            conexao, bd, b, usuario, AGORA, status="emitida", numero="OC1", fornecedor_id=forn
        )


def test_valor_so_em_mes_aberto_e_cancelada_nao_recebe_valor(base):
    conexao, bd, usuario, dem, _ = base
    ordem = compras.criar_prevista(conexao, bd, "OS", dem, "X", usuario, AGORA)
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)

    compras.definir_valor(conexao, bd, ordem, "2026-02", 100_000, usuario, AGORA)
    with pytest.raises(compras.ComprasInvalido) as erro:
        compras.definir_valor(conexao, bd, ordem, "2026-01", 100_000, usuario, AGORA)
    compras.editar(conexao, bd, ordem, usuario, AGORA, status="cancelada")
    with pytest.raises(compras.ComprasInvalido):
        compras.definir_valor(conexao, bd, ordem, "2026-03", 1, usuario, AGORA)

    assert "fechado" in str(erro.value)


def test_compra_em_mes_aberto_entra_como_forecast_e_mes_fechado_como_realizado(base):
    conexao, bd, usuario, dem, forn = base
    ordem = compras.criar_prevista(conexao, bd, "OC", dem, "X", usuario, AGORA)
    compras.editar(
        conexao, bd, ordem, usuario, AGORA, status="emitida", numero="OC1", fornecedor_id=forn
    )
    conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (?, ?, '2026-01', 100000)",
        (bd, ordem),
    )
    conexao.commit()
    compras.definir_valor(conexao, bd, ordem, "2026-02", 200_000, usuario, AGORA)
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)

    linha = compras.listar(conexao, bd, 2026, AGORA)[0]

    assert linha.realizado_centavos == 110_000  # jan fechado: R$ 1.000,00 × 1,10
    assert linha.forecast_centavos == 220_000  # fev aberto: R$ 2.000,00 × 1,10


def test_ordem_cancelada_nao_entra_em_realizado_nem_em_forecast(base):
    conexao, bd, usuario, dem, forn = base
    ordem = compras.criar_prevista(conexao, bd, "OC", dem, "X", usuario, AGORA)
    compras.definir_valor(conexao, bd, ordem, "2026-02", 200_000, usuario, AGORA)

    compras.editar(conexao, bd, ordem, usuario, AGORA, status="cancelada")

    linha = compras.listar(conexao, bd, 2026, AGORA)[0]
    assert (linha.realizado_centavos, linha.forecast_centavos) == (0, 0)
    assert fechamento.totais_do_mes(conexao, bd, "2026-02").compras_centavos == 0
    assert forn


def test_nao_cancela_ordem_com_valor_em_mes_fechado(base):
    conexao, bd, usuario, dem, _ = base
    ordem = compras.criar_prevista(conexao, bd, "OC", dem, "X", usuario, AGORA)
    conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (?, ?, '2026-01', 100000)",
        (bd, ordem),
    )
    conexao.commit()
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)

    with pytest.raises(compras.ComprasInvalido) as erro:
        compras.editar(conexao, bd, ordem, usuario, AGORA, status="cancelada")

    assert "fechado" in str(erro.value)
    assert compras.achar(conexao, bd, ordem).status == "prevista"


def test_busca_por_numero_fornecedor_descricao_e_filtro_de_status(base):
    conexao, bd, usuario, dem, forn = base
    a = compras.criar_prevista(conexao, bd, "OC", dem, "Licenças de plataforma", usuario, AGORA)
    compras.criar_prevista(conexao, bd, "OS", dem, "Squad de desenvolvimento", usuario, AGORA)
    compras.editar(
        conexao, bd, a, usuario, AGORA, status="emitida", numero="OC0001", fornecedor_id=forn
    )

    por_texto = compras.listar(conexao, bd, 2026, AGORA, busca="plataforma")
    por_numero = compras.listar(conexao, bd, 2026, AGORA, busca="oc0001")
    por_status = compras.listar(conexao, bd, 2026, AGORA, status="prevista")

    assert [o.descricao for o in por_texto] == ["Licenças de plataforma"]
    assert len(por_numero) == 1 and len(por_status) == 1


def test_valores_por_mes_mostra_realizado_bruto_e_forecast(base):
    conexao, bd, usuario, dem, _ = base
    ordem = compras.criar_prevista(conexao, bd, "OS", dem, "X", usuario, AGORA)
    conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (?, ?, '2026-01', 100000)",
        (bd, ordem),
    )
    conexao.commit()
    fechamento.fechar(conexao, bd, "2026-01", usuario, AGORA)
    compras.definir_valor(conexao, bd, ordem, "2026-02", 50_000, usuario, AGORA)

    meses = compras.valores_por_mes(conexao, bd, ordem, 2026)

    assert (meses[0].estado, meses[0].liquido_centavos, meses[0].bruto_centavos) == (
        "realizado", 100_000, 110_000,
    )  # fmt: skip
    assert (meses[1].estado, meses[1].liquido_centavos, meses[1].bruto_centavos) == (
        "forecast", 50_000, 55_000,
    )  # fmt: skip
    assert meses[2].liquido_centavos == 0


def test_ordem_de_outro_bd_nao_e_acessivel(base):
    conexao, bd, usuario, dem, _ = base
    outro = acesso.criar_bd(conexao, "Outro", "OT")
    ordem = compras.criar_prevista(conexao, bd, "OC", dem, "X", usuario, AGORA)

    assert compras.achar(conexao, outro, ordem) is None
    assert compras.listar(conexao, outro, 2026, AGORA) == []
    with pytest.raises(compras.ComprasInvalido):
        compras.editar(conexao, outro, ordem, usuario, AGORA, status="cancelada")
