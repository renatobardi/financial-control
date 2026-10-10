import tomllib
from functools import cache
from pathlib import Path

_ARQUIVO = Path(__file__).parent / "pt-BR.toml"


class ChaveAusente(KeyError):
    """A chave não existe no catálogo: texto visível sempre vem dele."""


@cache
def _catalogo() -> dict[str, str]:
    plano: dict[str, str] = {}
    with _ARQUIVO.open("rb") as arquivo:
        for area, textos in tomllib.load(arquivo).items():
            for nome, texto in textos.items():
                plano[f"{area}.{nome}"] = texto
    return plano


def t(chave: str, **parametros: object) -> str:
    """Texto do catálogo pt-BR, com os parâmetros preenchidos."""
    try:
        texto = _catalogo()[chave]
    except KeyError:
        raise ChaveAusente(chave) from None
    return texto.format(**parametros)
