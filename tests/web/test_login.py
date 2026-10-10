from tests.web.ajuda import csrf_de, entrar, semear


def test_raiz_sem_sessao_leva_ao_login(ambiente):
    resposta = ambiente.cliente.get("/")

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


def test_pagina_de_login_tem_os_campos_e_o_texto_do_catalogo(ambiente):
    html = ambiente.cliente.get("/login").text

    assert 'name="email"' in html and 'name="senha"' in html
    assert "Entrar" in html


def test_login_certo_com_um_bd_entra_direto_e_mostra_o_bd(ambiente):
    semear(ambiente, bds=(("O1", "Admin"),))

    resposta = entrar(ambiente)

    assert resposta.status_code == 303 and resposta.headers["location"] == "/"
    inicio = ambiente.cliente.get("/")
    assert inicio.status_code == 200
    assert "O1" in inicio.text and "Ana" in inicio.text


def test_cookie_de_sessao_e_httponly_secure_e_samesite(ambiente):
    semear(ambiente)

    cookie = entrar(ambiente).headers["set-cookie"].lower()

    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie


def test_senha_errada_devolve_401_sem_cookie(ambiente):
    semear(ambiente)

    resposta = entrar(ambiente, senha_="errada")

    assert resposta.status_code == 401
    assert "E-mail ou senha incorretos." in resposta.text
    assert "set-cookie" not in resposta.headers


def test_limite_de_tentativas_bloqueia_com_429(ambiente):
    semear(ambiente)
    for _ in range(3):
        assert entrar(ambiente, senha_="errada").status_code == 401

    resposta = entrar(ambiente)

    assert resposta.status_code == 429
    assert "Muitas tentativas" in resposta.text


def test_dois_bds_levam_a_escolha_e_a_escolha_vale(ambiente):
    _, ids = semear(ambiente, bds=(("O1", "Admin"), ("B2", "Leitor")))

    assert entrar(ambiente).headers["location"] == "/bds"
    pagina = ambiente.cliente.get("/bds")
    assert "O1" in pagina.text and "B2" in pagina.text
    resposta = ambiente.cliente.post(f"/bds/{ids['B2']}", data={"csrf": csrf_de(pagina.text)})

    assert resposta.status_code == 303
    assert "B2" in ambiente.cliente.get("/").text


def test_nao_escolhe_bd_de_que_nao_e_membro(ambiente):
    semear(ambiente, bds=(("O1", "Admin"), ("B2", "Leitor")))
    _, ids = semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("Secreto", "Admin"),))
    entrar(ambiente)
    csrf = csrf_de(ambiente.cliente.get("/bds").text)

    resposta = ambiente.cliente.post(f"/bds/{ids['Secreto']}", data={"csrf": csrf})

    assert resposta.status_code == 403


def test_rotas_protegidas_sem_sessao_devolvem_401(ambiente):
    assert ambiente.cliente.get("/bds").status_code == 401
    assert ambiente.cliente.post("/bds/1", data={"csrf": "x"}).status_code == 401
    assert ambiente.cliente.post("/sair", data={"csrf": "x"}).status_code == 401


def test_post_sem_csrf_devolve_403(ambiente):
    semear(ambiente)
    entrar(ambiente)

    assert ambiente.cliente.post("/sair", data={}).status_code == 403
    assert ambiente.cliente.post("/sair", data={"csrf": "errado"}).status_code == 403


def test_sair_encerra_a_sessao(ambiente):
    semear(ambiente)
    entrar(ambiente)
    csrf = csrf_de(ambiente.cliente.get("/").text)

    resposta = ambiente.cliente.post("/sair", data={"csrf": csrf})

    assert resposta.status_code == 303 and resposta.headers["location"] == "/login"
    assert ambiente.cliente.get("/").headers["location"] == "/login"


def test_cookie_adulterado_nao_autentica(ambiente):
    semear(ambiente)
    entrar(ambiente)
    nome, valor = next(iter(ambiente.cliente.cookies.items()))
    ambiente.cliente.cookies.set(nome, valor + "x")

    assert ambiente.cliente.get("/").headers["location"] == "/login"


def test_sessao_expirada_nao_autentica(ambiente):
    semear(ambiente)
    entrar(ambiente)
    ambiente.relogio.avancar(hours=9)

    assert ambiente.cliente.get("/").headers["location"] == "/login"
