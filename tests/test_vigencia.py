import pytest

from financeiro import vigencia


@pytest.mark.parametrize(
    ("mes", "anterior"), [("2026-10", "2026-09"), ("2026-01", "2025-12"), ("2025-03", "2025-02")]
)
def test_mes_anterior(mes, anterior):
    assert vigencia.mes_anterior(mes) == anterior


@pytest.mark.parametrize("mes", ["2026-13", "2026-00", "26-10", "2026/10", "", "2026-1"])
def test_mes_invalido_falha(mes):
    with pytest.raises(ValueError):
        vigencia.validar_mes(mes)


def test_vigente_em_considera_inicio_e_fim_inclusivos():
    assert vigencia.vigente_em("2025-01", "2026-01", "2025-01") is True
    assert vigencia.vigente_em("2025-01", "2026-01", "2026-01") is True
    assert vigencia.vigente_em("2025-01", "2026-01", "2026-02") is False
    assert vigencia.vigente_em("2026-02", None, "2030-01") is True
    assert vigencia.vigente_em("2026-02", None, "2026-01") is False


def test_sobreposicao_de_intervalos():
    assert vigencia.sobrepoe("2025-01", "2026-01", "2026-01", None) is True
    assert vigencia.sobrepoe("2025-01", "2026-01", "2026-02", None) is False
    assert vigencia.sobrepoe("2026-02", None, "2027-01", None) is True
    assert vigencia.sobrepoe("2025-01", "2025-06", "2025-07", "2025-12") is False
