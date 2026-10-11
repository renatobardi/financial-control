from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from financeiro import compras, i18n, store
from financeiro.i18n import t
from financeiro.store import portfolio
from financeiro.web.parametros import IntOpcional
from financeiro.web.sessao import Contexto, conexao_db, exigir_edicao, exigir_sessao
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/compras")


def _exigir_bd(contexto: Contexto) -> int:
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    return contexto.bd_id


def _lista(
    request: Request,
    conexao: store.Conexao,
    contexto: Contexto,
    *,
    ano: IntOpcional = None,
    busca: str = "",
    status_filtro: str = "",
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    agora = request.app.state.agora()
    ano = ano or agora.year
    linhas = compras.listar(conexao, contexto.bd_id, ano, agora, busca, status_filtro or None)
    return renderizar(
        "compras/_lista.html",
        status,
        linhas=linhas,
        ano=ano,
        busca=busca,
        status_filtro=status_filtro,
        status_opcoes=compras.STATUS,
        realizado=sum(x.realizado_centavos for x in linhas),
        forecast=sum(x.forecast_centavos for x in linhas),
        previstas=sum(x.status == "prevista" for x in linhas),
        demandas=portfolio.listar_demandas(conexao, contexto.bd_id),
        tipos=compras.TIPOS,
        csrf=contexto.csrf,
        pode_editar=contexto.papel in ("Admin", "Editor"),
        ok=ok,
        erro=erro,
    )


def _detalhe(
    request: Request,
    conexao: store.Conexao,
    contexto: Contexto,
    compra_id: int,
    *,
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    ordem = compras.achar(conexao, contexto.bd_id, compra_id)
    if ordem is None:
        raise HTTPException(status_code=404)
    ano = request.app.state.agora().year
    return renderizar(
        "compras/_detalhe.html",
        status,
        ordem=ordem,
        meses=compras.valores_por_mes(conexao, contexto.bd_id, compra_id, ano),
        historico=compras.historico(conexao, contexto.bd_id, compra_id),
        fornecedores=portfolio.listar_fornecedores(conexao, contexto.bd_id),
        demandas=portfolio.listar_demandas(conexao, contexto.bd_id),
        tipos=compras.TIPOS,
        status_opcoes=compras.STATUS,
        csrf=contexto.csrf,
        pode_editar=contexto.papel in ("Admin", "Editor"),
        total_realizado=0,
        ok=ok,
        erro=erro,
    )


@roteador.get("")
def pagina(
    request: Request,
    ano: IntOpcional = None,
    busca: str = "",
    status: str = "",
    contexto: Contexto = Depends(exigir_sessao),
):
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    return renderizar(
        "compras.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        usuario=contexto.usuario,
        papel=contexto.papel,
        ano=ano or request.app.state.agora().year,
        busca=busca,
        status_filtro=status,
    )


@roteador.get("/lista")
def lista(
    request: Request,
    ano: IntOpcional = None,
    busca: str = "",
    status: str = "",
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _exigir_bd(contexto)
    return _lista(request, conexao, contexto, ano=ano, busca=busca, status_filtro=status)


@roteador.post("")
def criar(
    request: Request,
    tipo: str = Form(""),
    demanda_id: str = Form(""),
    descricao: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if tipo not in compras.TIPOS or not demanda_id.isdigit():
        return _lista(request, conexao, contexto, erro=t("compras.erro_campos"), status=400)
    try:
        compras.criar_prevista(
            conexao, contexto.bd_id, tipo, int(demanda_id), descricao, contexto.usuario.id,
            request.app.state.agora(),
        )  # fmt: skip
    except compras.ComprasInvalido as erro:
        return _lista(request, conexao, contexto, erro=str(erro), status=400)
    return _lista(request, conexao, contexto, ok=t("compras.ok_criada"))


@roteador.get("/{compra_id}")
def pagina_ordem(compra_id: int, contexto: Contexto = Depends(exigir_sessao)):
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    return renderizar(
        "compras_ordem.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        usuario=contexto.usuario,
        papel=contexto.papel,
        compra_id=compra_id,
    )


@roteador.get("/{compra_id}/detalhe")
def detalhe(
    request: Request,
    compra_id: int,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _exigir_bd(contexto)
    return _detalhe(request, conexao, contexto, compra_id)


def _numero(texto: str) -> int | None:
    return int(texto) if texto.isdigit() else None


@roteador.post("/{compra_id}")
def salvar(
    request: Request,
    compra_id: int,
    status: str = Form(""),
    numero: str = Form(""),
    fornecedor_id: str = Form(""),
    demanda_id: str = Form(""),
    descricao: str | None = Form(None),
    tipo: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if compras.achar(conexao, contexto.bd_id, compra_id) is None:
        raise HTTPException(status_code=404)
    try:
        compras.editar(
            conexao,
            contexto.bd_id,
            compra_id,
            contexto.usuario.id,
            request.app.state.agora(),
            status=status or None,
            numero=numero or None,
            fornecedor_id=_numero(fornecedor_id),
            demanda_id=_numero(demanda_id),
            descricao=descricao,
            tipo=tipo or None,
        )
    except compras.ComprasInvalido as erro:
        return _detalhe(request, conexao, contexto, compra_id, erro=str(erro), status=400)
    return _detalhe(request, conexao, contexto, compra_id, ok=t("compras.ok_salva"))


@roteador.post("/{compra_id}/valores")
def salvar_valor(
    request: Request,
    compra_id: int,
    mes: str = Form(""),
    valor: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if compras.achar(conexao, contexto.bd_id, compra_id) is None:
        raise HTTPException(status_code=404)
    try:
        centavos = i18n.ler_moeda(valor)
    except ValueError:
        return _detalhe(
            request, conexao, contexto, compra_id, erro=t("compras.erro_valor"), status=400
        )
    try:
        compras.definir_valor(
            conexao, contexto.bd_id, compra_id, mes, centavos, contexto.usuario.id,
            request.app.state.agora(),
        )  # fmt: skip
    except compras.ComprasInvalido as erro:
        status = 409 if "fechado" in str(erro) else 400
        return _detalhe(request, conexao, contexto, compra_id, erro=str(erro), status=status)
    return _detalhe(request, conexao, contexto, compra_id, ok=t("compras.ok_valor"))


@roteador.post("/{compra_id}/cancelar")
def cancelar(
    request: Request,
    compra_id: int,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if compras.achar(conexao, contexto.bd_id, compra_id) is None:
        raise HTTPException(status_code=404)
    try:
        compras.editar(
            conexao, contexto.bd_id, compra_id, contexto.usuario.id, request.app.state.agora(),
            status="cancelada",
        )  # fmt: skip
    except compras.ComprasInvalido as erro:
        return _detalhe(request, conexao, contexto, compra_id, erro=str(erro), status=409)
    return _detalhe(request, conexao, contexto, compra_id, ok=t("compras.ok_cancelada"))
