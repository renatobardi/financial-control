from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from financeiro import realizado, store
from financeiro.i18n import t
from financeiro.web.parametros import IntOpcional
from financeiro.web.sessao import Contexto, conexao_db, exigir_sessao
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/realizado")


def _parametros(request: Request, ano, dimensao, origem, base):
    ano = ano or request.app.state.agora().year
    dimensao = dimensao if dimensao in realizado.DIMENSOES else "iniciativa"
    origem = origem if origem in realizado.ORIGENS else "todas"
    base = base if base in realizado.BASES else "bruto"
    return ano, dimensao, origem, base


@roteador.get("")
def pagina(
    request: Request,
    ano: IntOpcional = None,
    dimensao: str = "iniciativa",
    origem: str = "todas",
    base: str = "bruto",
    contexto: Contexto = Depends(exigir_sessao),
):
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    ano, dimensao, origem, base = _parametros(request, ano, dimensao, origem, base)
    return renderizar(
        "realizado.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        usuario=contexto.usuario,
        papel=contexto.papel,
        ano=ano,
        dimensao=dimensao,
        origem=origem,
        base=base,
        dimensoes=realizado.DIMENSOES,
        origens=realizado.ORIGENS,
        bases=realizado.BASES,
    )


@roteador.get("/tabela")
def tabela(
    request: Request,
    ano: IntOpcional = None,
    dimensao: str = "iniciativa",
    origem: str = "todas",
    base: str = "bruto",
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    ano, dimensao, origem, base = _parametros(request, ano, dimensao, origem, base)
    resultado = realizado.consultar(
        conexao, contexto.bd_id, ano, dimensao, origem, base, request.app.state.agora()
    )
    return renderizar(
        "realizado/_tabela.html",
        tabela=resultado,
        com_orcamento=dimensao in ("iniciativa", "iniciativa_tipo"),
        meses=[f"{ano}-{m:02d}" for m in range(1, 13)],
    )
