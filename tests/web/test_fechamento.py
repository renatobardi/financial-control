from financeiro import fechamento
from financeiro.store import acesso
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Editor"):
    _, ids = semear(ambiente, bds=(("O1", papel),))
    entrar(ambiente)
    return ids["O1"], csrf_de(ambiente.cliente.get("/configuracoes").text)


def _acao(ambiente, csrf, mes, acao, **dados):
    return ambiente.cliente.post(f"/fechamento/{mes}/{acao}", data={"csrf": csrf, **dados})


def test_fechamento_sem_sessao_devolve_401(ambiente):
    assert ambiente.cliente.get("/fechamento").status_code == 401
    assert ambiente.cliente.get("/fechamento/grade").status_code == 401
    assert ambiente.cliente.post("/fechamento/2026-01/fechar", data={}).status_code == 401


def test_pagina_carrega_a_grade_do_ano_por_fragmento(ambiente):
    _preparar(ambiente)

    pagina = ambiente.cliente.get("/fechamento?ano=2026")
    grade = ambiente.cliente.get("/fechamento/grade?ano=2026")

    assert 'hx-get="/fechamento/grade?ano=2026"' in pagina.text
    assert "jan/2026" in grade.text and "dez/2026" in grade.text
    assert "Fechar jan/2026" in grade.text
    assert "Fechar fev/2026" not in grade.text


def test_editor_fecha_o_mes_e_o_log_mostra_autor_e_hora(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _acao(ambiente, csrf, "2026-01", "fechar", ano="2026")

    assert resposta.status_code == 200
    assert "jan/2026 fechado." in resposta.text
    assert "Fechado" in resposta.text
    assert "Ana" in resposta.text and "10/10/2026 12:00" in resposta.text
    assert "Fechar fev/2026" in resposta.text


def test_fechar_fora_de_ordem_devolve_409_com_mensagem(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _acao(ambiente, csrf, "2026-03", "fechar", ano="2026")

    assert resposta.status_code == 409
    assert "Feche antes" in resposta.text


def test_reabrir_exige_motivo_e_vale_so_para_o_ultimo_mes(ambiente):
    bd, csrf = _preparar(ambiente)
    _acao(ambiente, csrf, "2026-01", "fechar", ano="2026")
    _acao(ambiente, csrf, "2026-02", "fechar", ano="2026")

    sem_motivo = _acao(ambiente, csrf, "2026-02", "reabrir", ano="2026", motivo=" ")
    nao_ultimo = _acao(ambiente, csrf, "2026-01", "reabrir", ano="2026", motivo="x")
    ok = _acao(ambiente, csrf, "2026-02", "reabrir", ano="2026", motivo="erro de carga")

    assert sem_motivo.status_code == 409 and "Informe o motivo" in sem_motivo.text
    assert nao_ultimo.status_code == 409 and "último mês fechado" in nao_ultimo.text
    assert ok.status_code == 200 and "erro de carga" in ok.text
    assert fechamento.meses_fechados(ambiente.conexao, bd) == ["2026-01"]


def test_leitor_ve_a_grade_mas_nao_fecha(ambiente):
    bd, csrf = _preparar(ambiente, "Leitor")

    grade = ambiente.cliente.get("/fechamento/grade?ano=2026")
    resposta = _acao(ambiente, csrf, "2026-01", "fechar", ano="2026")

    assert grade.status_code == 200 and "Fechar jan/2026" not in grade.text
    assert "Seu papel neste BD é Leitor" in grade.text
    assert resposta.status_code == 403
    assert fechamento.meses_fechados(ambiente.conexao, bd) == []


def test_fechamento_de_um_bd_nao_aparece_em_outro(ambiente):
    bd, csrf = _preparar(ambiente)
    _acao(ambiente, csrf, "2026-01", "fechar", ano="2026")
    ambiente.cliente.cookies.clear()
    semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("B2", "Admin"),))
    entrar(ambiente, "bia@empresa.com")

    grade = ambiente.cliente.get("/fechamento/grade?ano=2026")

    assert "Fechado" not in grade.text
    assert "Ana" not in grade.text
    assert acesso.achar_usuario_por_email(ambiente.conexao, "bia@empresa.com")
    assert bd


def test_carga_em_mes_fechado_e_rejeitada_pela_tela_de_cargas(ambiente):
    bd, csrf = _preparar(ambiente)
    _cadastros(ambiente, bd)
    _acao(ambiente, csrf, "2026-01", "fechar", ano="2026")
    texto = "matricula;tema_codigo;ano;mes;horas\nF0101;T-10;2026;1;100\nF0101;T-10;2026;2;100\n"

    resposta = ambiente.cliente.post(
        "/cargas",
        data={"csrf": csrf, "layout": "horas"},
        files={"arquivo": ("horas.csv", texto.encode(), "text/csv")},
    )

    assert resposta.status_code == 200
    assert "MES_FECHADO" in resposta.text
    assert "jan/2026 está fechado" in resposta.text
    assert ambiente.conexao.execute("SELECT mes FROM alocacao").fetchall() == [("2026-02",)]
