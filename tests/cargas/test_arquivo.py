import pytest

from financeiro.cargas import arquivo

COLUNAS = ("matricula", "tema_codigo", "ano", "mes", "horas")


def test_le_csv_com_ponto_e_virgula_e_utf8():
    texto = "matricula;tema_codigo;ano;mes;horas\nF0101;T-10;2026;9;120\nF0102;T-11;2026;9;80\n"

    linhas = arquivo.ler(texto.encode("utf-8"), COLUNAS)

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


def test_aceita_virgula_como_separador_e_bom():
    texto = "﻿matricula,tema_codigo,ano,mes,horas\nF0101,T-10,2026,9,120\n"

    linhas = arquivo.ler(texto.encode("utf-8"), COLUNAS)

    assert linhas[0][1]["matricula"] == "F0101"


def test_ignora_linha_em_branco_mas_mantem_a_numeracao():
    texto = "matricula;tema_codigo;ano;mes;horas\n\nF0101;T-10;2026;9;120\n"

    linhas = arquivo.ler(texto.encode(), COLUNAS)

    assert [numero for numero, _ in linhas] == [3]


def test_codificacao_que_nao_e_utf8_falha_com_mensagem():
    conteudo = "matricula;tema_codigo;ano;mes;horas\nF0101;Tê-10;2026;9;120\n".encode("latin-1")

    with pytest.raises(arquivo.ArquivoInvalido) as erro:
        arquivo.ler(conteudo, COLUNAS)

    assert erro.value.regra == "CSV_CODIFICACAO"
    assert "UTF-8" in str(erro.value)


def test_separador_inesperado_falha_com_mensagem():
    texto = "matricula\ttema_codigo\tano\tmes\thoras\nF0101\tT-10\t2026\t9\t120\n"

    with pytest.raises(arquivo.ArquivoInvalido) as erro:
        arquivo.ler(texto.encode(), COLUNAS)

    assert erro.value.regra == "CSV_CABECALHO"


def test_coluna_faltando_e_extra_sao_reportadas_pelo_nome():
    faltando = "matricula;tema_codigo;ano;mes\nF0101;T-10;2026;9\n"
    sobrando = "matricula;tema_codigo;ano;mes;horas;obs\nF0101;T-10;2026;9;1;x\n"

    with pytest.raises(arquivo.ArquivoInvalido) as erro:
        arquivo.ler(faltando.encode(), COLUNAS)
    assert "horas" in str(erro.value)
    with pytest.raises(arquivo.ArquivoInvalido) as erro:
        arquivo.ler(sobrando.encode(), COLUNAS)
    assert "obs" in str(erro.value)


def test_coluna_opcional_pode_faltar():
    texto = "matricula;nome\nF1;Ana\n"

    linhas = arquivo.ler(texto.encode(), ("matricula", "nome"), opcionais=("desligamento",))

    assert linhas[0][1] == {"matricula": "F1", "nome": "Ana", "desligamento": ""}


def test_linha_com_numero_de_colunas_errado_falha_apontando_a_linha():
    texto = "matricula;tema_codigo;ano;mes;horas\nF0101;T-10;2026\n"

    with pytest.raises(arquivo.ArquivoInvalido) as erro:
        arquivo.ler(texto.encode(), COLUNAS)

    assert erro.value.regra == "CSV_LINHA"
    assert "linha 2" in str(erro.value)


def test_arquivo_vazio_ou_so_cabecalho_falha():
    with pytest.raises(arquivo.ArquivoInvalido):
        arquivo.ler(b"", COLUNAS)
    with pytest.raises(arquivo.ArquivoInvalido) as erro:
        arquivo.ler(b"matricula;tema_codigo;ano;mes;horas\n", COLUNAS)
    assert erro.value.regra == "CSV_VAZIO"
