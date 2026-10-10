from financeiro.store import acesso, cadastros, organizacao, pessoas, portfolio
from tests.web.ajuda import csrf_de, entrar, semear

HORAS = "matricula;tema_codigo;ano;mes;horas\n"


def _cadastros(ambiente, bd_id):
    c = ambiente.conexao
    tribo = organizacao.criar_org(c, bd_id, "Tribo", "Tribo", None, "G", "2025-01")
    squad = organizacao.criar_org(c, bd_id, "Squad", "Squad", tribo, "G", "2025-01")
    empresa = cadastros.criar_empresa(c, bd_id, "Própria", "propria")
    cargo = cadastros.criar_cargo(c, bd_id, empresa, "Sênior", "N9")
    agrup = portfolio.criar_agrupamento(c, bd_id, "RTB")
    ini = portfolio.criar_iniciativa(c, bd_id, "I-01", "Alfa")
    dem = portfolio.criar_demanda(c, bd_id, "D-1", ini, "Dem", "CAPEX", squad)
    tema = portfolio.criar_tema(c, bd_id, "T-10", dem, "Tema", agrup)
    tema2 = portfolio.criar_tema(c, bd_id, "T-11", dem, "Tema 2", agrup)
    pessoas.criar_pessoa(c, bd_id, "F0101", "Ana Lima", squad, cargo, tema, "2025-01", None)
    return tema, tema2


def _preparar(ambiente, papel="Editor"):
    _, ids = semear(ambiente, bds=(("O1", papel),))
    _cadastros(ambiente, ids["O1"])
    entrar(ambiente)
    csrf = csrf_de(ambiente.cliente.get("/configuracoes").text)
    return ids["O1"], csrf


def _enviar(ambiente, csrf, texto, layout="horas", acao="", nome="horas.csv", conteudo=None):
    arquivos = {"arquivo": (nome, conteudo if conteudo is not None else texto.encode(), "text/csv")}
    return ambiente.cliente.post(
        f"/cargas{acao}", data={"csrf": csrf, "layout": layout}, files=arquivos
    )


def _alocacoes(ambiente):
    return ambiente.conexao.execute("SELECT COUNT(*) FROM alocacao").fetchone()[0]


def test_cargas_sem_sessao_devolve_401(ambiente):
    assert ambiente.cliente.get("/cargas").status_code == 401
    assert ambiente.cliente.get("/cargas/historico").status_code == 401
    assert ambiente.cliente.post("/cargas", data={"layout": "horas"}).status_code == 401


def test_pagina_lista_os_seis_layouts_e_carrega_o_historico_por_fragmento(ambiente):
    _preparar(ambiente)

    pagina = ambiente.cliente.get("/cargas").text

    for layout in ("horas", "compras", "pdd", "pessoas", "tarifas", "portfolio"):
        assert f'value="{layout}"' in pagina
        assert f"/cargas/modelo/{layout}.csv" in pagina
    assert 'hx-get="/cargas/historico"' in pagina


def test_baixar_modelo_traz_o_cabecalho_do_layout(ambiente):
    _preparar(ambiente)

    resposta = ambiente.cliente.get("/cargas/modelo/horas.csv")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/csv")
    assert resposta.content.decode("utf-8-sig").strip() == "matricula;tema_codigo;ano;mes;horas"
    assert ambiente.cliente.get("/cargas/modelo/xpto.csv").status_code == 404


def test_pre_validacao_mostra_o_relatorio_sem_gravar(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _enviar(
        ambiente, csrf, HORAS + "F0101;T-10;2026;9;120\nF9999;T-10;2026;9;1\n", acao="/validar"
    )

    assert resposta.status_code == 200
    assert "Pré-validação: nada foi gravado." in resposta.text
    assert "PESSOA_INEXISTENTE" in resposta.text
    assert _alocacoes(ambiente) == 0
    assert ambiente.conexao.execute("SELECT COUNT(*) FROM carga").fetchone()[0] == 0


def test_carregar_grava_e_o_historico_mostra_as_contagens(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _enviar(ambiente, csrf, HORAS + "F0101;T-10;2026;9;120\nF9999;T-10;2026;9;1\n")

    assert resposta.status_code == 200
    assert "1 inseridas, 0 atualizadas, 0 sem mudança, 1 rejeitadas" in resposta.text
    assert _alocacoes(ambiente) == 1
    historico = ambiente.cliente.get("/cargas/historico").text
    assert "horas.csv" in historico and "Horas realizadas" in historico and "Ana" in historico


def test_baixar_rejeicoes_em_csv(ambiente):
    _, csrf = _preparar(ambiente)
    _enviar(ambiente, csrf, HORAS + "F9999;T-10;2026;9;1\n")

    resposta = ambiente.cliente.get("/cargas/1/rejeicoes.csv")

    assert resposta.status_code == 200
    texto = resposta.content.decode("utf-8-sig")
    assert "linha;regra;mensagem" in texto and "PESSOA_INEXISTENTE" in texto


def test_arquivo_com_codificacao_errada_devolve_400_sem_gravar(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _enviar(
        ambiente, csrf, "", conteudo=(HORAS + "F0101;Tê-10;2026;9;1\n").encode("latin-1")
    )

    assert resposta.status_code == 400
    assert "UTF-8" in resposta.text
    assert ambiente.conexao.execute("SELECT COUNT(*) FROM carga").fetchone()[0] == 0


def test_separador_inesperado_devolve_400_com_mensagem(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _enviar(
        ambiente, csrf, "matricula\ttema_codigo\tano\tmes\thoras\nF0101\tT-10\t2026\t9\t1\n"
    )

    assert resposta.status_code == 400
    assert "Cabeçalho inválido" in resposta.text


def test_desfazer_pela_tela_volta_o_banco(ambiente):
    _, csrf = _preparar(ambiente)
    _enviar(ambiente, csrf, HORAS + "F0101;T-10;2026;9;120\n")
    assert _alocacoes(ambiente) == 1

    resposta = ambiente.cliente.post("/cargas/1/desfazer", data={"csrf": csrf})

    assert resposta.status_code == 200
    assert "Carga #1 desfeita." in resposta.text
    assert _alocacoes(ambiente) == 0


def test_leitor_ve_o_historico_mas_nao_envia_nem_desfaz(ambiente):
    _, csrf = _preparar(ambiente, "Leitor")

    pagina = ambiente.cliente.get("/cargas").text
    envio = _enviar(ambiente, csrf, HORAS + "F0101;T-10;2026;9;1\n")
    desfazer = ambiente.cliente.post("/cargas/1/desfazer", data={"csrf": csrf})

    assert "Seu papel neste BD é Leitor" in pagina
    assert 'action="/cargas"' not in pagina
    assert envio.status_code == 403 and desfazer.status_code == 403


def test_aprovar_horas_extras_so_o_admin(ambiente):
    # set/2026 tem 168 h de capacidade: 120 + 90 = 210 h pendentes de aprovação
    _, csrf = _preparar(ambiente, "Editor")
    texto = HORAS + "F0101;T-10;2026;9;120\nF0101;T-11;2026;9;90\n"
    relatorio = _enviar(ambiente, csrf, texto)
    assert "HORAS_ACIMA_CAL" in relatorio.text and "Aprovar horas extras" not in relatorio.text
    grupo = "F0101|2026-09"

    negado = ambiente.cliente.post("/cargas/1/aprovar", data={"csrf": csrf, "grupo": grupo})

    assert negado.status_code == 403
    assert _alocacoes(ambiente) == 0
    ambiente.conexao.execute("UPDATE membro SET papel = 'Admin'")
    ambiente.conexao.commit()
    aprovado = ambiente.cliente.post("/cargas/1/aprovar", data={"csrf": csrf, "grupo": grupo})
    assert aprovado.status_code == 200
    assert "Horas extras aprovadas: 210h gravadas." in aprovado.text
    assert _alocacoes(ambiente) == 2


def test_carga_de_um_bd_nao_aparece_nem_se_desfaz_em_outro(ambiente):
    _, csrf = _preparar(ambiente)
    _enviar(ambiente, csrf, HORAS + "F0101;T-10;2026;9;120\n")
    ambiente.cliente.cookies.clear()
    semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("B2", "Admin"),))
    entrar(ambiente, "bia@empresa.com")
    csrf_bia = csrf_de(ambiente.cliente.get("/configuracoes").text)

    historico = ambiente.cliente.get("/cargas/historico").text
    desfazer = ambiente.cliente.post("/cargas/1/desfazer", data={"csrf": csrf_bia})
    detalhe = ambiente.cliente.get("/cargas/1")

    assert "horas.csv" not in historico
    assert desfazer.status_code == 404 and detalhe.status_code == 404
    assert _alocacoes(ambiente) == 1
    assert acesso.achar_usuario_por_email(ambiente.conexao, "bia@empresa.com")
