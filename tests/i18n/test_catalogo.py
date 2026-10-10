import pytest

from financeiro import i18n


def test_t_devolve_o_texto_do_catalogo():
    assert i18n.t("fechamento.titulo") == "Fechamento mensal"


def test_t_preenche_parametros():
    assert i18n.t("fechamento.mes_fechado", mes="out/2026") == "Mês out/2026 fechado."


def test_t_com_chave_ausente_falha_alto():
    with pytest.raises(i18n.ChaveAusente):
        i18n.t("nao.existe")
