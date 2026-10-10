"""Custo por hora: tarifa líquida vigente do cargo + markup vigente do BD. Tudo em inteiros."""

from typing import NamedTuple

from financeiro.store import Conexao, cadastros


class SemTarifa(Exception):
    """Não há tarifa ou markup vigente na data pedida."""


class CustoHora(NamedTuple):
    liquida_centavos: int
    markup_centesimos_pct: int
    bruta_centavos: int


def bruta(liquida_centavos: int, markup_centesimos_pct: int) -> int:
    """bruto = líquido × (1 + markup), em centavos, meio centavo para cima."""
    for valor in (liquida_centavos, markup_centesimos_pct):
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise TypeError(f"esperava int, recebeu {type(valor).__name__}")
    acrescimo = (liquida_centavos * markup_centesimos_pct + 5_000) // 10_000
    return liquida_centavos + acrescimo


def custo_hora(conexao: Conexao, bd_id: int, cargo_id: int, mes: str) -> CustoHora:
    """Valor da hora do cargo no mês: a tarifa e o markup que valiam naquele mês."""
    tarifa = cadastros.tarifa_vigente(conexao, bd_id, cargo_id, mes)
    if tarifa is None:
        raise SemTarifa(f"cargo {cargo_id} sem tarifa vigente em {mes}")
    markup = cadastros.markup_vigente(conexao, bd_id, mes)
    if markup is None:
        raise SemTarifa(f"BD {bd_id} sem markup vigente em {mes}")
    return CustoHora(
        tarifa.liquida_centavos,
        markup.centesimos_pct,
        bruta(tarifa.liquida_centavos, markup.centesimos_pct),
    )
