import pytest

from financeiro import treemap

LARGURA, ALTURA = 1000.0, 560.0


def _area(r):
    return r.largura * r.altura


def test_a_area_de_cada_bloco_e_proporcional_ao_valor():
    itens = [("a", 500), ("b", 300), ("c", 150), ("d", 50)]

    blocos = treemap.layout(itens, LARGURA, ALTURA)

    total = sum(v for _, v in itens)
    for bloco in blocos:
        valor = dict(itens)[bloco.chave]
        assert _area(bloco) / (LARGURA * ALTURA) == pytest.approx(valor / total, rel=1e-9)


def test_os_blocos_cobrem_o_retangulo_sem_sobrepor_e_sem_sair_dele():
    itens = [(str(i), v) for i, v in enumerate([40, 30, 10, 8, 6, 3, 2, 1])]

    blocos = treemap.layout(itens, LARGURA, ALTURA)

    assert sum(_area(b) for b in blocos) == pytest.approx(LARGURA * ALTURA, rel=1e-9)
    for b in blocos:
        assert b.x >= -1e-9 and b.y >= -1e-9
        assert b.x + b.largura <= LARGURA + 1e-6 and b.y + b.altura <= ALTURA + 1e-6
    for i, a in enumerate(blocos):
        for b in blocos[i + 1 :]:
            sobra_x = min(a.x + a.largura, b.x + b.largura) - max(a.x, b.x)
            sobra_y = min(a.y + a.altura, b.y + b.altura) - max(a.y, b.y)
            assert sobra_x <= 1e-6 or sobra_y <= 1e-6, (a, b)


def test_blocos_saem_do_maior_para_o_menor_e_valor_zero_some():
    blocos = treemap.layout([("p", 10), ("g", 90), ("z", 0)], LARGURA, ALTURA)

    assert [b.chave for b in blocos] == ["g", "p"]


def test_um_bloco_so_ocupa_tudo():
    (bloco,) = treemap.layout([("unico", 7)], LARGURA, ALTURA)

    assert (bloco.x, bloco.y, bloco.largura, bloco.altura) == (0, 0, LARGURA, ALTURA)


def test_lista_vazia_ou_toda_zerada_nao_gera_bloco():
    assert treemap.layout([], LARGURA, ALTURA) == []
    assert treemap.layout([("a", 0)], LARGURA, ALTURA) == []


def test_valor_negativo_e_recusado():
    with pytest.raises(ValueError):
        treemap.layout([("a", -1)], LARGURA, ALTURA)
