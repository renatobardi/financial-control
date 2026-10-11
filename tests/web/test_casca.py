"""Casca do protótipo: menu lateral com grupos, cabeçalho com BD e papel, item ativo."""

from tests.web.ajuda import entrar, semear

TELAS = {
    "/": ("visao", "Visão geral"),
    "/orcamento": ("orcamento", "Orçamento (PDD)"),
    "/realizado": ("realizado", "Realizado"),
    "/forecast": ("forecast", "Forecast"),
    "/pessoas": ("pessoas", "Pessoas"),
    "/compras": ("compras", "Compras (OC/OS)"),
    "/cadastros": ("cadastros", "Cadastros"),
    "/cargas": ("cargas", "Cargas"),
    "/fechamento": ("fechamento", "Fechamento mensal"),
    "/configuracoes": ("configuracoes", "Configurações"),
}


def test_toda_tela_logada_tem_menu_lateral_com_os_tres_grupos(ambiente):
    semear(ambiente, bds=(("Mobility", "Admin"),))
    entrar(ambiente)

    for caminho in TELAS:
        html = ambiente.cliente.get(caminho).text
        assert 'id="menu-lateral"' in html, caminho
        for grupo in ("Financeiro", "Consumo", "Operação"):
            assert grupo in html, (caminho, grupo)
        for _, rotulo in TELAS.values():
            assert rotulo in html, (caminho, rotulo)


def test_o_item_da_tela_atual_vem_marcado_como_ativo(ambiente):
    semear(ambiente, bds=(("Mobility", "Admin"),))
    entrar(ambiente)

    for caminho in TELAS:
        html = ambiente.cliente.get(caminho).text
        ativos = html.count("aria-current=page")
        assert ativos == 1, (caminho, ativos)
        assert f'href="{caminho}" aria-current=page' in html, caminho


def test_cabecalho_mostra_bd_papel_e_o_menu_do_usuario(ambiente):
    semear(ambiente, bds=(("Mobility", "Editor"),))
    entrar(ambiente)

    html = ambiente.cliente.get("/orcamento").text

    assert "Mobility" in html and "Editor" in html
    assert "Ana" in html and "ana@empresa.com" in html
    assert 'action="/sair"' in html
    assert "somente leitura" not in html


def test_leitor_ve_a_marca_de_somente_leitura(ambiente):
    semear(ambiente, bds=(("Mobility", "Leitor"),))
    entrar(ambiente)

    assert "somente leitura" in ambiente.cliente.get("/").text


def test_base_de_valor_so_aparece_nas_telas_que_a_usam(ambiente):
    semear(ambiente, bds=(("Mobility", "Admin"),))
    entrar(ambiente)

    assert 'href="?base=liquido"' in ambiente.cliente.get("/realizado").text
    assert 'href="?base=liquido"' not in ambiente.cliente.get("/cargas").text
