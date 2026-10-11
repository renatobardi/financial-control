"""Onboarding: o roteiro de configuração de um BD, na ordem em que os cadastros dependem.

Sem SQL: usa `store.onboarding`. O estado de cada passo é derivado dos dados do BD.
"""

from typing import NamedTuple

from financeiro.store import Conexao
from financeiro.store import onboarding as armazem


class PassoDesconhecido(Exception):
    """A chave não é de nenhum passo do onboarding."""


class PassoObrigatorio(Exception):
    """Só passo opcional pode ser dispensado."""


class Passo(NamedTuple):
    chave: str
    obrigatorio: bool
    contagem: int
    estado: str  # feito | pendente | bloqueado | nao_se_aplica
    bloqueado_por: tuple[str, ...]


class Situacao(NamedTuple):
    passos: tuple[Passo, ...]
    feitos: int
    total: int
    pronto: bool


class _Regra(NamedTuple):
    chave: str
    obrigatorio: bool
    depende_de: tuple[str, ...]
    conta: tuple[str, ...]  # contagens que precisam ser >= 1; a primeira é a exibida


# A ordem é a da tela. `depende_de` espelha as chaves estrangeiras do banco.
_REGRAS = (
    _Regra("organizacao", True, (), ("squad",)),
    _Regra("iniciativas", True, (), ("iniciativa",)),
    _Regra("demandas", True, ("iniciativas",), ("demanda",)),
    _Regra("agrupamentos", True, (), ("agrupamento",)),
    _Regra("temas", True, ("demandas", "agrupamentos"), ("tema",)),
    _Regra("cargos", True, (), ("cargo",)),
    _Regra("tarifas", True, ("cargos",), ("tarifa", "markup")),
    _Regra("pessoas", True, ("organizacao", "temas", "cargos"), ("pessoa",)),
    _Regra("orcamento", False, ("iniciativas",), ("revisao",)),
    _Regra("compras", False, ("demandas",), ("compra",)),
    _Regra("calendario", False, (), ("calendario",)),
)


def situacao(conexao: Conexao, bd_id: int) -> Situacao:
    contagens = armazem.contagens(conexao, bd_id)
    dispensados = armazem.dispensados(conexao, bd_id)
    resolvidos: set[str] = set()
    passos = []
    for regra in _REGRAS:
        feito = all(contagens[c] >= 1 for c in regra.conta)
        faltam = tuple(d for d in regra.depende_de if d not in resolvidos)
        if feito:
            estado, bloqueado_por = "feito", ()
        elif regra.chave in dispensados and not regra.obrigatorio:
            estado, bloqueado_por = "nao_se_aplica", ()
        elif faltam:
            estado, bloqueado_por = "bloqueado", faltam
        else:
            estado, bloqueado_por = "pendente", ()
        if estado in ("feito", "nao_se_aplica"):
            resolvidos.add(regra.chave)
        passos.append(
            Passo(regra.chave, regra.obrigatorio, contagens[regra.conta[0]], estado, bloqueado_por)
        )
    obrigatorios = [p for p in passos if p.obrigatorio]
    return Situacao(
        passos=tuple(passos),
        feitos=sum(p.estado in ("feito", "nao_se_aplica") for p in passos),
        total=len(passos),
        pronto=all(p.estado == "feito" for p in obrigatorios),
    )


def dispensar(conexao: Conexao, bd_id: int, chave: str, *, desfazer: bool = False) -> None:
    """Marca (ou desmarca) um passo opcional como "não se aplica" a este BD."""
    regra = next((r for r in _REGRAS if r.chave == chave), None)
    if regra is None:
        raise PassoDesconhecido(chave)
    if regra.obrigatorio:
        raise PassoObrigatorio(chave)
    if desfazer:
        armazem.desfazer_dispensa(conexao, bd_id, chave)
    else:
        armazem.dispensar(conexao, bd_id, chave)


def abrir_primeira_vez(conexao: Conexao, bd_id: int) -> bool:
    """True uma única vez por BD: quem recebe True abre o onboarding sozinho."""
    return armazem.marcar_aberto(conexao, bd_id)
