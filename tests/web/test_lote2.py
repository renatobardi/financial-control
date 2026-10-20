"""Lote 2 da #44: valores na preferência do usuário, cartões de resumo e Realizado enxuto."""

import re

from financeiro import compras, fechamento, orcamento
from financeiro.store import cadastros, portfolio
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, formato="mil"):
    """Ana (R$ 193,00/h, 10%): 100 h em jan (fechado) e 50 h em fev. PDD de R$ 500.000,00."""
    _, ids = semear(ambiente, bds=(("O1", "Admin"),))
    bd = ids["O1"]
    c = ambiente.conexao
    tema, _ = _cadastros(ambiente, bd)
    cargo = c.execute("SELECT id FROM cargo").fetchone()[0]
    pessoa = c.execute("SELECT id FROM pessoa").fetchone()[0]
    cadastros.definir_tarifa(c, bd, cargo, 19300, "2026-01")
    cadastros.definir_markup(c, bd, 1000, "2026-01")
    for mes, horas in (("2026-01", 100), ("2026-02", 50)):
        c.execute(
            "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (%s, %s, %s, %s, %s)",
            (bd, pessoa, tema, mes, horas),
        )
    c.execute("UPDATE usuario SET formato_valor = %s", (formato,))
    c.commit()
    entrar(ambiente)
    usuario = c.execute("SELECT id FROM usuario").fetchone()[0]
    agora = ambiente.relogio()
    fechamento.fechar(c, bd, "2026-01", usuario, agora)
    rev = orcamento.nova_revisao(c, bd, agora)
    ini = portfolio.listar_iniciativas(c, bd)[0].id
    orcamento.definir_linha(c, bd, rev.id, ini, "CAPEX", 50_000_000)
    orcamento.definir_linha(c, bd, rev.id, ini, "OPEX", 20_000_000)
    orcamento.aprovar(c, bd, rev.id, agora)
    return bd, usuario, csrf_de(ambiente.cliente.get("/configuracoes").text)


# ---- valores na preferência ----


def test_tabelas_mostram_o_valor_em_mil_e_deixam_o_exato_no_tooltip(ambiente):
    _preparar(ambiente, "mil")

    pdd = ambiente.cliente.get("/orcamento/tabela").text

    assert "R$ 500 mil" in pdd  # CAPEX R$ 500.000,00
    assert 'title="R$ 500.000,00"' in pdd


def test_preferencia_mi_muda_a_unidade_das_tabelas(ambiente):
    _preparar(ambiente, "mi")

    pdd = ambiente.cliente.get("/orcamento/tabela").text

    assert "R$ 0,50 mi" in pdd
    assert "R$ 500 mil" not in pdd


def test_realizado_e_pessoas_tambem_seguem_a_preferencia(ambiente):
    _preparar(ambiente, "mil")

    real = ambiente.cliente.get("/realizado/tabela?ano=2026").text
    pess = ambiente.cliente.get("/pessoas/lista?de=2026-01&ate=2026-12").text

    assert re.search(r"R\$ \d+ mil", real) and re.search(r"R\$ \d+ mil", pess)
    assert 'title="R$ 21.230,00"' in real


# ---- cartões de resumo ----


def test_orcamento_tem_os_quatro_cartoes_do_topo(ambiente):
    _preparar(ambiente)

    pdd = ambiente.cliente.get("/orcamento/tabela").text

    for rotulo in ("Budget bruto", "Budget líquido", "CAPEX bruto", "OPEX bruto"):
        assert rotulo in pdd, rotulo


def test_realizado_tem_cartoes_de_realizado_pessoas_e_compras(ambiente):
    _preparar(ambiente)

    real = ambiente.cliente.get("/realizado/tabela?ano=2026").text

    for rotulo in ("Realizado", "Pessoas", "Compras (OC/OS)"):
        assert rotulo in real, rotulo


# ---- Realizado enxuto ----


def test_realizado_mostra_so_os_meses_fechados_e_a_barra_de_percentual(ambiente):
    _preparar(ambiente)

    real = ambiente.cliente.get("/realizado/tabela?ano=2026").text

    assert "jan/2026" in real
    assert "fev/2026" not in real and "dez/2026" not in real
    assert 'data-barra="' in real  # % do total por linha


def test_realizado_agrupa_por_iniciativa_e_tipo_por_padrao(ambiente):
    _preparar(ambiente)

    real = ambiente.cliente.get("/realizado/tabela?ano=2026").text

    assert "Alfa · CAPEX" in real


# ---- selos e total ----


def test_compras_tem_selo_de_status_e_total_do_filtro(ambiente):
    bd, usuario, _ = _preparar(ambiente)
    demanda = portfolio.listar_demandas(ambiente.conexao, bd)[0].id
    compras.criar_prevista(
        ambiente.conexao, bd, "OC", demanda, "Licenças", usuario, ambiente.relogio()
    )

    lista = ambiente.cliente.get("/compras/lista?ano=2026").text

    assert 'data-selo="prevista"' in lista
    assert "Total do filtro" in lista
