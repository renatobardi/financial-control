"""Vigência de cadastro: meses `AAAA-MM`, início e fim inclusivos, fim aberto = None."""

import re

_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_ABERTO = "9999-12"


class VigenciaSobreposta(Exception):
    """A nova vigência cobre meses que já têm valor para a mesma chave."""


def validar_mes(mes: str) -> str:
    if not _MES.match(mes):
        raise ValueError(f"mês fora do formato AAAA-MM: {mes!r}")
    return mes


def mes_anterior(mes: str) -> str:
    ano, numero = int(mes[:4]), int(mes[5:])
    if numero == 1:
        return f"{ano - 1}-12"
    return f"{ano}-{numero - 1:02d}"


def vigente_em(inicio: str, fim: str | None, mes: str) -> bool:
    return inicio <= mes <= (fim or _ABERTO)


def sobrepoe(a_ini: str, a_fim: str | None, b_ini: str, b_fim: str | None) -> bool:
    return a_ini <= (b_fim or _ABERTO) and b_ini <= (a_fim or _ABERTO)
