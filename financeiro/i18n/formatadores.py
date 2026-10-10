"""Formatadores pt-BR sobre inteiros: dinheiro é centavos, nunca float (ADR-0001)."""

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
