"""Volume esperado (entrevista de intent, #1): 200 pessoas por mês, 30 temas, 20 demandas,
10 iniciativas e 20 cenários. Cada bloco deve carregar em até 20 segundos."""

import time
from datetime import UTC, datetime

import pytest

from financeiro import cenarios, fechamento, forecast, orcamento, realizado, senha
from financeiro.store import acesso, cadastros, organizacao, portfolio

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
LIMITE_SEGUNDOS = 20.0


@pytest.fixture(scope="module")
def volume():
    from financeiro import store

    conexao = store.abrir(":memory:")
    store.migrar(conexao, store.PASTA_MIGRACOES)
    bd = acesso.criar_bd(conexao, "BD Volume", "BV")
    usuario = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", senha.gerar_hash("x"))
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "Tribo", None, "G", "2025-01")
    squads = [
        organizacao.criar_org(conexao, bd, "Squad", f"Squad {i}", tribo, "G", "2025-01")
        for i in range(8)
    ]
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    cargos = []
    for i, nivel in enumerate(("N8", "N9", "N10", "N11")):
        cargo = cadastros.criar_cargo(conexao, bd, empresa, f"Cargo {i}", nivel)
        cadastros.definir_tarifa(conexao, bd, cargo, 12000 + i * 2500, "2026-01")
        cargos.append(cargo)
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")
    agrupamentos = [portfolio.criar_agrupamento(conexao, bd, f"Agrup {i}") for i in range(4)]
    iniciativas = [portfolio.criar_iniciativa(conexao, bd, f"I-{i}", f"Ini {i}") for i in range(10)]
    demandas = []
    for i in range(20):
        demandas.append(
            portfolio.criar_demanda(
                conexao,
                bd,
                f"D-{i}",
                iniciativas[i % 10],
                f"Dem {i}",
                "CAPEX" if i % 2 else "OPEX",
                squads[i % 8],
            )  # fmt: skip
        )
    temas = [
        portfolio.criar_tema(
            conexao, bd, f"T-{i}", demandas[i % 20], f"Tema {i}", agrupamentos[i % 4]
        )
        for i in range(30)
    ]
    for i in range(200):
        conexao.execute(
            "INSERT INTO pessoa (bd_id, matricula, nome, org_id, cargo_id, tema_id, admissao)"
            " VALUES (?, ?, ?, ?, ?, ?, '2025-01')",
            (bd, f"F{i:04d}", f"Pessoa {i}", squads[i % 8], cargos[i % 4], temas[i % 30]),
        )
    pessoas_ids = [r[0] for r in conexao.execute("SELECT id FROM pessoa ORDER BY id")]
    for i, pessoa in enumerate(pessoas_ids):
        for mes in range(1, 10):
            conexao.execute(
                "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (?, ?, ?, ?, ?)",
                (bd, pessoa, temas[i % 30], f"2026-{mes:02d}", 120 + (i % 40)),
            )
    for i in range(60):
        conexao.execute(
            "INSERT INTO compra (bd_id, numero, tipo, demanda_id, status) VALUES (?, ?, 'OC', ?, 'emitida')",
            (bd, f"OC{i:04d}", demandas[i % 20]),
        )
    for compra in [r[0] for r in conexao.execute("SELECT id FROM compra")]:
        for mes in range(1, 13):
            conexao.execute(
                "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
                " VALUES (?, ?, ?, 250000)",
                (bd, compra, f"2026-{mes:02d}"),
            )
    conexao.commit()
    for mes in range(1, 7):
        fechamento.fechar(conexao, bd, f"2026-{mes:02d}", usuario, AGORA)
    rev = orcamento.nova_revisao(conexao, bd, AGORA)
    for ini in iniciativas:
        orcamento.definir_linha(conexao, bd, rev.id, ini, "CAPEX", 900_000_000)
    orcamento.aprovar(conexao, bd, rev.id, AGORA)
    for i in range(20):
        cenarios.criar(
            conexao, bd, f"Cenário {i}", 9000 + i * 100, 9000 + i * 150,
            trimestres=15, escala_tipo="PDD", elemento_tipo="Agrupamento",
        )  # fmt: skip
    return conexao, bd


def _medir(funcao):
    inicio = time.perf_counter()
    resultado = funcao()
    return resultado, time.perf_counter() - inicio


def test_cada_cenario_calcula_resumo_e_composicao_em_ate_20_segundos(volume):
    conexao, bd = volume

    for cenario in cenarios.listar(conexao, bd):
        _, t_resumo = _medir(
            lambda c=cenario: forecast.resumo(conexao, bd, 2026, c, "bruto", AGORA)
        )
        _, t_comp = _medir(
            lambda c=cenario: forecast.composicao(conexao, bd, 2026, c, "bruto", AGORA)
        )
        assert t_resumo <= LIMITE_SEGUNDOS, cenario.nome
        assert t_comp <= LIMITE_SEGUNDOS, cenario.nome


def test_realizado_por_dimensao_no_volume_em_ate_20_segundos(volume):
    conexao, bd = volume

    for dimensao in ("iniciativa", "tema", "agrupamento", "squad", "origem"):
        _, tempo = _medir(
            lambda d=dimensao: realizado.consultar(conexao, bd, 2026, d, "todas", "bruto", AGORA)
        )
        assert tempo <= LIMITE_SEGUNDOS, dimensao


def test_o_volume_tem_o_tamanho_esperado(volume):
    conexao, bd = volume

    assert conexao.execute("SELECT COUNT(*) FROM pessoa").fetchone()[0] == 200
    assert conexao.execute("SELECT COUNT(*) FROM tema").fetchone()[0] == 30
    assert conexao.execute("SELECT COUNT(*) FROM demanda").fetchone()[0] == 20
    assert conexao.execute("SELECT COUNT(*) FROM iniciativa").fetchone()[0] == 10
    assert len(cenarios.listar(conexao, bd)) == 20
