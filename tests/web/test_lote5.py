"""Lote 5 da #44: edição inline no PDD e edição de campos nos Cadastros."""

from financeiro import orcamento
from financeiro.store import cadastros, portfolio
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Admin"):
    _, ids = semear(ambiente, bds=(("O1", papel),))
    bd = ids["O1"]
    c = ambiente.conexao
    _cadastros(ambiente, bd)
    cadastros.definir_markup(c, bd, 1000, "2026-01")
    entrar(ambiente)
    return bd, csrf_de(ambiente.cliente.get("/configuracoes").text)


def _postar(ambiente, csrf, aba, acao, **dados):
    return ambiente.cliente.post(f"/cadastros/{aba}/{acao}", data={"csrf": csrf, **dados})


# ---- PDD ----


def test_linha_do_rascunho_tem_edicao_inline_do_valor(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao
    rev = orcamento.nova_revisao(c, bd, ambiente.relogio())
    ini = portfolio.listar_iniciativas(c, bd)[0].id
    orcamento.definir_linha(c, bd, rev.id, ini, "CAPEX", 100_000)

    tabela = ambiente.cliente.get("/orcamento/tabela").text

    assert f'hx-post="/orcamento/{rev.id}/linhas"' in tabela
    assert 'name="valor" value="1.000,00"' in tabela  # o campo já vem com o valor atual


def test_comparar_vem_com_a_revisao_anterior_e_mostra_linha_removida(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao
    agora = ambiente.relogio()
    ini = portfolio.listar_iniciativas(c, bd)[0].id
    original = orcamento.nova_revisao(c, bd, agora)
    orcamento.definir_linha(c, bd, original.id, ini, "CAPEX", 100_000)
    orcamento.definir_linha(c, bd, original.id, ini, "OPEX", 50_000)
    orcamento.aprovar(c, bd, original.id, agora)
    t1 = orcamento.nova_revisao(c, bd, agora)
    orcamento.remover_linha(c, bd, t1.id, ini, "OPEX")
    orcamento.definir_linha(c, bd, t1.id, ini, "CAPEX", 120_000)

    padrao = ambiente.cliente.get(f"/orcamento/tabela?rev={t1.id}").text
    sem = ambiente.cliente.get(f"/orcamento/tabela?rev={t1.id}&comparar=0").text

    assert "Δ vs Original" in padrao
    assert "removida" in padrao  # a linha OPEX que existia na Original
    assert "+" in padrao  # Δ de CAPEX com sinal
    assert "Δ vs" not in sem


def test_nova_revisao_so_aparece_sem_rascunho(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao
    rev = orcamento.nova_revisao(c, bd, ambiente.relogio())

    com_rascunho = ambiente.cliente.get("/orcamento/tabela").text
    orcamento.aprovar(c, bd, rev.id, ambiente.relogio())
    sem_rascunho = ambiente.cliente.get("/orcamento/tabela").text

    assert 'action="/orcamento/revisoes"' not in com_rascunho
    assert 'action="/orcamento/revisoes"' in sem_rascunho


def test_total_do_pdd_mostra_liquido_e_percentual_capex_opex(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao
    ini = portfolio.listar_iniciativas(c, bd)[0].id
    rev = orcamento.nova_revisao(c, bd, ambiente.relogio())
    orcamento.definir_linha(c, bd, rev.id, ini, "CAPEX", 75_000)
    orcamento.definir_linha(c, bd, rev.id, ini, "OPEX", 25_000)

    tabela = ambiente.cliente.get("/orcamento/tabela").text

    assert "75% CAPEX · 25% OPEX" in tabela


# ---- Cadastros ----


def test_editar_tipo_da_empresa_e_nivel_do_cargo(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao
    empresa = cadastros.listar_empresas(c, bd)[0]
    cargo = cadastros.listar_cargos(c, bd)[0]

    _postar(ambiente, csrf, "empresas", "editar", id=str(empresa.id), tipo="consultoria")
    _postar(ambiente, csrf, "cargos", "editar", id=str(cargo.id), nivel="N11")

    assert cadastros.listar_empresas(c, bd)[0].tipo == "consultoria"
    assert cadastros.achar_cargo(c, bd, cargo.id).nivel == "N11"


def test_editar_demanda_tipo_e_iniciativa_e_tema_agrupamento(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao
    outra = portfolio.criar_iniciativa(c, bd, "I-99", "Outra")
    agrup = portfolio.criar_agrupamento(c, bd, "Gravity")
    demanda = portfolio.listar_demandas(c, bd)[0]
    tema = portfolio.listar_temas(c, bd)[0]

    r1 = _postar(
        ambiente, csrf, "demandas", "editar",
        id=str(demanda.id), tipo="OPEX", iniciativa_id=str(outra),
    )  # fmt: skip
    r2 = _postar(ambiente, csrf, "temas", "editar", id=str(tema.id), agrupamento_id=str(agrup))

    assert r1.status_code == 200 and r2.status_code == 200
    d = portfolio.listar_demandas(c, bd)[0]
    assert (d.tipo, d.iniciativa) == ("OPEX", "Outra")
    assert portfolio.listar_temas(c, bd)[0].agrupamento == "Gravity"


def test_editar_cadastro_de_outro_bd_nao_muda_nada(ambiente):
    bd, csrf = _preparar(ambiente)
    from financeiro.store import acesso

    outro = acesso.criar_bd(ambiente.conexao, "Outro", "OT")
    alheia = cadastros.criar_empresa(ambiente.conexao, outro, "NTT", "consultoria")

    _postar(ambiente, csrf, "empresas", "editar", id=str(alheia), tipo="propria")

    assert cadastros.listar_empresas(ambiente.conexao, outro)[0].tipo == "consultoria"


def test_cargo_novo_ja_nasce_com_tarifa(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao
    empresa = cadastros.listar_empresas(c, bd)[0].id

    resposta = _postar(
        ambiente, csrf, "cargos", "nova",
        empresa_id=str(empresa), nome="Master", nivel="N10", valor="250,00", a_partir_de="2026-01",
    )  # fmt: skip

    assert resposta.status_code == 200
    novo = next(x for x in cadastros.listar_cargos(c, bd) if x.nome == "Master")
    assert cadastros.tarifa_vigente(c, bd, novo.id, "2026-03").liquida_centavos == 25000


def test_editar_o_markup_vigente(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao

    resposta = _postar(ambiente, csrf, "markup", "editar", percentual="11,5")

    assert resposta.status_code == 200
    assert cadastros.markup_vigente(c, bd, "2026-06").centesimos_pct == 1150
    assert len(cadastros.listar_markups(c, bd)) == 1  # editou o vigente, não criou outro


def test_aba_markup_explica_o_efeito_da_edicao(ambiente):
    _preparar(ambiente)

    lista = ambiente.cliente.get("/cadastros/markup/lista").text

    assert "meses fechados ficam congelados" in lista
