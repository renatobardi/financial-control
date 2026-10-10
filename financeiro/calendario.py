"""Calendário: 8 h × dias úteis, descontados feriados nacionais, bancários e do BD."""

import datetime as dt

from financeiro.store import Conexao
from financeiro.store import calendario as armazem

HORAS_POR_DIA = 8


def pascoa(ano: int) -> dt.date:
    """Domingo de Páscoa (algoritmo anônimo gregoriano)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 (nome do algoritmo)
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return dt.date(ano, mes, dia)


def feriados_nacionais(ano: int) -> dict[dt.date, str]:
    """Feriados nacionais e os pontos bancários sem expediente (Carnaval, Corpus Christi)."""
    p = pascoa(ano)
    dia = dt.timedelta
    return {
        dt.date(ano, 1, 1): "Confraternização Universal",
        p - dia(days=48): "Carnaval",
        p - dia(days=47): "Carnaval",
        p - dia(days=2): "Sexta-feira Santa",
        dt.date(ano, 4, 21): "Tiradentes",
        dt.date(ano, 5, 1): "Dia do Trabalho",
        p + dia(days=60): "Corpus Christi",
        dt.date(ano, 9, 7): "Independência",
        dt.date(ano, 10, 12): "Nossa Senhora Aparecida",
        dt.date(ano, 11, 2): "Finados",
        dt.date(ano, 11, 15): "Proclamação da República",
        dt.date(ano, 11, 20): "Consciência Negra",
        dt.date(ano, 12, 25): "Natal",
    }


def dias_uteis(ano: int, mes: int, feriados_extra: set[dt.date] | None = None) -> int:
    if not 1 <= mes <= 12:
        raise ValueError(f"mês fora de 1 a 12: {mes}")
    feriados = set(feriados_nacionais(ano)) | (feriados_extra or set())
    dia = dt.date(ano, mes, 1)
    total = 0
    while dia.month == mes:
        if dia.weekday() < 5 and dia not in feriados:
            total += 1
        dia += dt.timedelta(days=1)
    return total


def adicionar_feriado(conexao: Conexao, bd_id: int, data: dt.date, nome: str) -> None:
    armazem.adicionar_feriado(conexao, bd_id, data.isoformat(), nome)


def gerar(conexao: Conexao, bd_id: int, ano: int) -> None:
    """Grava as horas dos 12 meses (8 h × dias úteis). Mês já ajustado à mão é mantido."""
    extras = {dt.date.fromisoformat(d) for d, _ in armazem.feriados_do_ano(conexao, bd_id, ano)}
    for mes in range(1, 13):
        if armazem.mes_ajustado(conexao, bd_id, ano, mes):
            continue
        horas = dias_uteis(ano, mes, extras) * HORAS_POR_DIA
        armazem.gravar_horas(conexao, bd_id, ano, mes, horas, ajustado=False)


def ajustar(conexao: Conexao, bd_id: int, ano: int, mes: int, horas: int) -> None:
    if not 1 <= mes <= 12:
        raise ValueError(f"mês fora de 1 a 12: {mes}")
    if horas < 0:
        raise ValueError(f"horas negativas: {horas}")
    armazem.gravar_horas(conexao, bd_id, ano, mes, horas, ajustado=True)


def horas_do_mes(conexao: Conexao, bd_id: int, ano: int, mes: int) -> int | None:
    return armazem.horas_do_mes(conexao, bd_id, ano, mes)


def capacidade(conexao: Conexao, bd_id: int, ano: int, mes: int) -> int:
    """Horas de capacidade do mês: o calendário gravado ou, sem ele, 8 h × dias úteis."""
    gravadas = armazem.horas_do_mes(conexao, bd_id, ano, mes)
    if gravadas is not None:
        return gravadas
    extras = {dt.date.fromisoformat(d) for d, _ in armazem.feriados_do_ano(conexao, bd_id, ano)}
    return dias_uteis(ano, mes, extras) * HORAS_POR_DIA
