import pytest

from financeiro import i18n


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (0, "R$ 0,00"),
        (5, "R$ 0,05"),
        (123456, "R$ 1.234,56"),
        (100000000, "R$ 1.000.000,00"),
        (-123456, "−R$ 1.234,56"),
    ],
)
def test_moeda_formata_centavos(centavos, esperado):
    assert i18n.moeda(centavos) == esperado


def test_moeda_recusa_float():
    with pytest.raises(TypeError):
        i18n.moeda(12.5)


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (123456789, "R$ 1.235 mil"),
        (-50000000, "−R$ 500 mil"),
        (50000, "R$ 1 mil"),
        (49999, "R$ 0 mil"),
    ],
)
def test_moeda_mil_arredonda_para_milhares(centavos, esperado):
    assert i18n.moeda_mil(centavos) == esperado


def test_mes_abreviado():
    assert i18n.mes(2026, 10) == "out/2026"
    assert i18n.mes(2026, 3) == "mar/2026"


def test_mes_invalido_falha():
    with pytest.raises(ValueError):
        i18n.mes(2026, 13)


def test_numero_usa_ponto_de_milhar():
    assert i18n.numero(1234567) == "1.234.567"
    assert i18n.numero(-1000) == "−1.000"
