from functools import cache
from pathlib import Path

from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from financeiro import i18n

PASTA = Path(__file__).parent / "templates"


@cache
def ambiente() -> Environment:
    """Ambiente Jinja com autoescape, `t()` e os formatadores pt-BR como globais."""
    env = Environment(
        loader=FileSystemLoader(PASTA),
        autoescape=select_autoescape(["html"], default_for_string=True),
        undefined=StrictUndefined,
    )
    env.globals.update(
        t=i18n.t, moeda=i18n.moeda, moeda_mil=i18n.moeda_mil, mes=i18n.mes, numero=i18n.numero
    )
    return env


def renderizar(template: str, /, status: int = 200, **contexto: object) -> HTMLResponse:
    """Renderiza um template da pasta de templates como resposta HTML."""
    return HTMLResponse(ambiente().get_template(template).render(**contexto), status_code=status)
