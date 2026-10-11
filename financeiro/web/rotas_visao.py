from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from financeiro import cenarios, graficos, i18n, orcamento, realizado, store, visao_geral
from financeiro.i18n import t
from financeiro.web.parametros import IntOpcional
from financeiro.web.sessao import Contexto, conexao_db, exigir_sessao
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/visao-geral")

_MESES = [i18n.mes(2000, n)[:3] for n in range(1, 13)]


def _calcular(
    request: Request,
    conexao: store.Conexao,
    contexto: Contexto,
    cenario_id: int | None,
    base: str,
    rev: int | None,
):
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    agora = request.app.state.agora()
    todos = cenarios.garantir_padrao(conexao, contexto.bd_id)
    cenario = next((c for c in todos if c.id == cenario_id), todos[0])
    base = base if base in realizado.BASES else "bruto"
    v = visao_geral.visao(conexao, contexto.bd_id, agora.year, cenario, base, agora, rev)
    return v, cenario, base


def _renderizar(
    nome: str, request, conexao, contexto, cenario_id, base, rev, **extra
) -> HTMLResponse:
    v, cenario, base = _calcular(request, conexao, contexto, cenario_id, base, rev)
    revisao = next(
        (r for r in orcamento.revisoes(conexao, contexto.bd_id) if r.id == rev),
        orcamento.vigente(conexao, contexto.bd_id),
    )
    return renderizar(
        f"visao/_{nome}.html",
        formato=contexto.usuario.formato_valor,
        v=v,
        cenario=cenario,
        base=base,
        revisao=revisao,
        percentual=i18n.percentual,
        **extra,
    )


@roteador.get("/kpis")
def kpis(
    request: Request,
    cenario: IntOpcional = None,
    base: str = "bruto",
    rev: IntOpcional = None,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    return _renderizar("kpis", request, conexao, contexto, cenario, base, rev)


@roteador.get("/alertas")
def alertas(
    request: Request,
    cenario: IntOpcional = None,
    base: str = "bruto",
    rev: IntOpcional = None,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    return _renderizar("alertas", request, conexao, contexto, cenario, base, rev)


@roteador.get("/curva")
def curva(
    request: Request,
    cenario: IntOpcional = None,
    base: str = "bruto",
    rev: IntOpcional = None,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    v, *_ = _calcular(request, conexao, contexto, cenario, base, rev)
    svg = graficos.curva(
        {
            t("visao.curva_budget"): v.curva_budget,
            t("visao.curva_realizado"): v.curva_realizado,
            t("visao.curva_forecast"): v.curva_forecast,
        },
        _MESES,
        t("visao.curva"),
    )
    return _renderizar("curva", request, conexao, contexto, cenario, base, rev, svg=svg)


@roteador.get("/risco")
def risco(
    request: Request,
    cenario: IntOpcional = None,
    base: str = "bruto",
    rev: IntOpcional = None,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    v, *_ = _calcular(request, conexao, contexto, cenario, base, rev)
    itens = [
        {"nome": r.nome, "orcamento": r.orcamento, "realizado": r.realizado, "forecast": r.forecast}
        for r in v.risco
    ]
    return _renderizar(
        "risco", request, conexao, contexto, cenario, base, rev,
        svg=graficos.barras_risco(itens, t("visao.risco")),
        svg_composicao=graficos.barras_composicao(v.composicao, t("visao.composicao")),
    )  # fmt: skip
