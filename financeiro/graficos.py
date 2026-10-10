"""Gráficos em SVG gerados no servidor: monocromáticos (tokens do DS), sem biblioteca de JS.

Cores só por `currentColor` e por variáveis CSS do tema (`--foreground`, `--border`, `--muted`):
claro e escuro funcionam sem mudar o gráfico.
"""

from html import escape

from financeiro.treemap import Bloco

_FG = "var(--foreground)"
_BORDA = "var(--border)"
_MUDO = "var(--muted-foreground)"


def _abrir(largura: float, altura: float, titulo: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura:g} {altura:g}" '
        f'role="img" width="100%" aria-label="{escape(titulo, quote=True)}">',
        f"<title>{escape(titulo)}</title>",
    ]


def curva(
    series: dict[str, list[int | None]],
    rotulos: list[str],
    titulo: str,
    largura: int = 640,
    altura: int = 260,
) -> str:
    """Linhas acumuladas por mês. A 1ª série é tracejada (budget); a 2ª, cheia e grossa."""
    margem_x, margem_y = 40, 20
    topo = max((v for s in series.values() for v in s if v is not None), default=0) or 1
    passo = (largura - 2 * margem_x) / max(len(rotulos) - 1, 1)

    def y(v: int) -> float:
        return altura - margem_y - (altura - 2 * margem_y) * v / topo

    partes = _abrir(largura, altura, titulo)
    partes.append(
        f'<line x1="{margem_x}" y1="{altura - margem_y}" x2="{largura - margem_x}" '
        f'y2="{altura - margem_y}" stroke="{_BORDA}"/>'
    )
    for i, rotulo in enumerate(rotulos):
        partes.append(
            f'<text x="{margem_x + i * passo:.1f}" y="{altura - 4}" font-size="10" '
            f'text-anchor="middle" fill="{_MUDO}">{escape(rotulo)}</text>'
        )
    estilos = [
        ('stroke-dasharray="4 4"', 1.5, 0.6),
        ("", 3, 1.0),
        ('stroke-dasharray="1 5" stroke-linecap="round"', 3, 0.7),
    ]
    for (nome, valores), (traco, espessura, opacidade) in zip(
        series.items(), estilos, strict=False
    ):
        pontos = " ".join(
            f"{margem_x + i * passo:.1f},{y(v):.1f}" for i, v in enumerate(valores) if v is not None
        )
        if pontos:
            partes.append(
                f'<polyline data-serie="{escape(nome, quote=True)}" points="{pontos}" fill="none" '
                f'stroke="{_FG}" stroke-width="{espessura}" stroke-opacity="{opacidade}" {traco}/>'
            )
    partes.append("</svg>")
    return "".join(partes)


def barras_risco(itens: list[dict], titulo: str, largura: int = 640) -> str:
    """Uma faixa por iniciativa: realizado (cheio), forecast (claro) e a linha do orçamento."""
    altura_faixa, rotulo_w = 34, 150
    altura = max(len(itens), 1) * altura_faixa + 10
    maior = (
        max((max(i["orcamento"], i["realizado"] + i["forecast"]) for i in itens), default=0) or 1
    )
    util = largura - rotulo_w - 10
    partes = _abrir(largura, altura, titulo)
    for n, item in enumerate(itens):
        y = 6 + n * altura_faixa
        real = util * item["realizado"] / maior
        fc = util * item["forecast"] / maior
        orc = rotulo_w + util * item["orcamento"] / maior
        partes.append(
            f'<g class="iniciativa"><text x="0" y="{y + 16}" font-size="12" fill="{_FG}">'
            f"{escape(item['nome'])}</text>"
            f'<rect x="{rotulo_w}" y="{y + 4}" width="{real:.1f}" height="18" fill="{_FG}" '
            f'fill-opacity="0.85"/>'
            f'<rect x="{rotulo_w + real:.1f}" y="{y + 4}" width="{fc:.1f}" height="18" '
            f'fill="{_FG}" fill-opacity="0.35"/>'
            f'<line class="orcamento" x1="{orc:.1f}" y1="{y}" x2="{orc:.1f}" y2="{y + 26}" '
            f'stroke="{_FG}" stroke-width="2"/></g>'
        )
    partes.append("</svg>")
    return "".join(partes)


def barras_composicao(itens: list[tuple[str, int]], titulo: str, largura: int = 640) -> str:
    """Barras horizontais proporcionais ao valor."""
    altura_faixa, rotulo_w = 30, 110
    altura = max(len(itens), 1) * altura_faixa + 10
    maior = max((v for _, v in itens), default=0) or 1
    util = largura - rotulo_w - 10
    partes = _abrir(largura, altura, titulo)
    for n, (rotulo, valor) in enumerate(itens):
        y = 6 + n * altura_faixa
        partes.append(
            f'<text x="0" y="{y + 15}" font-size="12" fill="{_FG}">{escape(rotulo)}</text>'
            f'<rect data-rotulo="{escape(rotulo, quote=True)}" x="{rotulo_w}" y="{y + 3}" '
            f'width="{util * valor / maior:.2f}" height="18" fill="{_FG}" fill-opacity="0.8"/>'
        )
    partes.append("</svg>")
    return "".join(partes)


def treemap_svg(
    blocos: list[Bloco],
    nomes: dict[str, str],
    largura: float,
    altura: float,
    titulo: str,
    realizados: dict[str, int] | None = None,
) -> str:
    """Blocos do treemap. `__saldo` é o que sobra da escala (tracejado, sem preenchimento)."""
    realizados = realizados or {}
    partes = _abrir(largura, altura, titulo)
    for bloco in blocos:
        saldo = bloco.chave == "__saldo"
        preench = "none" if saldo else _FG
        opacidade = "1" if saldo else "0.18"
        partes.append(
            f'<g><rect data-chave="{escape(bloco.chave, quote=True)}" x="{bloco.x:.2f}" '
            f'y="{bloco.y:.2f}" width="{bloco.largura:.2f}" height="{bloco.altura:.2f}" '
            f'fill="{preench}" fill-opacity="{opacidade}" stroke="{_FG}" stroke-width="1" '
            f"{'stroke-dasharray=' + chr(34) + '6 4' + chr(34) if saldo else ''}>"
            f"<title>{escape(nomes.get(bloco.chave, bloco.chave))}</title></rect>"
        )
        real = realizados.get(bloco.chave, 0)
        if real and bloco.valor:
            parte = bloco.altura * min(real / bloco.valor, 1)
            partes.append(
                f'<rect x="{bloco.x:.2f}" y="{bloco.y + bloco.altura - parte:.2f}" '
                f'width="{bloco.largura:.2f}" height="{parte:.2f}" fill="{_FG}" '
                f'fill-opacity="0.45"/>'
            )
        if bloco.largura > 70 and bloco.altura > 28:
            nome = escape(nomes.get(bloco.chave, bloco.chave))
            partes.append(
                f'<text x="{bloco.x + 8:.1f}" y="{bloco.y + 20:.1f}" font-size="13" '
                f'font-weight="600" fill="{_FG}">{nome}</text>'
            )
        partes.append("</g>")
    partes.append("</svg>")
    return "".join(partes)
