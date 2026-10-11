"""Organização como árvore com nível BD (pendência do lote 6 da #44)."""

import re

from financeiro.store import organizacao
from tests.web.ajuda import entrar, semear


def _preparar(ambiente):
    _, ids = semear(ambiente, bds=(("Diretoria X", "Admin"),))
    bd = ids["Diretoria X"]
    c = ambiente.conexao
    t1 = organizacao.criar_org(c, bd, "Tribo", "Alfa", None, "G", "2025-01")
    organizacao.criar_org(c, bd, "Tribo", "Beta", None, "G", "2025-01")
    organizacao.criar_org(c, bd, "Squad", "Alfa-1", t1, "G", "2025-01")
    organizacao.criar_org(c, bd, "Squad", "Alfa-2", t1, "G", "2025-01")
    entrar(ambiente)
    return bd


def _linhas(html):
    """(nível, nome) de cada linha da tabela, na ordem em que aparecem."""
    achados = re.findall(
        r"<tr class=\"border-t border-border\">\s*<td[^>]*>([^<]*)</td>\s*<td[^>]*>([^<]*)</td>",
        html,
    )
    return [(a.strip(), b.strip()) for a, b in achados]


def test_a_lista_comeca_pelo_bd_e_agrupa_cada_squad_sob_a_sua_tribo(ambiente):
    _preparar(ambiente)

    html = ambiente.cliente.get("/cadastros/organizacao/lista").text

    assert _linhas(html) == [
        ("BD", "Diretoria X"),
        ("Tribo", "Alfa"),
        ("Squad", "Alfa-1"),
        ("Squad", "Alfa-2"),
        ("Tribo", "Beta"),
    ]


def test_a_linha_do_bd_nao_tem_acoes_de_edicao(ambiente):
    _preparar(ambiente)

    html = ambiente.cliente.get("/cadastros/organizacao/lista").text
    linha_bd = html.split("Diretoria X</td>")[1].split("</tr>")[0]

    assert "<form" not in linha_bd


def test_squad_aparece_recuado_sob_a_tribo(ambiente):
    _preparar(ambiente)

    html = ambiente.cliente.get("/cadastros/organizacao/lista").text

    assert 'data-nivel="Squad"' in html and "pl-8" in html


def test_filtro_por_nivel_tem_o_chip_bd(ambiente):
    _preparar(ambiente)

    todas = ambiente.cliente.get("/cadastros/organizacao/lista").text
    so_bd = ambiente.cliente.get("/cadastros/organizacao/lista?filtro=BD").text

    assert 'data-chip="BD"' in todas
    assert _linhas(so_bd) == [("BD", "Diretoria X")]
