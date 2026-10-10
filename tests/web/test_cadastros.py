import html

from financeiro.store import acesso, cadastros, portfolio
from financeiro.store import organizacao as arvore_org
from tests.web.ajuda import csrf_de, entrar, semear


def _preparar(ambiente, papel="Admin"):
    semear(ambiente, bds=(("O1", papel),))
    entrar(ambiente)
    pagina = ambiente.cliente.get("/cadastros")
    return csrf_de(ambiente.cliente.get("/configuracoes").text), pagina


def _postar(ambiente, csrf, aba, acao, **dados):
    return ambiente.cliente.post(f"/cadastros/{aba}/{acao}", data={"csrf": csrf, **dados})


def test_cadastros_sem_sessao_devolve_401(ambiente):
    assert ambiente.cliente.get("/cadastros").status_code == 401
    assert ambiente.cliente.get("/cadastros/empresas/lista").status_code == 401
    assert ambiente.cliente.post("/cadastros/empresas/nova", data={"nome": "x"}).status_code == 401


def test_pagina_tem_as_11_abas_e_carrega_a_aba_por_fragmento(ambiente):
    _, pagina = _preparar(ambiente)

    for aba in (
        "organizacao",
        "iniciativas",
        "demandas",
        "temas",
        "agrupamentos",
        "empresas",
        "cargos",
        "fornecedores",
        "vagas",
        "markup",
        "calendario",
    ):
        assert f'href="/cadastros?aba={aba}"' in pagina.text
    assert 'hx-get="/cadastros/organizacao/lista"' in pagina.text
    assert 'hx-trigger="load"' in pagina.text


def test_aba_inexistente_devolve_404(ambiente):
    _preparar(ambiente)

    assert ambiente.cliente.get("/cadastros?aba=nada").status_code == 404
    assert ambiente.cliente.get("/cadastros/nada/lista").status_code == 404


def test_cada_aba_renderiza_o_fragmento(ambiente):
    _preparar(ambiente)

    for aba in (
        "organizacao",
        "iniciativas",
        "demandas",
        "temas",
        "agrupamentos",
        "empresas",
        "cargos",
        "fornecedores",
        "vagas",
        "markup",
        "calendario",
    ):
        resposta = ambiente.cliente.get(f"/cadastros/{aba}/lista")
        assert resposta.status_code == 200, aba
        assert 'id="aba-conteudo"' in resposta.text


def test_editor_cria_empresa_e_cargo_e_nova_tarifa_aparece_na_lista(ambiente):
    csrf, _ = _preparar(ambiente, "Editor")

    _postar(ambiente, csrf, "empresas", "nova", nome="NTT", tipo="consultoria")
    empresa = cadastros.listar_empresas(ambiente.conexao, 1)[0].id
    _postar(ambiente, csrf, "cargos", "nova", empresa_id=str(empresa), nome="Dev Pleno", nivel="N8")
    cargo = cadastros.listar_cargos(ambiente.conexao, 1)[0].id
    resposta = _postar(
        ambiente,
        csrf,
        "cargos",
        "tarifa",
        cargo_id=str(cargo),
        valor="135,00",
        a_partir_de="2026-01",
    )

    assert resposta.status_code == 200
    assert "Nova tarifa criada" in resposta.text
    assert cadastros.tarifa_vigente(ambiente.conexao, 1, cargo, "2026-03").liquida_centavos == 13500


def test_tarifa_retroativa_devolve_409_com_mensagem(ambiente):
    csrf, _ = _preparar(ambiente)
    _postar(ambiente, csrf, "empresas", "nova", nome="NTT", tipo="consultoria")
    empresa = cadastros.listar_empresas(ambiente.conexao, 1)[0].id
    _postar(ambiente, csrf, "cargos", "nova", empresa_id=str(empresa), nome="Dev", nivel="N8")
    cargo = str(cadastros.listar_cargos(ambiente.conexao, 1)[0].id)
    _postar(
        ambiente, csrf, "cargos", "tarifa", cargo_id=cargo, valor="135,00", a_partir_de="2026-02"
    )

    resposta = _postar(
        ambiente, csrf, "cargos", "tarifa", cargo_id=cargo, valor="120,00", a_partir_de="2026-01"
    )

    assert resposta.status_code == 409
    assert "A vigência começa antes ou junto da vigente" in resposta.text


def test_valor_invalido_devolve_400(ambiente):
    csrf, _ = _preparar(ambiente)

    resposta = _postar(ambiente, csrf, "markup", "novo", percentual="dez", a_partir_de="2026-01")

    assert resposta.status_code == 400


def test_markup_novo_encerra_o_anterior(ambiente):
    csrf, _ = _preparar(ambiente)

    _postar(ambiente, csrf, "markup", "novo", percentual="10,5", a_partir_de="2025-01")
    resposta = _postar(ambiente, csrf, "markup", "novo", percentual="10,9", a_partir_de="2026-02")

    assert resposta.status_code == 200
    assert "10,50%" in resposta.text and "10,90%" in resposta.text
    assert "2026-01" in resposta.text  # fim do anterior


def test_leitor_ve_a_lista_mas_nao_ve_formularios_e_nao_grava(ambiente):
    csrf, _ = _preparar(ambiente, "Leitor")
    lista = ambiente.cliente.get("/cadastros/empresas/lista")

    resposta = _postar(ambiente, csrf, "empresas", "nova", nome="NTT", tipo="consultoria")

    assert lista.status_code == 200
    assert "Seu papel neste BD é Leitor" in lista.text
    assert 'action="/cadastros/empresas/nova"' not in lista.text
    assert resposta.status_code == 403
    assert cadastros.listar_empresas(ambiente.conexao, 1) == []


def test_lista_e_paginada_de_10_em_10_e_busca(ambiente):
    csrf, _ = _preparar(ambiente)
    for i in range(1, 13):
        _postar(ambiente, csrf, "fornecedores", "nova", nome=f"Fornecedor {i:02d}")

    primeira = ambiente.cliente.get("/cadastros/fornecedores/lista").text
    segunda = ambiente.cliente.get("/cadastros/fornecedores/lista?pagina=2").text
    busca = ambiente.cliente.get("/cadastros/fornecedores/lista?q=11").text

    assert "Fornecedor 10" in primeira and "Fornecedor 11" not in primeira
    assert "Fornecedor 11" in segunda and "Fornecedor 12" in segunda
    assert "Página 1 de 2" in primeira
    assert "Fornecedor 11" in busca and "Fornecedor 01" not in busca


def test_cadastro_de_um_bd_nao_aparece_em_outro(ambiente):
    csrf, _ = _preparar(ambiente)
    _postar(ambiente, csrf, "fornecedores", "nova", nome="Fornecedor Secreto")
    ambiente.cliente.cookies.clear()
    semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("B2", "Admin"),))
    entrar(ambiente, "bia@empresa.com")

    lista = ambiente.cliente.get("/cadastros/fornecedores/lista")

    assert "Fornecedor Secreto" not in lista.text


def test_renomear_nao_altera_registro_de_outro_bd(ambiente):
    csrf, _ = _preparar(ambiente)
    outro = acesso.criar_bd(ambiente.conexao, "Outro", "OT")
    _postar(ambiente, csrf, "iniciativas", "nova", codigo="I-01", nome="Minha")
    alheia = portfolio.criar_iniciativa(ambiente.conexao, outro, "I-99", "Alheia")

    _postar(ambiente, csrf, "iniciativas", "renomear", id=str(alheia), nome="Invadida")

    assert portfolio.listar_iniciativas(ambiente.conexao, outro)[0].nome == "Alheia"


def test_organizacao_cria_tribo_squad_reorganiza_e_troca_gestor(ambiente):
    csrf, _ = _preparar(ambiente)
    _postar(
        ambiente, csrf, "organizacao", "tribo", nome="Tribo D&C", gestor="Renato", inicio="2025-01"
    )
    _postar(
        ambiente, csrf, "organizacao", "tribo", nome="Tribo Pay", gestor="Marina", inicio="2025-01"
    )
    orgs = {o.nome: o.id for o in arvore_org.listar_orgs(ambiente.conexao, 1)}
    _postar(
        ambiente,
        csrf,
        "organizacao",
        "squad",
        nome="Squad Risk",
        tribo_id=str(orgs["Tribo Pay"]),
        gestor="G",
        inicio="2025-01",
    )
    squad = {o.nome: o.id for o in arvore_org.listar_orgs(ambiente.conexao, 1)}["Squad Risk"]

    resposta = _postar(
        ambiente,
        csrf,
        "organizacao",
        "reorganizar",
        squad_id=str(squad),
        tribo_id=str(orgs["Tribo D&C"]),
        mes="2026-07",
    )

    assert resposta.status_code == 200
    assert "reorganização: veio de Tribo Pay para Tribo D&C" in html.unescape(resposta.text)


def test_calendario_gera_o_ano_e_mostra_as_horas(ambiente):
    csrf, _ = _preparar(ambiente)

    resposta = _postar(ambiente, csrf, "calendario", "gerar", ano="2026")

    assert resposta.status_code == 200
    assert "jan/2026" in resposta.text and "168" in resposta.text  # 21 dias úteis x 8 h
