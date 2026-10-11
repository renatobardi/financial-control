"""Lote 4 da #44: Forecast interativo e Visão geral mais completa."""

import re

from financeiro import cenarios, fechamento, orcamento
from financeiro.store import cadastros, portfolio
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Admin"):
    """Ana (R$ 193,00/h, 10%): 100 h em jan (fechado) e 50 h em fev; compra de R$ 1.000 em fev."""
    _, ids = semear(ambiente, bds=(("O1", papel),))
    bd = ids["O1"]
    c = ambiente.conexao
    tema, _ = _cadastros(ambiente, bd)
    cargo = c.execute("SELECT id FROM cargo").fetchone()[0]
    pessoa = c.execute("SELECT id FROM pessoa").fetchone()[0]
    demanda = portfolio.listar_demandas(c, bd)[0].id
    cadastros.definir_tarifa(c, bd, cargo, 19300, "2026-01")
    cadastros.definir_markup(c, bd, 1000, "2026-01")
    for mes, horas in (("2026-01", 100), ("2026-02", 50)):
        c.execute(
            "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (?, ?, ?, ?, ?)",
            (bd, pessoa, tema, mes, horas),
        )
    c.execute(
        "INSERT INTO compra (bd_id, numero, tipo, demanda_id, status) VALUES (?, 'OC1', 'OC', ?, 'emitida')",
        (bd, demanda),
    )
    compra = c.execute("SELECT id FROM compra").fetchone()[0]
    c.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (?, ?, '2026-02', 100000)",
        (bd, compra),
    )
    c.commit()
    entrar(ambiente)
    usuario = c.execute("SELECT id FROM usuario").fetchone()[0]
    agora = ambiente.relogio()
    fechamento.fechar(c, bd, "2026-01", usuario, agora)
    rev = orcamento.nova_revisao(c, bd, agora)
    ini = portfolio.listar_iniciativas(c, bd)[0].id
    orcamento.definir_linha(c, bd, rev.id, ini, "CAPEX", 50_000_000)
    orcamento.aprovar(c, bd, rev.id, agora)
    cenarios.garantir_padrao(c, bd)
    return bd, csrf_de(ambiente.cliente.get("/configuracoes").text)


# ---- Forecast ----


def test_forecast_tem_tres_cartoes_de_quanto_falta(ambiente):
    _preparar(ambiente)

    painel = ambiente.cliente.get("/forecast/painel").text

    for rotulo in ("Escala", "Incluído", "Ainda falta alocar"):
        assert rotulo in painel, rotulo
    assert 'data-uso="' in painel  # barra de uso da escala


def test_clicar_no_bloco_abre_o_detalhe_com_contagens_e_situacao(ambiente):
    bd, csrf = _preparar(ambiente)
    base = cenarios.listar(ambiente.conexao, bd)[0]
    painel = ambiente.cliente.get(f"/forecast/painel?cenario={base.id}").text
    chave = re.search(r'name="chave" value="([^"]+)"', painel).group(1)

    detalhe = ambiente.cliente.get(f"/forecast/painel?cenario={base.id}&detalhe={chave}").text

    assert "Detalhe" in detalhe
    for rotulo in ("Demandas", "OC/OS", "Vagas", "Realizado", "Forecast"):
        assert rotulo in detalhe, rotulo
    assert "Incluir no cenário" in detalhe


def test_blocos_do_treemap_sao_clicaveis_e_a_bandeja_arrastavel(ambiente):
    bd, csrf = _preparar(ambiente)
    base = cenarios.listar(ambiente.conexao, bd)[0]
    painel = ambiente.cliente.get(f"/forecast/painel?cenario={base.id}").text
    chave = re.search(r'name="chave" value="([^"]+)"', painel).group(1)
    ambiente.cliente.post(
        f"/forecast/cenarios/{base.id}/incluir", data={"csrf": csrf, "chave": chave}
    )

    incluido = ambiente.cliente.get(f"/forecast/painel?cenario={base.id}").text

    assert 'draggable="true"' in painel or 'draggable="true"' in incluido
    assert f"detalhe={chave}" in incluido  # o bloco leva ao detalhe


def test_origem_da_escala_e_botao_voltar_ao_padrao(ambiente):
    bd, csrf = _preparar(ambiente)
    cid = cenarios.criar(ambiente.conexao, bd, "Manual", 10000, 10000, escala_valor=7_000_000)

    painel = ambiente.cliente.get(f"/forecast/painel?cenario={cid}").text

    assert "Valor simulado neste cenário" in painel
    assert "Voltar ao padrão" in painel


# ---- cores do tema nos gráficos ----


def test_graficos_usam_as_cores_de_grafico_do_tema(ambiente):
    _preparar(ambiente)

    curva = ambiente.cliente.get("/visao-geral/curva").text
    painel = ambiente.cliente.get("/forecast/painel").text

    assert "var(--chart-" in curva
    assert "var(--chart-" in painel


def test_css_define_as_cores_de_grafico_claro_e_escuro(ambiente):
    css = ambiente.cliente.get("/static/app.css")
    # o CSS compilado só existe na imagem; o input é a fonte
    from pathlib import Path

    fonte = (Path(__file__).parents[2] / "financeiro/web/styles/input.css").read_text()
    for n in range(1, 6):
        assert f"--chart-{n}:" in fonte
        assert f"--color-chart-{n}:" in fonte
    assert css.status_code in (200, 404)


# ---- Visão geral ----


def test_visao_tem_chips_de_contexto(ambiente):
    _preparar(ambiente)

    chips = ambiente.cliente.get("/visao-geral/contexto").text

    for rotulo in ("Fechado até", "PDD", "Forecast · cenário", "Última carga"):
        assert rotulo in chips, rotulo
    assert "jan/2026" in chips  # fechado até


def test_visao_tem_faixa_de_pessoas(ambiente):
    _preparar(ambiente)

    faixa = ambiente.cliente.get("/visao-geral/pessoas").text

    for rotulo in ("Ativos", "Funcionários", "Terceiros", "Vagas abertas", "Custo de pessoas"):
        assert rotulo in faixa, rotulo


def test_alertas_trazem_tag_e_atalho_para_a_tela(ambiente):
    _preparar(ambiente)

    alertas = ambiente.cliente.get("/visao-geral/alertas").text

    assert 'data-tag="' in alertas
    assert 'href="/fechamento"' in alertas or 'href="/orcamento"' in alertas


def test_composicao_mostra_capex_opex_e_agrupamento(ambiente):
    _preparar(ambiente)

    risco = ambiente.cliente.get("/visao-geral/risco").text

    for rotulo in ("CAPEX", "Pessoas", "Compras", "RTB"):
        assert rotulo in risco, rotulo


def test_top5_mostra_tipo_e_percentual_projetado(ambiente):
    _preparar(ambiente)

    risco = ambiente.cliente.get("/visao-geral/risco").text

    assert "Alfa" in risco and "projetado" in risco
    assert 'data-selo="capex"' in risco
