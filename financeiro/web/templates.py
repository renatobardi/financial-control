from functools import cache
from pathlib import Path

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
