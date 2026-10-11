"""Criar BD pela tela de escolha de BD (#61)."""

from tests.web.ajuda import csrf_de, entrar, semear


def _criar(ambiente, nome, csrf=None):
    csrf = csrf or csrf_de(ambiente.cliente.get("/bds").text)
    return ambiente.cliente.post("/bds", data={"csrf": csrf, "nome": nome})


def test_criar_bd_sem_sessao_devolve_401(ambiente):
    assert ambiente.cliente.post("/bds", data={"csrf": "x", "nome": "Novo"}).status_code == 401


def test_formulario_aparece_com_bds_e_sem_bds(ambiente):
    semear(ambiente, bds=(("Mobility", "Leitor"),))
    entrar(ambiente)
    com_bds = ambiente.cliente.get("/bds").text
    assert 'action="/bds"' in com_bds and 'name="nome"' in com_bds

    ambiente.cliente.cookies.clear()
    semear(ambiente, email="bia@empresa.com", nome="Bia", bds=())
    entrar(ambiente, email="bia@empresa.com")
    sem_bds = ambiente.cliente.get("/bds").text
    assert "Você ainda não tem acesso a nenhum BD." in sem_bds
    assert 'action="/bds"' in sem_bds and 'name="nome"' in sem_bds


def test_quem_nao_tem_bd_cria_o_primeiro_e_cai_no_onboarding(ambiente):
    semear(ambiente, bds=())
    entrar(ambiente)

    resposta = _criar(ambiente, "Crédito")

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"
    primeira = ambiente.cliente.get("/")
    assert primeira.status_code == 303
    assert primeira.headers["location"] == "/onboarding"
    pagina = ambiente.cliente.get("/onboarding")
    assert pagina.status_code == 200
    assert "Crédito" in pagina.text and "Admin" in pagina.text
    assert ambiente.cliente.get("/").status_code == 200  # a abertura é uma vez só


def test_bd_criado_nao_aparece_para_quem_nao_e_membro(ambiente):
    semear(ambiente, bds=())
    entrar(ambiente)
    _criar(ambiente, "Crédito")

    ambiente.cliente.cookies.clear()
    semear(ambiente, email="bia@empresa.com", nome="Bia", bds=())
    entrar(ambiente, email="bia@empresa.com")

    assert "Crédito" not in ambiente.cliente.get("/bds").text


def test_nome_invalido_ou_repetido_volta_com_a_mensagem(ambiente):
    semear(ambiente, bds=(("Mobility", "Admin"),))
    entrar(ambiente)

    vazio = _criar(ambiente, "   ")
    assert vazio.status_code == 400
    assert "Informe o nome do BD (até 60 caracteres)." in vazio.text

    longo = _criar(ambiente, "x" * 61)
    assert longo.status_code == 400

    repetido = _criar(ambiente, "Mobility")
    assert repetido.status_code == 409
    assert "Já existe um BD com esse nome. Escolha outro." in repetido.text


def test_criar_bd_sem_csrf_e_recusado(ambiente):
    semear(ambiente, bds=(("Mobility", "Admin"),))
    entrar(ambiente)

    resposta = ambiente.cliente.post("/bds", data={"csrf": "errado", "nome": "Novo"})

    assert resposta.status_code == 403
