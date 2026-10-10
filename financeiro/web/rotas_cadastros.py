from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from financeiro import store
from financeiro.i18n import t
from financeiro.web import cadastros as abas
from financeiro.web.sessao import Contexto, conexao_db, exigir_edicao, exigir_sessao
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/cadastros")


def _aba_valida(aba: str) -> str:
    if aba not in abas.ABAS:
        raise HTTPException(status_code=404)
    return aba


def _mes_atual(request: Request) -> str:
    return request.app.state.agora().strftime("%Y-%m")


def _fragmento(
    request: Request,
    conexao: store.Conexao,
    contexto: Contexto,
    aba: str,
    *,
    pagina: int = 1,
    q: str = "",
    ano: int | None = None,
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    ano = ano or request.app.state.agora().year
    conteudo = abas.montar(conexao, contexto.bd_id, aba, ano, _mes_atual(request))
    if conteudo.paginada:
        linhas, pagina, total = abas.paginar(conteudo.linhas, pagina, q)
    else:
        linhas, pagina, total = conteudo.linhas, 1, 1
    return renderizar(
        "cadastros/_aba.html",
        status,
        aba=aba,
        conteudo=conteudo,
        linhas=linhas,
        pagina=pagina,
        total_paginas=total,
        q=q,
        ano=str(ano),
        csrf=contexto.csrf,
        pode_editar=contexto.papel in ("Admin", "Editor"),
        ok=ok,
        erro=erro,
    )


@roteador.get("")
def pagina(aba: str = "organizacao", contexto: Contexto = Depends(exigir_sessao)):
    _aba_valida(aba)
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    return renderizar(
        "cadastros.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        papel=contexto.papel,
        abas=abas.ABAS,
        aba=aba,
    )


@roteador.get("/{aba}/lista")
def lista(
    request: Request,
    aba: str,
    pagina: int = 1,
    q: str = "",
    ano: int | None = None,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _aba_valida(aba)
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    return _fragmento(request, conexao, contexto, aba, pagina=pagina, q=q, ano=ano)


@roteador.post("/{aba}/{acao}")
async def agir(
    request: Request,
    aba: str,
    acao: str,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _aba_valida(aba)
    handler = abas.ACOES.get((aba, acao))
    if handler is None:
        raise HTTPException(status_code=404)
    dados = {k: str(v) for k, v in (await request.form()).items() if k != "csrf"}
    ano = int(dados["ano"]) if dados.get("ano", "").isdigit() else None
    try:
        chave_ok = handler(conexao, contexto.bd_id, dados, _mes_atual(request))
    except abas.ErroCadastro as erro:
        return _fragmento(
            request, conexao, contexto, aba, ano=ano, erro=t(erro.chave), status=erro.status
        )
    return _fragmento(request, conexao, contexto, aba, ano=ano, ok=t(chave_ok))
