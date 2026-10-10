"""Consumo do mês por lançamento: horas das pessoas e compras, em líquido e em bruto.

Mês aberto: calculado agora, pelas tarifas e pelo markup vigentes (é o forecast do lançamento).
Mês fechado: as linhas congeladas no fechamento (é o realizado, ADR-0003).
"""

from typing import NamedTuple

from financeiro import custo
from financeiro.store import Conexao, cadastros
from financeiro.store import consumo as armazem
from financeiro.store.consumo import Lancamento


class Calculo(NamedTuple):
    linhas: list[Lancamento]
    sem_tarifa_horas: int  # horas sem tarifa vigente no mês: entram com valor zero


def calcular(conexao: Conexao, bd_id: int, mes: str) -> Calculo:
    linhas: list[Lancamento] = []
    sem_tarifa = 0
    for (
        pessoa,
        tema,
        demanda,
        iniciativa,
        tipo,
        agrup,
        org,
        empresa,
        cargo,
        horas,
    ) in armazem.alocacoes_do_mes(conexao, bd_id, mes):
        try:
            hora = custo.custo_hora(conexao, bd_id, cargo, mes)
            liquido, bruto = horas * hora.liquida_centavos, horas * hora.bruta_centavos
        except custo.SemTarifa:
            liquido = bruto = 0
            sem_tarifa += horas
        linhas.append(
            Lancamento(
                "pessoas", pessoa, None, tema, demanda, iniciativa, tipo, agrup, org, empresa,
                cargo, horas, liquido, bruto,
            )
        )  # fmt: skip
    markup = cadastros.markup_vigente(conexao, bd_id, mes)
    pct = markup.centesimos_pct if markup else 0
    for compra, demanda, iniciativa, tipo, squad, liquido in armazem.compras_do_mes(
        conexao, bd_id, mes
    ):
        linhas.append(
            Lancamento(
                "compras", None, compra, None, demanda, iniciativa, tipo, None, squad, None,
                None, 0, liquido, custo.bruta(liquido, pct),
            )
        )  # fmt: skip
    return Calculo(linhas, sem_tarifa)


def do_mes(conexao: Conexao, bd_id: int, mes: str) -> tuple[str, list[Lancamento]]:
    """("realizado", linhas congeladas) se o mês está fechado; senão ("forecast", calculadas)."""
    if armazem.mes_esta_fechado(conexao, bd_id, mes):
        return "realizado", armazem.ler_realizado(conexao, bd_id, mes)
    return "forecast", calcular(conexao, bd_id, mes).linhas
