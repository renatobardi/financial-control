"""Sessões ativas em Configurações: listar e encerrar (#54)."""

from datetime import timedelta

from financeiro import autenticacao
from financeiro.store import acesso
from tests.web.ajuda import csrf_de, entrar, semear


def _outra_sessao(ambiente, email="ana@empresa.com", agente="Firefox no Linux", ip="203.0.113.7"):
    token, _ = autenticacao.entrar(
        ambiente.conexao, email, "correta-123", ambiente.relogio(), agente=agente, ip=ip
    )
    return token


def _pagina(ambiente):
    return ambiente.cliente.get("/configuracoes?aba=sessoes").text


def _csrf(ambiente):
    return csrf_de(ambiente.cliente.get("/configuracoes").text)


def _ids_de_encerrar(html):
    import re

    return re.findall(r"/configuracoes/sessoes/(\d+)/encerrar", html)


def test_login_guarda_o_dispositivo_e_o_ip_e_a_aba_lista_com_a_atual_marcada(ambiente):
    semear(ambiente)
    ambiente.cliente.post(
        "/login",
        data={"email": "ana@empresa.com", "senha": "correta-123"},
        headers={"User-Agent": "Safari no macOS", "X-Real-IP": "198.51.100.9"},
    )
    _outra_sessao(ambiente)

    html = _pagina(ambiente)

    assert "Safari no macOS" in html and "198.51.100.9" in html
    assert "Firefox no Linux" in html and "203.0.113.7" in html
    assert html.count("Esta sessão") == 1
    assert len(_ids_de_encerrar(html)) == 1  # só a outra tem botão


def test_encerrar_outra_sessao_invalida_o_token_dela(ambiente):
    semear(ambiente)
    entrar(ambiente)
    token = _outra_sessao(ambiente)
    (id_,) = _ids_de_encerrar(_pagina(ambiente))

    resposta = ambiente.cliente.post(
        f"/configuracoes/sessoes/{id_}/encerrar", data={"csrf": _csrf(ambiente)}
    )

    assert resposta.status_code == 200
    assert autenticacao.sessao_do_token(ambiente.conexao, token, ambiente.relogio()) is None
    assert _ids_de_encerrar(_pagina(ambiente)) == []


def test_a_sessao_atual_nao_se_encerra_por_aqui(ambiente):
    semear(ambiente)
    entrar(ambiente)
    linha = ambiente.conexao.execute("SELECT id FROM sessao").fetchone()[0]

    resposta = ambiente.cliente.post(
        f"/configuracoes/sessoes/{linha}/encerrar", data={"csrf": _csrf(ambiente)}
    )

    assert resposta.status_code == 400
    assert ambiente.cliente.get("/configuracoes").status_code == 200


def test_sessao_de_outro_usuario_e_404_e_nao_muda(ambiente):
    semear(ambiente)
    semear(ambiente, email="bia@empresa.com", nome="Bia")
    token_bia = _outra_sessao(ambiente, email="bia@empresa.com")
    entrar(ambiente)
    alheia = ambiente.conexao.execute(
        "SELECT s.id FROM sessao s JOIN usuario u ON u.id = s.usuario_id WHERE u.email = %s",
        ("bia@empresa.com",),
    ).fetchone()[0]

    resposta = ambiente.cliente.post(
        f"/configuracoes/sessoes/{alheia}/encerrar", data={"csrf": _csrf(ambiente)}
    )

    assert resposta.status_code == 404
    assert autenticacao.sessao_do_token(ambiente.conexao, token_bia, ambiente.relogio())


def test_encerrar_todas_as_outras_mantem_a_atual_e_as_dos_demais(ambiente):
    semear(ambiente)
    semear(ambiente, email="bia@empresa.com", nome="Bia")
    token_bia = _outra_sessao(ambiente, email="bia@empresa.com")
    entrar(ambiente)
    t1, t2 = _outra_sessao(ambiente), _outra_sessao(ambiente)

    resposta = ambiente.cliente.post(
        "/configuracoes/sessoes/encerrar-outras", data={"csrf": _csrf(ambiente)}
    )

    assert resposta.status_code == 200
    for token in (t1, t2):
        assert autenticacao.sessao_do_token(ambiente.conexao, token, ambiente.relogio()) is None
    assert autenticacao.sessao_do_token(ambiente.conexao, token_bia, ambiente.relogio())
    assert ambiente.cliente.get("/configuracoes").status_code == 200


def test_sessao_expirada_nao_aparece(ambiente):
    semear(ambiente)
    entrar(ambiente)
    _outra_sessao(ambiente, agente="Navegador antigo")
    ambiente.relogio.avancar(days=40)
    ambiente.cliente.cookies.clear()
    entrar(ambiente)

    assert "Navegador antigo" not in _pagina(ambiente)


def test_exige_sessao_e_csrf(ambiente):
    semear(ambiente)

    sem_login = ambiente.cliente.post("/configuracoes/sessoes/encerrar-outras", data={})
    entrar(ambiente)
    sem_csrf = ambiente.cliente.post("/configuracoes/sessoes/encerrar-outras", data={})

    assert sem_login.status_code == 401
    assert sem_csrf.status_code == 403
    _ = (timedelta, acesso)
