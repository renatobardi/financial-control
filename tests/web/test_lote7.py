"""Lote 7 da #44: Configurações em abas, BDs (padrão e sair), membros em tabela e excluir conta."""

from financeiro.store import acesso
from tests.web.ajuda import csrf_de, entrar, semear


def _csrf(ambiente):
    return csrf_de(ambiente.cliente.get("/configuracoes").text)


def _post(ambiente, caminho, **dados):
    return ambiente.cliente.post(caminho, data={"csrf": _csrf(ambiente), **dados})


def test_abas_aparecem_e_cada_uma_mostra_so_a_sua_parte(ambiente):
    semear(ambiente)
    entrar(ambiente)

    perfil = ambiente.cliente.get("/configuracoes").text
    membros = ambiente.cliente.get("/configuracoes?aba=membros").text

    for aba in ("perfil", "bds", "membros", "conta"):
        assert f'data-aba="{aba}"' in perfil
    assert 'action="/configuracoes/perfil"' in perfil
    assert 'action="/configuracoes/convites"' not in perfil
    assert 'action="/configuracoes/convites"' in membros
    assert 'action="/configuracoes/perfil"' not in membros


def test_leitor_nao_tem_a_aba_membros(ambiente):
    semear(ambiente, bds=(("O1", "Leitor"),))
    entrar(ambiente)

    pagina = ambiente.cliente.get("/configuracoes").text

    assert 'data-aba="membros"' not in pagina
    assert 'data-aba="conta"' in pagina


def test_membros_em_tabela_com_o_papel_aplicado_na_hora(ambiente):
    semear(ambiente, bds=(("O1", "Admin"),))
    entrar(ambiente)

    pagina = ambiente.cliente.get("/configuracoes?aba=membros").text

    assert "<table" in pagina
    assert 'onchange="this.form.requestSubmit()"' in pagina


def test_tornar_padrao_grava_a_preferencia(ambiente):
    usuario_id, ids = semear(ambiente, bds=(("O1", "Admin"),))
    entrar(ambiente)

    resposta = _post(ambiente, f"/configuracoes/bds/{ids['O1']}/padrao")

    assert resposta.status_code == 200
    assert acesso.achar_usuario(ambiente.conexao, usuario_id).bd_padrao_id == ids["O1"]


def test_sair_do_bd_tira_o_vinculo_e_o_ultimo_admin_nao_sai(ambiente):
    id_usuario, ids = semear(ambiente, bds=(("O1", "Admin"), ("O2", "Editor")))
    entrar(ambiente)

    saiu = _post(ambiente, f"/configuracoes/bds/{ids['O2']}/sair")
    ultimo = _post(ambiente, f"/configuracoes/bds/{ids['O1']}/sair")

    assert saiu.status_code == 200
    assert acesso.papel_do(ambiente.conexao, ids["O2"], id_usuario) is None
    assert ultimo.status_code == 409
    assert acesso.papel_do(ambiente.conexao, ids["O1"], id_usuario) == "Admin"


def test_sair_de_bd_alheio_e_404(ambiente):
    _, ids = semear(ambiente, bds=(("O1", "Admin"),))
    entrar(ambiente)
    outro = acesso.criar_bd(ambiente.conexao, "Outro", "OT")

    assert _post(ambiente, f"/configuracoes/bds/{outro}/sair").status_code == 404
    assert _post(ambiente, f"/configuracoes/bds/{outro}/padrao").status_code == 404


def test_excluir_conta_exige_o_email_e_recusa_o_ultimo_admin(ambiente):
    semear(ambiente, bds=(("O1", "Admin"),))
    entrar(ambiente)

    errado = _post(ambiente, "/configuracoes/conta/excluir", confirmar="outra@exemplo.com")
    ultimo = _post(ambiente, "/configuracoes/conta/excluir", confirmar="ana@empresa.com")

    assert errado.status_code == 400
    assert ultimo.status_code == 409


def test_excluir_conta_encerra_a_sessao_e_impede_novo_login(ambiente):
    _, ids = semear(ambiente, bds=(("O1", "Editor"),))
    entrar(ambiente)

    resposta = _post(ambiente, "/configuracoes/conta/excluir", confirmar="ana@empresa.com")

    assert resposta.status_code in (200, 303)
    assert ambiente.cliente.get("/configuracoes").status_code == 401
    assert acesso.achar_usuario_por_email(ambiente.conexao, "ana@empresa.com") is None
    assert acesso.membros_do_bd(ambiente.conexao, ids["O1"]) == []
