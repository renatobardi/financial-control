"""Textos e formatadores pt-BR. Texto visível nunca fica solto no código ou no template."""

from financeiro.i18n.catalogo import ChaveAusente, t
from financeiro.i18n.formatadores import (
    ler_moeda,
    ler_percentual,
    mes,
    moeda,
    moeda_mil,
    numero,
    percentual,
)

__all__ = [
    "ChaveAusente",
    "ler_moeda",
    "ler_percentual",
    "mes",
    "moeda",
    "moeda_mil",
    "numero",
    "percentual",
    "t",
]
