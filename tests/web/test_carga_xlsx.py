"""Enviar a carga em .xlsx pela tela (#54): mesmo relatório e mesma gravação do CSV."""

import io

from openpyxl import Workbook

from tests.web.test_cargas import _alocacoes, _enviar, _preparar


def _planilha(linhas):
    livro = Workbook()
    for linha in linhas:
        livro.active.append(linha)
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


HORAS = [
    ["matricula", "tema_codigo", "ano", "mes", "horas"],
    ["F0101", "T-10", 2026, 9, 120],
    ["F9999", "T-10", 2026, 9, 1],
]


def test_pre_validacao_do_xlsx_relata_a_rejeicao_e_nao_grava(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _enviar(
        ambiente, csrf, "", acao="/validar", nome="horas.xlsx", conteudo=_planilha(HORAS)
    )

    assert resposta.status_code == 200
    assert "F9999" in resposta.text  # a matrícula que não existe é rejeitada
    assert _alocacoes(ambiente) == 0


def test_carga_do_xlsx_grava_como_o_csv(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _enviar(ambiente, csrf, "", nome="horas.xlsx", conteudo=_planilha(HORAS))

    assert resposta.status_code == 200
    assert _alocacoes(ambiente) == 1


def test_xlsx_com_cabecalho_errado_e_recusado_com_a_regra(ambiente):
    _, csrf = _preparar(ambiente)
    errada = _planilha([["matricula", "horas_extras"], ["F0101", 3]])

    resposta = _enviar(ambiente, csrf, "", nome="horas.xlsx", conteudo=errada)

    assert resposta.status_code == 400
    assert "XLSX_CABECALHO" in resposta.text
    assert _alocacoes(ambiente) == 0


def test_a_tela_aceita_xlsx_no_seletor_de_arquivo(ambiente):
    _preparar(ambiente)

    pagina = ambiente.cliente.get("/cargas").text

    assert 'accept=".csv,.xlsx' in pagina
