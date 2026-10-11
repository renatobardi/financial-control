"""Carga em .xlsx: a primeira planilha vira as mesmas linhas do CSV (#54)."""

import io
import zipfile
from datetime import datetime

import pytest
from openpyxl import Workbook

from financeiro.cargas import arquivo

COLUNAS = ("matricula", "tema_codigo", "ano", "mes", "horas")


def _xlsx(linhas, titulo="Dados"):
    livro = Workbook()
    planilha = livro.active
    planilha.title = titulo
    for linha in linhas:
        planilha.append(linha)
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def test_planilha_vira_as_mesmas_linhas_do_csv():
    conteudo = _xlsx(
        [
            ["matricula", "tema_codigo", "ano", "mes", "horas"],
            ["F0101", "T-10", 2026, 9, 120],
            ["F0102", "T-11", 2026, 9, 80],
        ]
    )

    linhas = arquivo.ler(conteudo, COLUNAS)

    assert linhas == [
        (
            2,
            {
                "matricula": "F0101",
                "tema_codigo": "T-10",
                "ano": "2026",
                "mes": "9",
                "horas": "120",
            },
        ),
        (
            3,
            {"matricula": "F0102", "tema_codigo": "T-11", "ano": "2026", "mes": "9", "horas": "80"},
        ),
    ]


def test_numero_decimal_vira_texto_com_ponto_e_inteiro_nao_ganha_decimal():
    conteudo = _xlsx([["ordem_numero", "valor_liquido"], ["OC-1", 1234.5], ["OC-2", 2000.0]])

    linhas = arquivo.ler(conteudo, ("ordem_numero", "valor_liquido"))

    assert [d["valor_liquido"] for _, d in linhas] == ["1234.50", "2000"]


def test_data_do_excel_vira_ano_e_mes():
    conteudo = _xlsx([["matricula", "vig_ini"], ["F0101", datetime(2026, 1, 1)]])

    linhas = arquivo.ler(conteudo, ("matricula", "vig_ini"))

    assert linhas[0][1]["vig_ini"] == "2026-01"


def test_coluna_opcional_ausente_vem_vazia_e_celula_vazia_tambem():
    conteudo = _xlsx([["matricula", "nome", "desligamento"], ["F1", "Ana", None]])

    linhas = arquivo.ler(conteudo, ("matricula", "nome"), ("tema_codigo", "desligamento"))

    assert linhas[0][1] == {"matricula": "F1", "nome": "Ana", "desligamento": "", "tema_codigo": ""}


def test_linha_em_branco_e_ignorada_mas_a_numeracao_segue_a_planilha():
    conteudo = _xlsx([["matricula", "nome"], [None, None], ["F1", "Ana"]])

    linhas = arquivo.ler(conteudo, ("matricula", "nome"))

    assert [n for n, _ in linhas] == [3]


def test_cabecalho_errado_e_arquivo_recusado_com_codigo_xlsx():
    conteudo = _xlsx([["matricula", "horas_extras"], ["F1", 3]])

    with pytest.raises(arquivo.ArquivoInvalido) as erro:
        arquivo.ler(conteudo, ("matricula", "horas"))

    assert erro.value.regra == "XLSX_CABECALHO"
    assert "faltam as colunas: horas" in str(erro.value)


def test_so_cabecalho_ou_planilha_vazia_e_recusado():
    so_cabecalho = _xlsx([["matricula", "horas"]])
    vazia = _xlsx([])

    for conteudo in (so_cabecalho, vazia):
        with pytest.raises(arquivo.ArquivoInvalido) as erro:
            arquivo.ler(conteudo, ("matricula", "horas"))
        assert erro.value.regra == "XLSX_VAZIO"


def test_arquivo_que_nao_e_planilha_e_recusado():
    falso = b"PK\x03\x04isto nao e um zip de verdade"

    with pytest.raises(arquivo.ArquivoInvalido) as erro:
        arquivo.ler(falso, COLUNAS)

    assert erro.value.regra == "XLSX_INVALIDO"


def test_zip_que_expande_demais_e_recusado_antes_de_abrir():
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", b"0" * (arquivo.LIMITE_DESCOMPRIMIDO + 1))

    with pytest.raises(arquivo.ArquivoInvalido) as erro:
        arquivo.ler(saida.getvalue(), COLUNAS)

    assert erro.value.regra == "XLSX_GRANDE"
