from datetime import UTC, datetime, timedelta

import pytest

from financeiro import autenticacao, senha
from financeiro.store import acesso

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def conexao(conexao):
    acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", senha.gerar_hash("correta-123"))
    return conexao


def test_entrar_com_credenciais_certas_devolve_token_e_sessao(conexao):
    token, sessao = autenticacao.entrar(conexao, "ana@empresa.com", "correta-123", AGORA)

    assert len(token) >= 32
    assert sessao.csrf
    assert autenticacao.sessao_do_token(conexao, token, AGORA) == sessao


def test_senha_errada_e_email_inexistente_dao_o_mesmo_erro(conexao):
    with pytest.raises(autenticacao.CredenciaisInvalidas):
        autenticacao.entrar(conexao, "ana@empresa.com", "errada", AGORA)
    with pytest.raises(autenticacao.CredenciaisInvalidas):
        autenticacao.entrar(conexao, "ninguem@empresa.com", "qualquer", AGORA)


def test_conta_pendente_de_convite_nao_entra(conexao):
    acesso.criar_usuario(conexao, "novo@empresa.com", "novo", None)

    with pytest.raises(autenticacao.CredenciaisInvalidas):
        autenticacao.entrar(conexao, "novo@empresa.com", "", AGORA)


def test_limite_bloqueia_depois_do_corte_mesmo_com_a_senha_certa(conexao):
    for _ in range(3):
        with pytest.raises(autenticacao.CredenciaisInvalidas):
            autenticacao.entrar(conexao, "ana@empresa.com", "errada", AGORA, max_tentativas=3)

    with pytest.raises(autenticacao.LimiteExcedido):
        autenticacao.entrar(conexao, "ana@empresa.com", "correta-123", AGORA, max_tentativas=3)


def test_limite_vale_por_janela_e_zera_no_sucesso(conexao):
    for _ in range(2):
        with pytest.raises(autenticacao.CredenciaisInvalidas):
            autenticacao.entrar(conexao, "ana@empresa.com", "errada", AGORA, max_tentativas=3)
    # sucesso antes do corte zera a contagem
    autenticacao.entrar(conexao, "ana@empresa.com", "correta-123", AGORA, max_tentativas=3)
    for _ in range(2):
        with pytest.raises(autenticacao.CredenciaisInvalidas):
            autenticacao.entrar(conexao, "ana@empresa.com", "errada", AGORA, max_tentativas=3)

    # fora da janela, as tentativas antigas não contam
    depois = AGORA + timedelta(minutes=16)
    token, _ = autenticacao.entrar(
        conexao, "ana@empresa.com", "correta-123", depois, max_tentativas=3
    )
    assert token


def test_sessao_expira(conexao):
    token, _ = autenticacao.entrar(conexao, "ana@empresa.com", "correta-123", AGORA)

    assert autenticacao.sessao_do_token(conexao, token, AGORA + timedelta(hours=7)) is not None
    assert autenticacao.sessao_do_token(conexao, token, AGORA + timedelta(hours=9)) is None


def test_sair_apaga_a_sessao(conexao):
    token, _ = autenticacao.entrar(conexao, "ana@empresa.com", "correta-123", AGORA)

    autenticacao.sair(conexao, token)

    assert autenticacao.sessao_do_token(conexao, token, AGORA) is None


def test_token_nao_fica_guardado_em_claro(conexao):
    token, _ = autenticacao.entrar(conexao, "ana@empresa.com", "correta-123", AGORA)

    guardados = [r[0] for r in conexao.execute("SELECT token_hash FROM sessao")]

    assert token not in guardados


def test_cookie_assinado_recusa_adulteracao():
    segredo = b"segredo-de-teste"
    valor = autenticacao.assinar("abc123", segredo)

    assert autenticacao.abrir_assinatura(valor, segredo) == "abc123"
    assert autenticacao.abrir_assinatura(valor + "x", segredo) is None
    assert autenticacao.abrir_assinatura(valor, b"outro") is None
    assert autenticacao.abrir_assinatura("semponto", segredo) is None
