"""Orçamento (PDD): revisões trimestrais por iniciativa × tipo, em valor bruto.

O markup fica congelado na aprovação de cada revisão. Líquido = bruto ÷ (1 + markup).
"""

from dataclasses import dataclass
from datetime import datetime

from financeiro.store import Conexao
from financeiro.store import cadastros as cadastros_store
from financeiro.store import pdd as armazem
from financeiro.store.pdd import Revisao

LIMITE_REVISOES = 4
TIPOS = ("CAPEX", "OPEX")


class OrcamentoInvalido(Exception):
    """A operação quebra uma regra do PDD; a mensagem vai para a tela."""


@dataclass(frozen=True)
class LinhaOrcamento:
    iniciativa_id: int
    codigo: str
    iniciativa: str
    tipo: str
    bruto_centavos: int
    liquido_centavos: int
    markup_centesimos_pct: int


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def gap(orcamento_centavos: int, total_ano_centavos: int) -> int:
    """Gap com sinal único: orçamento − total do ano. Positivo é saldo, negativo é estouro."""
    return orcamento_centavos - total_ano_centavos


def liquido_de(bruto_centavos: int, markup_centesimos_pct: int) -> int:
    """líquido = bruto ÷ (1 + markup), em centavos, meio centavo para cima."""
    for valor in (bruto_centavos, markup_centesimos_pct):
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise TypeError(f"esperava int, recebeu {type(valor).__name__}")
    divisor = 10_000 + markup_centesimos_pct
    return (bruto_centavos * 10_000 + divisor // 2) // divisor


def revisoes(conexao: Conexao, bd_id: int) -> list[Revisao]:
    return armazem.listar_revisoes(conexao, bd_id)


def vigente(conexao: Conexao, bd_id: int) -> Revisao | None:
    aprovadas = [r for r in armazem.listar_revisoes(conexao, bd_id) if r.estado == "aprovada"]
    return aprovadas[-1] if aprovadas else None


def rascunho(conexao: Conexao, bd_id: int) -> Revisao | None:
    for r in armazem.listar_revisoes(conexao, bd_id):
        if r.estado == "rascunho":
            return r
    return None


def _da_revisao(conexao: Conexao, bd_id: int, revisao_id: int) -> Revisao:
    revisao = armazem.achar_revisao(conexao, bd_id, revisao_id)
    if revisao is None:
        raise OrcamentoInvalido("Revisão não encontrada neste BD.")
    return revisao


def _rascunho_editavel(conexao: Conexao, bd_id: int, revisao_id: int) -> Revisao:
    revisao = _da_revisao(conexao, bd_id, revisao_id)
    if revisao.estado != "rascunho":
        raise OrcamentoInvalido(
            f"A revisão {revisao.rotulo} está aprovada e é só leitura. Crie uma nova revisão."
        )
    return revisao


def nova_revisao(conexao: Conexao, bd_id: int, agora: datetime) -> Revisao:
    """Cria o rascunho (a Original, ou T1, T2, T3) partindo das linhas da vigente."""
    existentes = armazem.listar_revisoes(conexao, bd_id)
    if any(r.estado == "rascunho" for r in existentes):
        raise OrcamentoInvalido("Já existe um rascunho: aprove ou descarte antes de criar outro.")
    if len(existentes) >= LIMITE_REVISOES:
        raise OrcamentoInvalido(f"O limite é de {LIMITE_REVISOES} revisões (Original e T1 a T3).")
    rotulo = "Original" if not existentes else f"T{len(existentes)}"
    conexao.commit()
    try:
        novo_id = armazem.criar_revisao(conexao, bd_id, rotulo, _iso(agora))
        base = vigente(conexao, bd_id)
        if base is not None:
            armazem.copiar_linhas(conexao, bd_id, base.id, novo_id)
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    return _da_revisao(conexao, bd_id, novo_id)


def definir_linha(
    conexao: Conexao, bd_id: int, revisao_id: int, iniciativa_id: int, tipo: str, bruto: int
) -> None:
    _rascunho_editavel(conexao, bd_id, revisao_id)
    if isinstance(bruto, bool) or not isinstance(bruto, int):
        raise TypeError(f"esperava int, recebeu {type(bruto).__name__}")
    if tipo not in TIPOS:
        raise OrcamentoInvalido(f"Tipo {tipo!r}: use CAPEX ou OPEX.")
    if bruto < 0:
        raise OrcamentoInvalido("O valor do budget não pode ser negativo.")
    try:
        armazem.definir_linha(conexao, bd_id, revisao_id, iniciativa_id, tipo, bruto)
        conexao.commit()
    except Exception as erro:
        conexao.rollback()
        raise OrcamentoInvalido("Iniciativa não encontrada neste BD.") from erro


def remover_linha(
    conexao: Conexao, bd_id: int, revisao_id: int, iniciativa_id: int, tipo: str
) -> None:
    _rascunho_editavel(conexao, bd_id, revisao_id)
    armazem.remover_linha(conexao, bd_id, revisao_id, iniciativa_id, tipo)
    conexao.commit()


def aprovar(conexao: Conexao, bd_id: int, revisao_id: int, agora: datetime) -> Revisao:
    """Aprova o rascunho e congela o markup vigente no mês da aprovação."""
    revisao = _rascunho_editavel(conexao, bd_id, revisao_id)
    mes = agora.strftime("%Y-%m")
    markup = cadastros_store.markup_vigente(conexao, bd_id, mes)
    if markup is None:
        raise OrcamentoInvalido(
            f"Não há markup vigente em {mes}. Cadastre o markup antes de aprovar a revisão."
        )
    armazem.aprovar_revisao(conexao, bd_id, revisao.id, markup.centesimos_pct, _iso(agora))
    conexao.commit()
    return _da_revisao(conexao, bd_id, revisao_id)


def descartar(conexao: Conexao, bd_id: int, revisao_id: int) -> None:
    revisao = _rascunho_editavel(conexao, bd_id, revisao_id)
    armazem.descartar_revisao(conexao, bd_id, revisao.id)
    conexao.commit()


def markup_da_revisao(conexao: Conexao, bd_id: int, revisao: Revisao, agora: datetime) -> int:
    """Markup congelado da aprovada; do rascunho, o vigente hoje (será congelado ao aprovar)."""
    if revisao.markup_centesimos_pct is not None:
        return revisao.markup_centesimos_pct
    vigente_hoje = cadastros_store.markup_vigente(conexao, bd_id, agora.strftime("%Y-%m"))
    return vigente_hoje.centesimos_pct if vigente_hoje else 0


def linhas(conexao: Conexao, bd_id: int, revisao_id: int, agora: datetime) -> list[LinhaOrcamento]:
    """Linhas da revisão, cada uma com o valor bruto e o líquido (pelo markup da revisão)."""
    revisao = _da_revisao(conexao, bd_id, revisao_id)
    markup = markup_da_revisao(conexao, bd_id, revisao, agora)
    return [
        LinhaOrcamento(
            linha.iniciativa_id,
            linha.codigo,
            linha.iniciativa,
            linha.tipo,
            linha.bruto_centavos,
            liquido_de(linha.bruto_centavos, markup),
            markup,
        )
        for linha in armazem.linhas_da_revisao(conexao, bd_id, revisao_id)
    ]
