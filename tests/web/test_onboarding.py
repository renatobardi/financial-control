"""Onboarding pela web: tela, papéis, dispensa, item do menu e abertura única."""

import pytest

from financeiro import organizacao
from financeiro.store import cadastros, pessoas, portfolio
from tests.web.ajuda import csrf_de, entrar, semear


def _post(ambiente, caminho, **dados):
    csrf = csrf_de(ambiente.cliente.get("/onboarding").text)
    return ambiente.cliente.post(caminho, data={"csrf": csrf, **dados})


def _configurar_bd(conexao, bd):
    tribo = organizacao.criar_tribo(conexao, bd, "Tribo", "G", "2026-01")
    squad = organizacao.criar_squad(conexao, bd, "Squad", tribo, "G", "2026-01")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-01", "Iniciativa")
    dem = portfolio.criar_demanda(conexao, bd, "D-01", ini, "Demanda", "OPEX", squad)
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    tema = portfolio.criar_tema(conexao, bd, "T-01", dem, "Tema", agrup)
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Pleno", "N8")
    cadastros.definir_tarifa(conexao, bd, cargo, 12000, "2026-01")
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")
    pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo, tema, "2026-01", None)


def test_sem_sessao_devolve_401(ambiente):
    assert ambiente.cliente.get("/onboarding").status_code == 401
    assert ambiente.cliente.get("/onboarding/progresso").status_code == 401
    assert ambiente.cliente.post("/onboarding/compras/dispensar").status_code == 401


@pytest.mark.parametrize("papel", ["Admin", "Editor"])
def test_admin_e_editor_veem_os_onze_passos(ambiente, papel):
    semear(ambiente, bds=(("Mobility", papel),))
    entrar(ambiente)

    resposta = ambiente.cliente.get("/onboarding")

    assert resposta.status_code == 200
    assert resposta.text.count("data-passo=") == 11
    assert 'data-passo="demandas" data-estado="bloqueado"' in resposta.text
    assert 'data-passo="iniciativas" data-estado="pendente"' in resposta.text


def test_leitor_nao_ve_o_onboarding(ambiente):
    semear(ambiente, bds=(("Mobility", "Leitor"),))
    entrar(ambiente)

    assert ambiente.cliente.get("/onboarding").status_code == 403
    assert ambiente.cliente.get("/onboarding/progresso").status_code == 403


def test_item_do_menu_so_aparece_para_admin_e_editor(ambiente):
    _, ids = semear(ambiente, bds=(("Mobility", "Admin"), ("Outro", "Leitor")))
    entrar(ambiente)
    csrf = csrf_de(ambiente.cliente.get("/bds").text)

    ambiente.cliente.post(f"/bds/{ids['Mobility']}", data={"csrf": csrf})
    assert "/onboarding/progresso" in ambiente.cliente.get("/").text

    ambiente.cliente.post(f"/bds/{ids['Outro']}", data={"csrf": csrf})
    assert "/onboarding/progresso" not in ambiente.cliente.get("/").text


def test_progresso_conta_passos_resolvidos_e_destaca_o_item_ativo(ambiente):
    semear(ambiente, bds=(("Mobility", "Admin"),))
    entrar(ambiente)

    assert "0 de 11" in ambiente.cliente.get("/onboarding/progresso").text
    assert _post(ambiente, "/onboarding/calendario/dispensar").status_code == 303

    progresso = ambiente.cliente.get("/onboarding/progresso?ativo=1").text
    assert "1 de 11" in progresso
    assert "Primeiros passos" in progresso
    assert "aria-current=page" in progresso
    assert "aria-current=page" not in ambiente.cliente.get("/onboarding/progresso").text


def test_bd_pronto_renomeia_o_item_e_mostra_os_proximos_passos(ambiente):
    _, ids = semear(ambiente, bds=(("Mobility", "Admin"),))
    entrar(ambiente)
    _configurar_bd(ambiente.conexao, ids["Mobility"])

    pagina = ambiente.cliente.get("/onboarding").text
    progresso = ambiente.cliente.get("/onboarding/progresso").text

    assert "BD pronto para uso" in pagina
    assert 'href="/fechamento"' in pagina
    assert "Configuração do BD" in progresso
    assert "Primeiros passos" not in progresso


def test_editor_dispensa_e_desfaz_passo_opcional(ambiente):
    semear(ambiente, bds=(("Mobility", "Editor"),))
    entrar(ambiente)

    resposta = _post(ambiente, "/onboarding/compras/dispensar")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/onboarding"
    assert 'data-passo="compras" data-estado="nao_se_aplica"' in (
        ambiente.cliente.get("/onboarding").text
    )

    _post(ambiente, "/onboarding/compras/desfazer")
    assert 'data-passo="compras" data-estado="nao_se_aplica"' not in (
        ambiente.cliente.get("/onboarding").text
    )


def test_passo_obrigatorio_nao_e_dispensado_e_passo_desconhecido_nao_existe(ambiente):
    semear(ambiente, bds=(("Mobility", "Admin"),))
    entrar(ambiente)

    assert _post(ambiente, "/onboarding/pessoas/dispensar").status_code == 400
    assert _post(ambiente, "/onboarding/nada/dispensar").status_code == 404


def test_primeiro_admin_do_bd_novo_cai_no_onboarding_uma_vez(ambiente):
    semear(ambiente, bds=(("Mobility", "Admin"),), onboarding_aberto=False)
    entrar(ambiente)

    primeira = ambiente.cliente.get("/")
    assert primeira.status_code == 303
    assert primeira.headers["location"] == "/onboarding"

    assert ambiente.cliente.get("/").status_code == 200


def test_editor_nao_consome_a_abertura_do_primeiro_admin(ambiente):
    semear(ambiente, bds=(("Mobility", "Editor"),), onboarding_aberto=False)
    entrar(ambiente)
    assert ambiente.cliente.get("/").status_code == 200

    ambiente.cliente.cookies.clear()
    semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("Mobility", "Admin"),))
    entrar(ambiente, email="bia@empresa.com")

    assert ambiente.cliente.get("/").headers["location"] == "/onboarding"
