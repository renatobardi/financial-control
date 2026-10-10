from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from financeiro import fechamento, i18n, store, vigencia
from financeiro.i18n import t
from financeiro.web.sessao import Contexto, conexao_db, exigir_edicao, exigir_sessao
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/fechamento")


def _ano(request: Request, ano: int | None) -> int:
    return ano or request.app.state.agora().year


def _grade(
    request: Request,
    conexao: store.Conexao,
    contexto: Contexto,
    ano: int,
    *,
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    agora = request.app.state.agora()
    meses = fechamento.situacao(conexao, contexto.bd_id, ano, agora)
    pendentes = fechamento.cargas_com_rejeicao_pendente(conexao, contexto.bd_id)
    primeiro_aberto = next((m.mes for m in meses if m.pode_fechar), None)
    return renderizar(
        "fechamento/_grade.html",
        status,
        ano=ano,
        meses=meses,
        rotulo=lambda mes: i18n.mes(int(mes[:4]), int(mes[5:])),
        anterior=lambda mes: i18n.mes(
            int(vigencia.mes_anterior(mes)[:4]), int(vigencia.mes_anterior(mes)[5:])
        ),
        pendentes=pendentes,
        primeiro_aberto=primeiro_aberto,
        log=fechamento.log(conexao, contexto.bd_id),
        csrf=contexto.csrf,
        pode_editar=contexto.papel in ("Admin", "Editor"),
        formato=contexto.usuario.formato_valor,
        ok=ok,
        erro=erro,
    )


@roteador.get("")
def pagina(request: Request, ano: int | None = None, contexto: Contexto = Depends(exigir_sessao)):
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    return renderizar(
        "fechamento.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        papel=contexto.papel,
        ano=_ano(request, ano),
    )


@roteador.get("/grade")
def grade(
    request: Request,
    ano: int | None = None,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    return _grade(request, conexao, contexto, _ano(request, ano))


def _mes_valido(mes: str) -> str:
    try:
        return vigencia.validar_mes(mes)
    except ValueError as erro:
        raise HTTPException(status_code=404) from erro


@roteador.post("/{mes}/fechar")
def fechar(
    request: Request,
    mes: str,
    ano: int | None = Form(None),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    mes = _mes_valido(mes)
    ano = ano or int(mes[:4])
    try:
        fechamento.fechar(
            conexao, contexto.bd_id, mes, contexto.usuario.id, request.app.state.agora()
        )
    except fechamento.FechamentoInvalido as erro:
        return _grade(request, conexao, contexto, ano, erro=str(erro), status=409)
    rotulo = i18n.mes(int(mes[:4]), int(mes[5:]))
    return _grade(request, conexao, contexto, ano, ok=t("fechamento_tela.ok_fechado", mes=rotulo))


@roteador.post("/{mes}/reabrir")
def reabrir(
    request: Request,
    mes: str,
    motivo: str = Form(""),
    ano: int | None = Form(None),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    mes = _mes_valido(mes)
    ano = ano or int(mes[:4])
    try:
        fechamento.reabrir(
            conexao, contexto.bd_id, mes, contexto.usuario.id, request.app.state.agora(), motivo
        )
    except fechamento.FechamentoInvalido as erro:
        return _grade(request, conexao, contexto, ano, erro=str(erro), status=409)
    rotulo = i18n.mes(int(mes[:4]), int(mes[5:]))
    return _grade(request, conexao, contexto, ano, ok=t("fechamento_tela.ok_reaberto", mes=rotulo))
