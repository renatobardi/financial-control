"""Treemap em quadrados (squarified): a área de cada bloco é proporcional ao seu valor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bloco:
    chave: str
    valor: int
    x: float
    y: float
    largura: float
    altura: float


def _pior_razao(areas: list[float], lado: float) -> float:
    soma = sum(areas)
    return max(max(lado * lado * a / (soma * soma), soma * soma / (lado * lado * a)) for a in areas)


def layout(itens: list[tuple[str, int]], largura: float, altura: float) -> list[Bloco]:
    """Posiciona os itens em `largura × altura`, do maior para o menor valor."""
    if any(valor < 0 for _, valor in itens):
        raise ValueError("valor negativo no treemap")
    ordenados = sorted(((c, v) for c, v in itens if v > 0), key=lambda x: (-x[1], x[0]))
    if not ordenados:
        return []
    total = sum(v for _, v in ordenados)
    area_total = largura * altura
    areas = [v / total * area_total for _, v in ordenados]
    blocos: list[Bloco] = []
    x, y, w, h = 0.0, 0.0, float(largura), float(altura)
    i = 0
    while i < len(ordenados):
        lado = min(w, h)
        linha = [i]
        while linha[-1] + 1 < len(ordenados):
            atual = [areas[j] for j in linha]
            proxima = atual + [areas[linha[-1] + 1]]
            if _pior_razao(proxima, lado) <= _pior_razao(atual, lado):
                linha.append(linha[-1] + 1)
            else:
                break
        soma = sum(areas[j] for j in linha)
        if w >= h:  # coluna à esquerda
            espessura = soma / h
            cursor = y
            for j in linha:
                altura_bloco = areas[j] / espessura
                blocos.append(Bloco(*ordenados[j], x, cursor, espessura, altura_bloco))
                cursor += altura_bloco
            x += espessura
            w -= espessura
        else:  # faixa no topo
            espessura = soma / w
            cursor = x
            for j in linha:
                largura_bloco = areas[j] / espessura
                blocos.append(Bloco(*ordenados[j], cursor, y, largura_bloco, espessura))
                cursor += largura_bloco
            y += espessura
            h -= espessura
        i = linha[-1] + 1
    return blocos
