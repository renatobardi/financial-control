"""Verificação em duas etapas (TOTP) no login e em Configurações (#54)."""

import re

from financeiro import totp
from financeiro.store import acesso, segundo_fator
from tests.web.ajuda import csrf_de, entrar, semear

SENHA = "correta-123"


def _csrf(ambiente):
    return csrf_de(ambiente.cliente.get("/configuracoes").text)


def _ativar(ambiente):
    """Entra, ativa o 2FA pela tela e devolve (segredo, códigos de recuperação)."""
    entrar(ambiente)
    csrf = _csrf(ambiente)
    inicio = ambiente.cliente.post("/configuracoes/2fa/iniciar", data={"csrf": csrf})
    segredo = re.search(r'data-segredo="([A-Z2-7]+)"', inicio.text).group(1)
    codigo = totp.codigo(segredo, totp.passo_de(ambiente.relogio()))
    ok = ambiente.cliente.post(
        "/configuracoes/2fa/confirmar", data={"csrf": csrf, "codigo": codigo}
    )
    codigos = re.findall(r'data-recuperacao="([0-9a-f]{5}-[0-9a-f]{5})"', ok.text)
    ambiente.cliente.post("/sair", data={"csrf": csrf})
    ambiente.cliente.cookies.clear()
    ambiente.relogio.avancar(seconds=31)  # o passo do código de ativação não vale de novo
    return segredo, codigos


def _login(ambiente, senha=SENHA, email="ana@empresa.com"):
    return ambiente.cliente.post("/login", data={"email": email, "senha": senha})


def _desafio(resposta):
    return re.search(r'name="desafio" value="([^"]+)"', resposta.text).group(1)


def _segundo_passo(ambiente, desafio, codigo):
    return ambiente.cliente.post("/login/2fa", data={"desafio": desafio, "codigo": codigo})


def _codigo_agora(ambiente, segredo):
    return totp.codigo(segredo, totp.passo_de(ambiente.relogio()))


def test_ativar_mostra_o_segredo_e_so_ativa_com_um_codigo_valido(ambiente):
    semear(ambiente)
    entrar(ambiente)
    csrf = _csrf(ambiente)

    inicio = ambiente.cliente.post("/configuracoes/2fa/iniciar", data={"csrf": csrf})
    segredo = re.search(r'data-segredo="([A-Z2-7]+)"', inicio.text).group(1)
    errado = ambiente.cliente.post(
        "/configuracoes/2fa/confirmar", data={"csrf": csrf, "codigo": "000000"}
    )

    assert "otpauth://totp/" in inicio.text and segredo in inicio.text
    assert errado.status_code == 400
    usuario = acesso.achar_usuario_por_email(ambiente.conexao, "ana@empresa.com")
    assert segundo_fator.obter(ambiente.conexao, usuario.id).ativo is False


def test_codigo_certo_ativa_e_mostra_oito_codigos_de_recuperacao_uma_vez(ambiente):
    semear(ambiente)

    segredo, codigos = _ativar(ambiente)

    assert len(codigos) == 8 and len(set(codigos)) == 8
    usuario = acesso.achar_usuario_por_email(ambiente.conexao, "ana@empresa.com")
    guardado = segundo_fator.obter(ambiente.conexao, usuario.id)
    assert guardado.ativo is True and guardado.segredo == segredo
    # os códigos não ficam em texto no banco
    dump = " ".join(
        str(linha) for linha in ambiente.conexao.execute("SELECT * FROM codigo_recuperacao")
    )
    assert not any(c in dump for c in codigos)


def test_com_2fa_o_login_so_conclui_com_o_segundo_passo(ambiente):
    semear(ambiente)
    segredo, _ = _autenticado = _ativar(ambiente)

    primeiro = _login(ambiente)
    sem_sessao = ambiente.cliente.get("/configuracoes")
    final = _segundo_passo(ambiente, _desafio(primeiro), _codigo_agora(ambiente, segredo))

    assert primeiro.status_code == 200 and 'name="codigo"' in primeiro.text
    assert sem_sessao.status_code == 401
    assert final.status_code == 303
    assert ambiente.cliente.get("/configuracoes").status_code == 200


def test_codigo_errado_recusa_e_nao_abre_sessao(ambiente):
    semear(ambiente)
    _ativar(ambiente)
    desafio = _desafio(_login(ambiente))

    resposta = _segundo_passo(ambiente, desafio, "123456")

    assert resposta.status_code == 401
    assert ambiente.cliente.get("/configuracoes").status_code == 401


def test_o_mesmo_codigo_nao_vale_duas_vezes(ambiente):
    semear(ambiente)
    segredo, _ = _ativar(ambiente)
    codigo = _codigo_agora(ambiente, segredo)
    primeiro = _segundo_passo(ambiente, _desafio(_login(ambiente)), codigo)
    ambiente.cliente.post("/sair", data={"csrf": _csrf(ambiente)})
    ambiente.cliente.cookies.clear()

    repetido = _segundo_passo(ambiente, _desafio(_login(ambiente)), codigo)

    assert primeiro.status_code == 303
    assert repetido.status_code == 401


def test_codigo_de_recuperacao_entra_uma_vez_so(ambiente):
    semear(ambiente)
    _, codigos = _ativar(ambiente)

    com_codigo = _segundo_passo(ambiente, _desafio(_login(ambiente)), codigos[0])
    ambiente.cliente.post("/sair", data={"csrf": _csrf(ambiente)})
    ambiente.cliente.cookies.clear()
    de_novo = _segundo_passo(ambiente, _desafio(_login(ambiente)), codigos[0])

    assert com_codigo.status_code == 303
    assert de_novo.status_code == 401


def test_chutar_codigos_esbarra_no_limite_de_tentativas_do_login(ambiente):
    semear(ambiente)
    _ativar(ambiente)
    desafio = _desafio(_login(ambiente))

    limite = ambiente.cfg.max_tentativas
    estados = [_segundo_passo(ambiente, desafio, f"{n:06d}").status_code for n in range(limite + 3)]

    assert estados[:limite] == [401] * limite
    assert estados[limite:] == [429] * 3
    assert _login(ambiente).status_code == 429  # nem a senha certa abre mais, até a janela passar


def test_desafio_vencido_ou_adulterado_e_recusado(ambiente):
    semear(ambiente)
    segredo, _ = _ativar(ambiente)
    desafio = _desafio(_login(ambiente))
    codigo = _codigo_agora(ambiente, segredo)

    adulterado = _segundo_passo(ambiente, desafio[:-3] + "abc", codigo)
    ambiente.relogio.avancar(minutes=6)
    vencido = _segundo_passo(ambiente, desafio, _codigo_agora(ambiente, segredo))

    assert adulterado.status_code == 400
    assert vencido.status_code == 400


def test_senha_errada_nem_chega_ao_segundo_passo(ambiente):
    semear(ambiente)
    _ativar(ambiente)

    resposta = _login(ambiente, senha="errada-999")

    assert resposta.status_code == 401 and 'name="desafio"' not in resposta.text


def test_desativar_pede_a_senha(ambiente):
    semear(ambiente)
    segredo, _ = _ativar(ambiente)
    _segundo_passo(ambiente, _desafio(_login(ambiente)), _codigo_agora(ambiente, segredo))
    csrf = _csrf(ambiente)

    errada = ambiente.cliente.post(
        "/configuracoes/2fa/desativar", data={"csrf": csrf, "senha": "x"}
    )
    certa = ambiente.cliente.post(
        "/configuracoes/2fa/desativar", data={"csrf": csrf, "senha": SENHA}
    )

    assert errada.status_code == 400
    assert certa.status_code == 200
    usuario = acesso.achar_usuario_por_email(ambiente.conexao, "ana@empresa.com")
    assert segundo_fator.obter(ambiente.conexao, usuario.id) is None
    ambiente.cliente.post("/sair", data={"csrf": csrf})
    ambiente.cliente.cookies.clear()
    assert _login(ambiente).status_code == 303  # volta a entrar só com a senha


def test_a_aba_seguranca_mostra_o_estado(ambiente):
    semear(ambiente)
    entrar(ambiente)

    desligado = ambiente.cliente.get("/configuracoes?aba=seguranca").text

    assert 'action="/configuracoes/2fa/iniciar"' in desligado
