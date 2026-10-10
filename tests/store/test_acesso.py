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


def test_convidar_email_novo_cria_conta_pendente_e_vinculo(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")

    usuario_id, novo = acesso.convidar(conexao, bd, "nova@empresa.com", "Editor")

    assert novo is True
    assert acesso.papel_do(conexao, bd, usuario_id) == "Editor"
    membro = acesso.membros_do_bd(conexao, bd)[0]
    assert membro.pendente is True


def test_convidar_conta_existente_so_da_acesso_ao_bd(conexao):
    a = acesso.criar_bd(conexao, "A", "A")
    b = acesso.criar_bd(conexao, "B", "B")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")
    acesso.adicionar_membro(conexao, a, ana, "Admin")

    usuario_id, novo = acesso.convidar(conexao, b, "ana@empresa.com", "Leitor")

    assert (usuario_id, novo) == (ana, False)
    assert acesso.papel_do(conexao, b, ana) == "Leitor"
    assert acesso.papel_do(conexao, a, ana) == "Admin"


def test_contar_admins_so_do_bd_informado(conexao):
    a = acesso.criar_bd(conexao, "A", "A")
    b = acesso.criar_bd(conexao, "B", "B")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")
    acesso.adicionar_membro(conexao, a, ana, "Admin")
    acesso.adicionar_membro(conexao, b, ana, "Leitor")

    assert acesso.contar_admins(conexao, a) == 1
    assert acesso.contar_admins(conexao, b) == 0


def test_pedido_de_acesso_aparece_so_para_o_bd_pedido_e_pode_ser_decidido(conexao):
    a = acesso.criar_bd(conexao, "A", "A")
    b = acesso.criar_bd(conexao, "B", "B")
    bia = acesso.criar_usuario(conexao, "bia@empresa.com", "Bia", "h")

    pedido = acesso.criar_pedido(conexao, a, bia, "preciso ver o PDD", "2026-10-10T12:00:00Z")

    assert [p.motivo for p in acesso.pedidos_abertos(conexao, a)] == ["preciso ver o PDD"]
    assert acesso.pedidos_abertos(conexao, b) == []
    assert [p.estado for p in acesso.pedidos_do_usuario(conexao, bia)] == ["aberto"]
    acesso.decidir_pedido(conexao, a, pedido, "recusado")
    assert acesso.pedidos_abertos(conexao, a) == []
    assert [p.estado for p in acesso.pedidos_do_usuario(conexao, bia)] == ["recusado"]


def test_bds_sem_vinculo_lista_so_os_que_o_usuario_nao_integra(conexao):
    a = acesso.criar_bd(conexao, "A", "A")
    acesso.criar_bd(conexao, "B", "B")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")
    acesso.adicionar_membro(conexao, a, ana, "Admin")

    assert [b.nome for b in acesso.bds_sem_vinculo(conexao, ana)] == ["B"]


def test_perfil_senha_e_preferencias_sao_gravados(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")

    acesso.atualizar_perfil(conexao, ana, "Ana Souza")
    acesso.definir_senha(conexao, ana, "novo-hash")
    acesso.atualizar_preferencias(conexao, ana, "escuro", "mi", "Forecast", bd)

    u = acesso.achar_usuario(conexao, ana)
    assert (u.nome, u.senha_hash) == ("Ana Souza", "novo-hash")
    assert (u.tema, u.formato_valor, u.tela_inicial, u.bd_padrao_id) == (
        "escuro",
        "mi",
        "Forecast",
        bd,
    )
