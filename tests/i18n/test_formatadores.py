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


@pytest.mark.parametrize(
    ("centesimos", "esperado"), [(1090, "10,90%"), (1050, "10,50%"), (0, "0,00%"), (5, "0,05%")]
)
def test_percentual_em_centesimos(centesimos, esperado):
    assert i18n.percentual(centesimos) == esperado


@pytest.mark.parametrize(
    ("texto", "centavos"),
    [
        ("204,75", 20475),
        ("R$ 204,75", 20475),
        ("1.234,56", 123456),
        ("193", 19300),
        ("193,5", 19350),
        ("0,05", 5),
        ("  12,00 ", 1200),
    ],
)
def test_ler_moeda_devolve_centavos_inteiros(texto, centavos):
    assert i18n.ler_moeda(texto) == centavos


@pytest.mark.parametrize("texto", ["", "abc", "12,345", "-5", "1,2,3", "12.5.0,1"])
def test_ler_moeda_recusa_texto_invalido(texto):
    with pytest.raises(ValueError):
        i18n.ler_moeda(texto)


@pytest.mark.parametrize(
    ("texto", "centesimos"), [("10,9", 1090), ("10,90%", 1090), ("10", 1000), ("0,05", 5)]
)
def test_ler_percentual_devolve_centesimos(texto, centesimos):
    assert i18n.ler_percentual(texto) == centesimos


def test_ler_percentual_recusa_texto_invalido():
    with pytest.raises(ValueError):
        i18n.ler_percentual("dez")


def test_data_hora_iso_para_o_formato_brasileiro():
    assert i18n.data_hora("2026-10-08T09:14:05Z") == "08/10/2026 09:14"


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (223_300_000, "R$ 2,23 mi"),
        (0, "R$ 0,00 mi"),
        (-150_000_000, "−R$ 1,50 mi"),
        (99_999_999, "R$ 1,00 mi"),
        (123_456_789, "R$ 1,23 mi"),
    ],
)
def test_moeda_mi_com_duas_casas_arredondando_para_cima_no_meio(centavos, esperado):
    assert i18n.moeda_mi(centavos) == esperado


def test_valor_abreviado_segue_a_preferencia_do_usuario():
    assert i18n.valor_abreviado(223_300_000, "mi") == "R$ 2,23 mi"
    assert i18n.valor_abreviado(223_300_000, "mil") == "R$ 2.233 mil"
