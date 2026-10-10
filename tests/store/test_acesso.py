import sqlite3

import pytest

from financeiro.store import acesso


def test_usuario_e_achado_por_email_sem_diferenciar_caixa(conexao):
    acesso.criar_usuario(conexao, "Ana@Empresa.com", "Ana", "hash")

    achado = acesso.achar_usuario_por_email(conexao, "ana@empresa.com")

    assert achado is not None
    assert (achado.email, achado.nome) == ("Ana@Empresa.com", "Ana")


def test_email_repetido_e_recusado(conexao):
    acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")

    with pytest.raises(sqlite3.IntegrityError):
        acesso.criar_usuario(conexao, "ANA@empresa.com", "Outra", "h")


def test_usuario_tem_papeis_diferentes_em_bds_diferentes(conexao):
    o1 = acesso.criar_bd(conexao, "Operações 1", "O1")
    bd2 = acesso.criar_bd(conexao, "BD 2", "B2")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")
    acesso.adicionar_membro(conexao, o1, ana, "Admin")
    acesso.adicionar_membro(conexao, bd2, ana, "Leitor")

    assert acesso.papel_do(conexao, o1, ana) == "Admin"
    assert acesso.papel_do(conexao, bd2, ana) == "Leitor"
    assert [(b.nome, b.papel) for b in acesso.bds_do_usuario(conexao, ana)] == [
        ("Operações 1", "Admin"),
        ("BD 2", "Leitor"),
    ]


def test_papel_fora_de_admin_editor_leitor_e_recusado(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")

    with pytest.raises(sqlite3.IntegrityError):
        acesso.adicionar_membro(conexao, bd, ana, "Dono")


def test_sem_vinculo_nao_ha_papel(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")

    assert acesso.papel_do(conexao, bd, ana) is None


def test_membros_do_bd_nao_trazem_membros_de_outro_bd(conexao):
    a = acesso.criar_bd(conexao, "A", "A")
    b = acesso.criar_bd(conexao, "B", "B")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")
    bia = acesso.criar_usuario(conexao, "bia@empresa.com", "Bia", "h")
    acesso.adicionar_membro(conexao, a, ana, "Admin")
    acesso.adicionar_membro(conexao, b, bia, "Editor")

    assert [m.email for m in acesso.membros_do_bd(conexao, a)] == ["ana@empresa.com"]
    assert [m.email for m in acesso.membros_do_bd(conexao, b)] == ["bia@empresa.com"]


def test_alterar_e_remover_papel_so_no_bd_informado(conexao):
    a = acesso.criar_bd(conexao, "A", "A")
    b = acesso.criar_bd(conexao, "B", "B")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")
    acesso.adicionar_membro(conexao, a, ana, "Leitor")
    acesso.adicionar_membro(conexao, b, ana, "Leitor")

    acesso.alterar_papel(conexao, a, ana, "Editor")
    acesso.remover_membro(conexao, b, ana)

    assert acesso.papel_do(conexao, a, ana) == "Editor"
    assert acesso.papel_do(conexao, b, ana) is None
