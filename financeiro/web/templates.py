from functools import cache
from pathlib import Path

from fastapi.responses import HTMLResponse
from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    pass_context,
    select_autoescape,
)
from markupsafe import Markup, escape

from financeiro import i18n

PASTA = Path(__file__).parent / "templates"


@pass_context
def valor(contexto, centavos: int | None) -> Markup:
    """Valor na preferência do usuário (mil ou mi), com o valor exato no tooltip."""
    if centavos is None:
        return Markup("—")
    formato = contexto.get("formato")
    if formato is None:
        usuario = contexto.get("usuario")
        formato = getattr(usuario, "formato_valor", "mil")
    exato = escape(i18n.moeda(centavos))
    curto = escape(i18n.valor_abreviado(centavos, formato))
    return Markup(f'<span class="tabular-nums" title="{exato}">{curto}</span>')


@cache
def ambiente() -> Environment:
    """Ambiente Jinja com autoescape, `t()` e os formatadores pt-BR como globais."""
    env = Environment(
        loader=FileSystemLoader(PASTA),
        autoescape=select_autoescape(["html"], default_for_string=True),
        undefined=StrictUndefined,
    )
    env.globals.update(
        t=i18n.t,
        moeda=i18n.moeda,
        moeda_mil=i18n.moeda_mil,
        mes=i18n.mes,
        numero=i18n.numero,
        data_hora=i18n.data_hora,
        valor_abreviado=i18n.valor_abreviado,
        percentual=i18n.percentual,
        valor=valor,
    )
    return env


def renderizar(template: str, /, status: int = 200, **contexto: object) -> HTMLResponse:
    """Renderiza um template da pasta de templates como resposta HTML."""
    return HTMLResponse(ambiente().get_template(template).render(**contexto), status_code=status)
