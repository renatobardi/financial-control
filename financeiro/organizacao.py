"""Organização BD → Tribo → Squad, com gestor, vigência e histórico de reorganização."""

from dataclasses import dataclass, field

from financeiro import vigencia
from financeiro.store import Conexao, ErroDeIntegridade, organizacao


class OrganizacaoInvalida(Exception):
    """A operação quebra a árvore: tipo errado, nome repetido ou nó de outro BD."""


@dataclass
class No:
    id: int
    nome: str
    gestor: str
    inicio: str
    fim: str | None
    squads: list["No"] = field(default_factory=list)


def _achar(conexao: Conexao, bd_id: int, org_id: int, tipo: str | None = None):
    org = organizacao.achar_org(conexao, bd_id, org_id)
    if org is None or (tipo is not None and org.tipo != tipo):
        raise OrganizacaoInvalida(f"{tipo or 'nó'} {org_id} não existe neste BD")
    return org


def _criar(conexao, bd_id, tipo, nome, pai_id, gestor, inicio) -> int:
    vigencia.validar_mes(inicio)
    try:
        return organizacao.criar_org(conexao, bd_id, tipo, nome.strip(), pai_id, gestor, inicio)
    except ErroDeIntegridade as erro:
        conexao.rollback()
        raise OrganizacaoInvalida(f"nome já existe neste BD: {nome}") from erro


def criar_tribo(conexao: Conexao, bd_id: int, nome: str, gestor: str, inicio: str) -> int:
    return _criar(conexao, bd_id, "Tribo", nome, None, gestor, inicio)


def criar_squad(
    conexao: Conexao, bd_id: int, nome: str, tribo_id: int, gestor: str, inicio: str
) -> int:
    _achar(conexao, bd_id, tribo_id, "Tribo")
    return _criar(conexao, bd_id, "Squad", nome, tribo_id, gestor, inicio)


def reorganizar(conexao: Conexao, bd_id: int, squad_id: int, nova_tribo_id: int, mes: str) -> None:
    """Move o squad para outra tribo e deixa o registro no histórico dele."""
    vigencia.validar_mes(mes)
    squad = _achar(conexao, bd_id, squad_id, "Squad")
    nova = _achar(conexao, bd_id, nova_tribo_id, "Tribo")
    if squad.pai_id == nova.id:
        raise OrganizacaoInvalida("o squad já está nesta tribo")
    antiga = _achar(conexao, bd_id, squad.pai_id, "Tribo")
    organizacao.mover_org(conexao, bd_id, squad_id, nova.id)
    organizacao.registrar_historico(
        conexao,
        bd_id,
        squad_id,
        mes,
        f"reorganização: veio de {antiga.nome} para {nova.nome}",
    )


def trocar_gestor(conexao: Conexao, bd_id: int, org_id: int, gestor: str, mes: str) -> None:
    vigencia.validar_mes(mes)
    org = _achar(conexao, bd_id, org_id)
    organizacao.alterar_gestor(conexao, bd_id, org_id, gestor)
    organizacao.registrar_historico(
        conexao, bd_id, org_id, mes, f"gestor: {org.gestor} para {gestor}"
    )


def historico(conexao: Conexao, bd_id: int, org_id: int) -> list[tuple[str, str]]:
    return organizacao.historico(conexao, bd_id, org_id)


def arvore(conexao: Conexao, bd_id: int) -> list[No]:
    """Tribos do BD, cada uma com os seus squads, na ordem de criação."""
    orgs = organizacao.listar_orgs(conexao, bd_id)
    tribos = {o.id: No(o.id, o.nome, o.gestor, o.inicio, o.fim) for o in orgs if o.tipo == "Tribo"}
    for o in orgs:
        if o.tipo == "Squad" and o.pai_id in tribos:
            tribos[o.pai_id].squads.append(No(o.id, o.nome, o.gestor, o.inicio, o.fim))
    return list(tribos.values())
