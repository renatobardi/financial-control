"""Parâmetros de consulta: campo em branco do formulário chega como `?rev=` e vale como ausente."""

from typing import Annotated

from pydantic import BeforeValidator


def _vazio_vira_none(valor: object) -> object:
    if isinstance(valor, str) and not valor.strip():
        return None
    return valor


IntOpcional = Annotated[int | None, BeforeValidator(_vazio_vira_none)]
