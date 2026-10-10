"""Formatadores pt-BR sobre inteiros: dinheiro é centavos, nunca float (ADR-0001)."""

import re

_MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
_MENOS = "−"


def _inteiro(valor: int) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise TypeError(f"esperava int, recebeu {type(valor).__name__}")
    return valor


def _milhares(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def numero(valor: int) -> str:
    """Inteiro com ponto de milhar: 1.234.567."""
    valor = _inteiro(valor)
    return (_MENOS if valor < 0 else "") + _milhares(abs(valor))


def moeda(centavos: int) -> str:
    """Centavos em reais: R$ 1.234,56."""
    centavos = _inteiro(centavos)
    reais, resto = divmod(abs(centavos), 100)
    return f"{_MENOS if centavos < 0 else ''}R$ {_milhares(reais)},{resto:02d}"


def moeda_mil(centavos: int) -> str:
    """Centavos em milhares de reais, arredondando meio para cima: R$ 1.235 mil."""
    centavos = _inteiro(centavos)
    mil = (abs(centavos) + 50_000) // 100_000
    return f"{_MENOS if centavos < 0 else ''}R$ {_milhares(mil)} mil"


def mes(ano: int, mes: int) -> str:
    """Mês abreviado com o ano: out/2026."""
    if not 1 <= mes <= 12:
        raise ValueError(f"mês fora de 1 a 12: {mes}")
    return f"{_MESES[mes - 1]}/{ano}"


def percentual(centesimos: int) -> str:
    """Centésimos de ponto percentual: 1090 vira 10,90%."""
    centesimos = _inteiro(centesimos)
    inteiro, resto = divmod(abs(centesimos), 100)
    return f"{_MENOS if centesimos < 0 else ''}{inteiro},{resto:02d}%"


_NUMERO = re.compile(r"^\d{1,3}(\.\d{3})*(,\d{1,2})?$|^\d+(,\d{1,2})?$")


def _ler_decimal_pt(texto: str, prefixos: tuple[str, ...]) -> tuple[int, int]:
    """Lê `1.234,56` e devolve (parte inteira, centésimos). Aceita no máximo 2 casas."""
    limpo = texto.strip()
    for prefixo in prefixos:
        limpo = limpo.removeprefix(prefixo).removesuffix(prefixo).strip()
    if not _NUMERO.match(limpo):
        raise ValueError(f"valor inválido: {texto!r}")
    inteiro, _, decimal = limpo.partition(",")
    return int(inteiro.replace(".", "")), int(decimal.ljust(2, "0")) if decimal else 0


def ler_moeda(texto: str) -> int:
    """`R$ 1.234,56` ou `204,75` em centavos inteiros, sem passar por float."""
    reais, centavos = _ler_decimal_pt(texto, ("R$",))
    return reais * 100 + centavos


def ler_percentual(texto: str) -> int:
    """`10,9` ou `10,90%` em centésimos de ponto percentual (1090)."""
    pontos, centesimos = _ler_decimal_pt(texto, ("%",))
    return pontos * 100 + centesimos


def data_hora(iso: str) -> str:
    """`2026-10-08T09:14:05Z` vira `08/10/2026 09:14`."""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]} {iso[11:16]}"
