"""TOTP (RFC 6238, SHA-1, 6 dígitos, passo de 30 s): vetores do apêndice B da RFC."""

from datetime import UTC, datetime

from financeiro import totp

SEGREDO_RFC = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890" em base32


def _em(segundos: int) -> datetime:
    return datetime.fromtimestamp(segundos, UTC)


def test_codigos_da_rfc_6238():
    # RFC 6238, apêndice B (8 dígitos): 94287082, 07081804, 89005924; aqui os 6 últimos.
    assert totp.codigo(SEGREDO_RFC, totp.passo_de(_em(59))) == "287082"
    assert totp.codigo(SEGREDO_RFC, totp.passo_de(_em(1111111109))) == "081804"
    assert totp.codigo(SEGREDO_RFC, totp.passo_de(_em(1234567890))) == "005924"


def test_verifica_com_tolerancia_de_um_passo_e_devolve_o_passo():
    agora = _em(1111111109)
    passo = totp.passo_de(agora)

    assert totp.verificar(SEGREDO_RFC, "081804", agora, 0) == passo
    assert totp.verificar(SEGREDO_RFC, totp.codigo(SEGREDO_RFC, passo - 1), agora, 0) == passo - 1
    assert totp.verificar(SEGREDO_RFC, totp.codigo(SEGREDO_RFC, passo + 1), agora, 0) == passo + 1
    assert totp.verificar(SEGREDO_RFC, totp.codigo(SEGREDO_RFC, passo + 3), agora, 0) is None
    assert totp.verificar(SEGREDO_RFC, "000000", agora, 0) is None


def test_codigo_ja_usado_nao_vale_de_novo():
    agora = _em(1111111109)
    passo = totp.passo_de(agora)

    assert totp.verificar(SEGREDO_RFC, "081804", agora, passo) is None
    assert totp.verificar(SEGREDO_RFC, "081804", agora, passo - 1) == passo


def test_aceita_espacos_e_recusa_o_que_nao_e_numero():
    agora = _em(1111111109)

    assert totp.verificar(SEGREDO_RFC, "081 804", agora, 0) is not None
    assert totp.verificar(SEGREDO_RFC, "08180a", agora, 0) is None
    assert totp.verificar(SEGREDO_RFC, "", agora, 0) is None


def test_segredo_novo_e_base32_de_160_bits_e_diferente_a_cada_vez():
    a, b = totp.gerar_segredo(), totp.gerar_segredo()

    assert a != b
    assert len(a) == 32 and set(a) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


def test_uri_para_o_aplicativo_autenticador():
    uri = totp.uri("ana@empresa.com", SEGREDO_RFC)

    assert uri.startswith("otpauth://totp/")
    assert f"secret={SEGREDO_RFC}" in uri
    assert "ana%40empresa.com" in uri and "issuer=" in uri
