"""Marca as funções do store que, de propósito, leem entre BDs (ADR-0002)."""

from collections.abc import Callable


def entre_bds[F: Callable[..., object]](funcao: F) -> F:
    """Declara que a função cruza BDs (ex.: listar os BDs de um usuário) e dispensa `bd_id`.

    O teste de guarda lista as marcadas: acrescentar uma exige acrescentá-la lá.
    """
    funcao.__entre_bds__ = True  # type: ignore[attr-defined]
    return funcao
