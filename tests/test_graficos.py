import xml.etree.ElementTree as ET

import pytest

from financeiro import graficos, treemap

NS = "{http://www.w3.org/2000/svg}"


def _raiz(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def test_curva_gera_svg_valido_com_tres_series_e_titulo():
    svg = graficos.curva(
        {
            "Budget": [i * 100 for i in range(1, 13)],
            "Realizado": [100, 250, 400, None, None, None, None, None, None, None, None, None],
            "Forecast": [None, None, 400, 520, 700, 900, 1000, 1100, 1150, 1180, 1190, 1200],
        },
        ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
        titulo="Curva do ano",
    )

    raiz = _raiz(svg)
    assert raiz.tag == f"{NS}svg"
    assert len(raiz.findall(f".//{NS}polyline")) == 3
    assert raiz.find(f"{NS}title").text == "Curva do ano"


def test_barras_de_risco_tem_uma_faixa_por_iniciativa_e_marca_o_orcamento():
    itens = [
        {"nome": "Alfa", "orcamento": 1000, "realizado": 600, "forecast": 500},
        {"nome": "Beta", "orcamento": 800, "realizado": 100, "forecast": 100},
    ]

    raiz = _raiz(graficos.barras_risco(itens, titulo="Risco"))

    assert len(raiz.findall(f".//{NS}g[@class='iniciativa']")) == 2
    assert len(raiz.findall(f".//{NS}line[@class='orcamento']")) == 2


def test_barras_de_composicao_proporcionais():
    raiz = _raiz(graficos.barras_composicao([("Pessoas", 750), ("Compras", 250)], titulo="C"))

    larguras = {r.get("data-rotulo"): float(r.get("width")) for r in raiz.findall(f".//{NS}rect")}
    assert larguras["Pessoas"] / larguras["Compras"] == pytest.approx(3.0, rel=1e-3)


def test_treemap_svg_desenha_um_retangulo_por_bloco_com_area_proporcional():
    blocos = treemap.layout([("a", 600), ("b", 300), ("__saldo", 100)], 1000, 560)
    nomes = {"a": "Alfa", "b": "Beta", "__saldo": "Disponível"}

    raiz = _raiz(graficos.treemap_svg(blocos, nomes, 1000, 560, titulo="Treemap"))

    retangulos = {r.get("data-chave"): r for r in raiz.findall(f".//{NS}rect[@data-chave]")}
    assert set(retangulos) == {"a", "b", "__saldo"}
    area = {k: float(r.get("width")) * float(r.get("height")) for k, r in retangulos.items()}
    assert area["a"] / area["b"] == pytest.approx(2.0, rel=1e-3)


def test_texto_com_caracteres_especiais_e_escapado():
    svg = graficos.barras_composicao([("<script>x</script> & Cia", 10)], titulo="a&b")

    raiz = _raiz(svg)  # continua XML válido
    assert "<script>" not in svg
    assert raiz.find(f"{NS}title").text == "a&b"


def test_sem_dados_gera_svg_vazio_valido():
    assert _raiz(graficos.barras_risco([], titulo="x")).tag == f"{NS}svg"
    assert _raiz(graficos.barras_composicao([], titulo="x")).tag == f"{NS}svg"
    assert _raiz(graficos.treemap_svg([], {}, 1000, 560, titulo="x")).tag == f"{NS}svg"
