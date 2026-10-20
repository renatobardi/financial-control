"""Cenários: fatores sobre pessoas e compras aplicados ao forecast, e a composição do treemap."""

from financeiro.store import Conexao, ErroDeIntegridade
from financeiro.store import cenarios as armazem
from financeiro.store.cenarios import Cenario

LIMITE = 20
PADRAO = (("Base", 10000, 10000), ("Otimista", 9700, 9000), ("Pessimista", 10500, 11500))

__all__ = ["Cenario", "CenarioInvalido"]


class CenarioInvalido(Exception):
    """A operação recusada, com a mensagem que vai para a tela."""


def listar(conexao: Conexao, bd_id: int) -> list[Cenario]:
    return armazem.listar(conexao, bd_id)


def achar(conexao: Conexao, bd_id: int, cenario_id: int) -> Cenario | None:
    return armazem.achar(conexao, bd_id, cenario_id)


def criar(
    conexao: Conexao,
    bd_id: int,
    nome: str,
    fator_pessoas: int,
    fator_compras: int,
    **composicao: object,
) -> int:
    if not nome.strip():
        raise CenarioInvalido("Informe o nome do cenário.")
    if len(armazem.listar(conexao, bd_id)) >= LIMITE:
        raise CenarioInvalido(f"O limite é de {LIMITE} cenários por BD.")
    for fator in (fator_pessoas, fator_compras):
        if isinstance(fator, bool) or not isinstance(fator, int) or fator < 0:
            raise CenarioInvalido("Os fatores são percentuais inteiros, de 0 para cima.")
    try:
        return armazem.criar(
            conexao, bd_id, nome.strip(), fator_pessoas, fator_compras, **composicao
        )
    except ErroDeIntegridade as erro:
        conexao.rollback()
        raise CenarioInvalido("Já existe um cenário com este nome.") from erro


def garantir_padrao(conexao: Conexao, bd_id: int) -> list[Cenario]:
    """Cria Base, Otimista e Pessimista se o BD ainda não tem nenhum cenário."""
    if not armazem.listar(conexao, bd_id):
        for nome, fp, fc in PADRAO:
            armazem.criar(conexao, bd_id, nome, fp, fc)
    return armazem.listar(conexao, bd_id)


def duplicar(conexao: Conexao, bd_id: int, cenario_id: int) -> int:
    origem = armazem.achar(conexao, bd_id, cenario_id)
    if origem is None:
        raise CenarioInvalido("Cenário não encontrado neste BD.")
    nomes = {c.nome for c in armazem.listar(conexao, bd_id)}
    nome = f"{origem.nome} (cópia)"
    n = 2
    while nome in nomes:
        nome = f"{origem.nome} (cópia {n})"
        n += 1
    novo = criar(
        conexao, bd_id, nome, origem.fator_pessoas, origem.fator_compras,
        trimestres=origem.trimestres, escala_tipo=origem.escala_tipo, escala_ref=origem.escala_ref,
        escala_valor=origem.escala_valor_centavos, elemento_tipo=origem.elemento_tipo,
        incluidos=list(origem.incluidos),
    )  # fmt: skip
    for vaga, mes in armazem.inicios_de_vaga(conexao, bd_id, cenario_id).items():
        armazem.definir_inicio_vaga(conexao, bd_id, novo, vaga, mes)
    return novo


def atualizar(conexao: Conexao, bd_id: int, cenario_id: int, **campos: object) -> None:
    if armazem.achar(conexao, bd_id, cenario_id) is None:
        raise CenarioInvalido("Cenário não encontrado neste BD.")
    try:
        armazem.atualizar(conexao, bd_id, cenario_id, **campos)
    except ErroDeIntegridade as erro:
        conexao.rollback()
        raise CenarioInvalido("Valor inválido ou nome já usado por outro cenário.") from erro


def remover(conexao: Conexao, bd_id: int, cenario_id: int) -> None:
    if armazem.achar(conexao, bd_id, cenario_id) is None:
        raise CenarioInvalido("Cenário não encontrado neste BD.")
    if len(armazem.listar(conexao, bd_id)) <= 1:
        raise CenarioInvalido("O BD precisa de ao menos um cenário.")
    armazem.remover(conexao, bd_id, cenario_id)


def definir_inicio_vaga(
    conexao: Conexao, bd_id: int, cenario_id: int, vaga_id: int, mes: str
) -> None:
    if armazem.achar(conexao, bd_id, cenario_id) is None:
        raise CenarioInvalido("Cenário não encontrado neste BD.")
    try:
        armazem.definir_inicio_vaga(conexao, bd_id, cenario_id, vaga_id, mes)
    except ErroDeIntegridade as erro:
        conexao.rollback()
        raise CenarioInvalido("Vaga não encontrada neste BD.") from erro
