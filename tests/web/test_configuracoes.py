from fastapi import Depends

from financeiro.store import acesso
from financeiro.web.sessao import Contexto, exigir_edicao
from tests.web.ajuda import csrf_de, entrar, semear


def _csrf(ambiente):
    return csrf_de(ambiente.cliente.get("/configuracoes").text)


def _post(ambiente, caminho, **dados):
    return ambiente.cliente.post(caminho, data={"csrf": _csrf(ambiente), **dados})


def test_configuracoes_sem_sessao_devolve_401(ambiente):
    assert ambiente.cliente.get("/configuracoes").status_code == 401
    assert ambiente.cliente.post("/configuracoes/perfil", data={"nome": "x"}).status_code == 401


def test_perfil_altera_o_nome(ambiente):
    semear(ambiente)
    entrar(ambiente)

    resposta = _post(ambiente, "/configuracoes/perfil", nome="Ana Souza")

    assert resposta.status_code == 200
    assert "Ana Souza" in ambiente.cliente.get("/").text


def test_senha_com_atual_errada_ou_curta_ou_diferente_e_recusada(ambiente):
    semear(ambiente)
    entrar(ambiente)

    errada = _post(
        ambiente, "/configuracoes/senha", atual="x", nova="nova-senha-1", confirmar="nova-senha-1"
    )
    curta = _post(
        ambiente, "/configuracoes/senha", atual="correta-123", nova="abc", confirmar="abc"
    )
    diferente = _post(
        ambiente,
        "/configuracoes/senha",
        atual="correta-123",
        nova="nova-senha-1",
        confirmar="outra-senha-1",
    )

    assert (errada.status_code, curta.status_code, diferente.status_code) == (400, 400, 400)
    assert "Senha atual incorreta." in errada.text


def test_senha_alterada_vale_no_proximo_login(ambiente):
    semear(ambiente)
    entrar(ambiente)

    ok = _post(
        ambiente,
        "/configuracoes/senha",
        atual="correta-123",
        nova="nova-senha-1",
        confirmar="nova-senha-1",
    )

    assert ok.status_code == 200
    ambiente.cliente.cookies.clear()
    assert entrar(ambiente, senha_="correta-123").status_code == 401
    assert entrar(ambiente, senha_="nova-senha-1").status_code == 303


def test_preferencia_de_tema_vale_na_tela_seguinte(ambiente):
    semear(ambiente)
    entrar(ambiente)
    assert 'class=""' in ambiente.cliente.get("/").text

    resposta = _post(
        ambiente,
        "/configuracoes/preferencias",
        tema="escuro",
        formato_valor="mi",
        tela_inicial="Forecast",
        bd_padrao_id="",
    )

    assert resposta.status_code == 200
    assert 'class="dark"' in ambiente.cliente.get("/").text


def test_preferencia_invalida_e_recusada(ambiente):
    semear(ambiente)
    entrar(ambiente)

    resposta = _post(
        ambiente,
        "/configuracoes/preferencias",
        tema="neon",
        formato_valor="mil",
        tela_inicial="Forecast",
        bd_padrao_id="",
    )

    assert resposta.status_code == 400


def test_bd_padrao_pula_a_escolha_no_proximo_login(ambiente):
    _, ids = semear(ambiente, bds=(("O1", "Admin"), ("B2", "Leitor")))
    entrar(ambiente)
    ambiente.cliente.post(
        f"/bds/{ids['B2']}", data={"csrf": csrf_de(ambiente.cliente.get("/bds").text)}
    )
    _post(
        ambiente,
        "/configuracoes/preferencias",
        tema="sistema",
        formato_valor="mil",
        tela_inicial="Visão geral",
        bd_padrao_id=str(ids["B2"]),
    )
    ambiente.cliente.cookies.clear()

    assert entrar(ambiente).headers["location"] == "/"
    assert "B2" in ambiente.cliente.get("/").text


def test_leitor_nao_ve_nem_usa_a_administracao(ambiente):
    semear(ambiente, bds=(("O1", "Leitor"),))
    entrar(ambiente)

    pagina = ambiente.cliente.get("/configuracoes").text
    resposta = _post(ambiente, "/configuracoes/convites", email="x@empresa.com", papel="Editor")

    assert 'action="/configuracoes/convites"' not in pagina
    assert resposta.status_code == 403


def test_admin_convida_email_novo_que_cria_a_conta_e_entra_no_bd(ambiente):
    semear(ambiente, bds=(("O1", "Admin"),))
    entrar(ambiente)

    convite = _post(ambiente, "/configuracoes/convites", email="novo@empresa.com", papel="Editor")

    assert convite.status_code == 200
    assert "novo@empresa.com" in convite.text
    ambiente.cliente.cookies.clear()
    conta = ambiente.cliente.post(
        "/conta",
        data={
            "nome": "Novo",
            "email": "novo@empresa.com",
            "senha": "senha-nova-1",
            "confirmar": "senha-nova-1",
        },
    )
    assert conta.status_code == 303
    assert entrar(ambiente, "novo@empresa.com", "senha-nova-1").headers["location"] == "/"
    assert "Editor" in ambiente.cliente.get("/").text


def test_criar_conta_com_email_ja_ativo_e_recusado(ambiente):
    semear(ambiente)

    resposta = ambiente.cliente.post(
        "/conta",
        data={
            "nome": "Outra",
            "email": "ana@empresa.com",
            "senha": "senha-nova-1",
            "confirmar": "senha-nova-1",
        },
    )

    assert resposta.status_code == 409


def test_conta_nova_sem_convite_nao_tem_bd(ambiente):
    semear(ambiente)

    ambiente.cliente.post(
        "/conta",
        data={
            "nome": "Cris",
            "email": "cris@empresa.com",
            "senha": "senha-nova-1",
            "confirmar": "senha-nova-1",
        },
    )
    resposta = entrar(ambiente, "cris@empresa.com", "senha-nova-1")

    assert resposta.headers["location"] == "/"
    assert ambiente.cliente.get("/").headers["location"] == "/bds"
    assert "Você ainda não tem acesso a nenhum BD." in ambiente.cliente.get("/bds").text


def test_ultimo_admin_nao_se_rebaixa(ambiente):
    ana, _ = semear(ambiente, bds=(("O1", "Admin"),))
    entrar(ambiente)

    resposta = _post(ambiente, f"/configuracoes/membros/{ana}/papel", papel="Leitor")

    assert resposta.status_code == 409
    assert acesso.papel_do(ambiente.conexao, 1, ana) == "Admin"


def test_pedido_de_acesso_aprovado_da_o_papel(ambiente):
    semear(ambiente, bds=(("O1", "Admin"),))
    _, ids_bia = semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("B2", "Admin"),))
    # Bia pede acesso ao O1
    entrar(ambiente, "bia@empresa.com")
    o1 = acesso.achar_usuario_por_email(ambiente.conexao, "ana@empresa.com")
    bd_o1 = acesso.bds_do_usuario(ambiente.conexao, o1.id)[0].id
    enviado = _post(ambiente, "/configuracoes/pedido", bd_id=str(bd_o1), motivo="preciso ver o PDD")
    assert enviado.status_code == 200
    # Ana (Admin do O1) aprova
    ambiente.cliente.cookies.clear()
    entrar(ambiente)
    pagina = ambiente.cliente.get("/configuracoes?aba=membros").text
    assert "preciso ver o PDD" in pagina
    pedido_id = acesso.pedidos_abertos(ambiente.conexao, bd_o1)[0].id

    aprovado = _post(ambiente, f"/configuracoes/pedidos/{pedido_id}/aprovar", papel="Leitor")

    assert aprovado.status_code == 200
    bia = acesso.achar_usuario_por_email(ambiente.conexao, "bia@empresa.com")
    assert acesso.papel_do(ambiente.conexao, bd_o1, bia.id) == "Leitor"
    assert ids_bia


def test_admin_de_um_bd_nao_mexe_em_membro_de_outro_bd(ambiente):
    semear(ambiente, bds=(("O1", "Admin"),))
    bia, ids = semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("B2", "Admin"),))
    entrar(ambiente)

    resposta = _post(ambiente, f"/configuracoes/membros/{bia}/papel", papel="Leitor")
    pagina = ambiente.cliente.get("/configuracoes").text

    assert resposta.status_code == 404
    assert acesso.papel_do(ambiente.conexao, ids["B2"], bia) == "Admin"
    assert "bia@empresa.com" not in pagina


def test_exigir_edicao_barra_leitor_com_a_mensagem_do_prototipo(ambiente):
    @ambiente.cliente.app.post("/_teste/editar")
    def editar(contexto: Contexto = Depends(exigir_edicao)):
        return {"ok": True}

    semear(ambiente, bds=(("O1", "Leitor"),))
    entrar(ambiente)
    csrf = _csrf(ambiente)

    resposta = ambiente.cliente.post("/_teste/editar", headers={"X-CSRF-Token": csrf})

    assert resposta.status_code == 403
    assert "Seu papel neste BD é Leitor" in resposta.text


def test_exigir_edicao_deixa_o_editor_passar(ambiente):
    @ambiente.cliente.app.post("/_teste/editar")
    def editar(contexto: Contexto = Depends(exigir_edicao)):
        return {"ok": True}

    semear(ambiente, bds=(("O1", "Editor"),))
    entrar(ambiente)
    csrf = _csrf(ambiente)

    assert (
        ambiente.cliente.post("/_teste/editar", headers={"X-CSRF-Token": csrf}).status_code == 200
    )
