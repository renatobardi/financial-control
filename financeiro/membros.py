"""Regras de membros e pedidos de acesso de um BD. Sem SQL: usa `store.acesso`."""

from financeiro.store import Conexao, acesso


class UltimoAdmin(Exception):
    """Todo BD precisa de ao menos um Admin."""


class PedidoInexistente(Exception):
    """O pedido não existe neste BD ou já foi decidido."""


def _protege_ultimo_admin(conexao: Conexao, bd_id: int, usuario_id: int) -> None:
    if (
        acesso.papel_do(conexao, bd_id, usuario_id) == "Admin"
        and acesso.contar_admins(conexao, bd_id) <= 1
    ):
        raise UltimoAdmin(usuario_id)


def alterar_papel(conexao: Conexao, bd_id: int, usuario_id: int, papel: str) -> None:
    if papel != "Admin":
        _protege_ultimo_admin(conexao, bd_id, usuario_id)
    acesso.alterar_papel(conexao, bd_id, usuario_id, papel)


def remover(conexao: Conexao, bd_id: int, usuario_id: int) -> None:
    _protege_ultimo_admin(conexao, bd_id, usuario_id)
    acesso.remover_membro(conexao, bd_id, usuario_id)


def _pedido_aberto(conexao: Conexao, bd_id: int, pedido_id: int) -> acesso.Pedido:
    pedido = acesso.achar_pedido(conexao, bd_id, pedido_id)
    if pedido is None or pedido.estado != "aberto":
        raise PedidoInexistente(pedido_id)
    return pedido


def aprovar_pedido(conexao: Conexao, bd_id: int, pedido_id: int, papel: str) -> None:
    pedido = _pedido_aberto(conexao, bd_id, pedido_id)
    acesso.convidar(conexao, bd_id, pedido.email, papel)
    acesso.decidir_pedido(conexao, bd_id, pedido_id, "aprovado")


def recusar_pedido(conexao: Conexao, bd_id: int, pedido_id: int) -> None:
    _pedido_aberto(conexao, bd_id, pedido_id)
    acesso.decidir_pedido(conexao, bd_id, pedido_id, "recusado")
