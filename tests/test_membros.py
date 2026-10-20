import pytest

from financeiro import membros
from financeiro.store import acesso


def _bd_com_admin(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    ana = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")
    acesso.adicionar_membro(conexao, bd, ana, "Admin")
    return bd, ana


def test_ultimo_admin_nao_pode_ser_rebaixado_nem_removido(conexao):
    bd, ana = _bd_com_admin(conexao)

    with pytest.raises(membros.UltimoAdmin):
        membros.alterar_papel(conexao, bd, ana, "Leitor")
    with pytest.raises(membros.UltimoAdmin):
        membros.remover(conexao, bd, ana)

    assert acesso.papel_do(conexao, bd, ana) == "Admin"


def test_com_dois_admins_um_pode_ser_rebaixado(conexao):
    bd, ana = _bd_com_admin(conexao)
    bia, _ = acesso.convidar(conexao, bd, "bia@empresa.com", "Admin")

    membros.alterar_papel(conexao, bd, bia, "Editor")

    assert acesso.papel_do(conexao, bd, bia) == "Editor"


def test_aprovar_pedido_da_o_papel_e_fecha_o_pedido(conexao):
    bd, _ = _bd_com_admin(conexao)
    bia = acesso.criar_usuario(conexao, "bia@empresa.com", "Bia", "h")
    pedido = acesso.criar_pedido(conexao, bd, bia, "preciso", "2026-10-10T12:00:00Z")

    membros.aprovar_pedido(conexao, bd, pedido, "Editor")

    assert acesso.papel_do(conexao, bd, bia) == "Editor"
    assert acesso.pedidos_abertos(conexao, bd) == []


def test_pedido_ja_decidido_nao_e_decidido_de_novo(conexao):
    bd, _ = _bd_com_admin(conexao)
    bia = acesso.criar_usuario(conexao, "bia@empresa.com", "Bia", "h")
    pedido = acesso.criar_pedido(conexao, bd, bia, "preciso", "2026-10-10T12:00:00Z")
    membros.recusar_pedido(conexao, bd, pedido)

    with pytest.raises(membros.PedidoInexistente):
        membros.aprovar_pedido(conexao, bd, pedido, "Admin")

    assert acesso.papel_do(conexao, bd, bia) is None
