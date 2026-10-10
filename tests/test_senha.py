from financeiro import senha


def test_hash_verifica_a_senha_certa_e_recusa_a_errada():
    h = senha.gerar_hash("correta-123")

    assert senha.verificar("correta-123", h) is True
    assert senha.verificar("errada-123", h) is False


def test_dois_hashes_da_mesma_senha_diferem():
    assert senha.gerar_hash("igual") != senha.gerar_hash("igual")


def test_hash_nao_guarda_a_senha_em_claro():
    assert "correta-123" not in senha.gerar_hash("correta-123")
    assert senha.gerar_hash("x").startswith("scrypt$")


def test_hash_malformado_ou_ausente_nao_autentica():
    assert senha.verificar("qualquer", "lixo") is False
    assert senha.verificar("qualquer", None) is False
