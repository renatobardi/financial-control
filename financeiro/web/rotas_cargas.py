import csv
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from financeiro import store
from financeiro.cargas import motor
from financeiro.cargas.layouts import LAYOUTS
from financeiro.i18n import t
from financeiro.store import cargas as armazem
from financeiro.web.sessao import (
    Contexto,
    conexao_db,
    exigir_admin,
    exigir_edicao,
    exigir_sessao,
)
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/cargas")

LIMITE_BYTES = 5 * 1024 * 1024
_ORDEM = ("horas", "compras", "pdd", "pessoas", "tarifas", "portfolio")


def _exigir_bd(contexto: Contexto) -> int:
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    return contexto.bd_id


def _historico(request: Request, conexao: store.Conexao, contexto: Contexto) -> HTMLResponse:
    return renderizar(
        "cargas/_historico.html",
        cargas=armazem.listar_cargas(conexao, contexto.bd_id),
        csrf=contexto.csrf,
        pode_editar=contexto.papel in ("Admin", "Editor"),
    )


def _relatorio(
    conexao: store.Conexao,
    contexto: Contexto,
    *,
    carga_id: int | None = None,
    pre: motor.Relatorio | None = None,
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    """Relatório sintético e analítico de uma carga gravada ou de uma pré-validação."""
    dados: dict | None = None
    if carga_id is not None:
        carga = armazem.achar_carga(conexao, contexto.bd_id, carga_id)
        if carga is None:
            raise HTTPException(status_code=404, detail=t("cargas.erro_nao_encontrada"))
        rejeicoes = armazem.rejeicoes_da_carga(conexao, contexto.bd_id, carga_id)
        dados = {
            "carga_id": carga.id, "layout": carga.layout, "arquivo": carga.arquivo,
            "lidas": carga.lidas, "inseridas": carga.inseridas, "atualizadas": carga.atualizadas,
            "iguais": carga.iguais, "rejeitadas": carga.rejeitadas, "horas": carga.horas,
            "valor": carga.valor_centavos, "estado": carga.estado, "pre": False,
            "rejeicoes": [
                {"linha": r.linha, "regra": r.regra, "mensagem": r.mensagem,
                 "aprovavel": r.aprovavel, "aprovada": r.aprovada, "grupo": r.grupo}
                for r in rejeicoes
            ],
        }  # fmt: skip
    elif pre is not None:
        dados = {
            "carga_id": None, "layout": pre.layout, "arquivo": "", "lidas": pre.lidas,
            "inseridas": pre.inseridas, "atualizadas": pre.atualizadas, "iguais": pre.iguais,
            "rejeitadas": pre.rejeitadas, "horas": pre.horas, "valor": pre.valor_centavos,
            "estado": "ativa", "pre": True,
            "rejeicoes": [
                {"linha": r.linha, "regra": r.regra, "mensagem": r.mensagem,
                 "aprovavel": r.aprovavel, "aprovada": False, "grupo": r.grupo}
                for r in pre.rejeicoes
            ],
        }  # fmt: skip
    resposta = renderizar(
        "cargas/_relatorio.html",
        status,
        r=dados,
        ok=ok,
        erro=erro,
        csrf=contexto.csrf,
        pode_editar=contexto.papel in ("Admin", "Editor"),
        eh_admin=contexto.papel == "Admin",
    )
    if ok:
        resposta.headers["HX-Trigger"] = "carga-atualizada"
    return resposta


@roteador.get("")
def pagina(contexto: Contexto = Depends(exigir_sessao)):
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    return renderizar(
        "cargas.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        usuario=contexto.usuario,
        papel=contexto.papel,
        layouts=[(chave, LAYOUTS[chave]) for chave in _ORDEM],
        pode_editar=contexto.papel in ("Admin", "Editor"),
    )


@roteador.get("/historico")
def historico(
    request: Request,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _exigir_bd(contexto)
    return _historico(request, conexao, contexto)


@roteador.get("/modelo/{layout}.csv")
def modelo(layout: str, contexto: Contexto = Depends(exigir_sessao)):
    definicao = LAYOUTS.get(layout)
    if definicao is None:
        raise HTTPException(status_code=404)
    conteudo = "﻿" + ";".join(definicao.colunas) + "\n"
    return Response(
        conteudo.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="modelo_{layout}.csv"'},
    )


@roteador.get("/{carga_id}")
def detalhe(
    carga_id: int,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _exigir_bd(contexto)
    return _relatorio(conexao, contexto, carga_id=carga_id)


@roteador.get("/{carga_id}/rejeicoes.csv")
def baixar_rejeicoes(
    carga_id: int,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    bd_id = _exigir_bd(contexto)
    if armazem.achar_carga(conexao, bd_id, carga_id) is None:
        raise HTTPException(status_code=404, detail=t("cargas.erro_nao_encontrada"))
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\n")
    escritor.writerow(["linha", "regra", "mensagem"])
    for r in armazem.rejeicoes_da_carga(conexao, bd_id, carga_id):
        escritor.writerow([r.linha, r.regra, r.mensagem])
    return Response(
        ("﻿" + saida.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="rejeicoes_{carga_id}.csv"'},
    )


async def _enviar(
    request: Request,
    layout: str,
    arquivo: UploadFile,
    contexto: Contexto,
    conexao: store.Conexao,
    aplicar: bool,
):
    bd_id = _exigir_bd(contexto)
    if layout not in LAYOUTS:
        return _relatorio(conexao, contexto, erro=t("cargas.erro_layout"), status=400)
    conteudo = await arquivo.read(LIMITE_BYTES + 1)
    if not conteudo:
        return _relatorio(conexao, contexto, erro=t("cargas.erro_sem_arquivo"), status=400)
    if len(conteudo) > LIMITE_BYTES:
        return _relatorio(conexao, contexto, erro=t("cargas.erro_arquivo_grande"), status=400)
    try:
        rel = motor.processar(
            conexao, bd_id, layout, conteudo, arquivo.filename or "carga.csv",
            contexto.usuario.id, request.app.state.agora(), aplicar=aplicar,
        )  # fmt: skip
    except motor.CargaInvalida as erro:
        return _relatorio(conexao, contexto, erro=f"{erro.regra}: {erro}", status=400)
    if not aplicar:
        return _relatorio(conexao, contexto, pre=rel)
    aviso = t(
        "cargas.ok_carregada",
        id=rel.carga_id,
        inseridas=rel.inseridas,
        atualizadas=rel.atualizadas,
        iguais=rel.iguais,
        rejeitadas=rel.rejeitadas,
    )
    return _relatorio(conexao, contexto, carga_id=rel.carga_id, ok=aviso)


@roteador.post("/validar")
async def validar(
    request: Request,
    layout: str = Form(""),
    arquivo: UploadFile = File(...),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    return await _enviar(request, layout, arquivo, contexto, conexao, aplicar=False)


@roteador.post("")
async def carregar(
    request: Request,
    layout: str = Form(""),
    arquivo: UploadFile = File(...),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    return await _enviar(request, layout, arquivo, contexto, conexao, aplicar=True)


@roteador.post("/{carga_id}/desfazer")
def desfazer(
    request: Request,
    carga_id: int,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    bd_id = _exigir_bd(contexto)
    if armazem.achar_carga(conexao, bd_id, carga_id) is None:
        raise HTTPException(status_code=404, detail=t("cargas.erro_nao_encontrada"))
    try:
        motor.desfazer(conexao, bd_id, carga_id, request.app.state.agora())
    except motor.CargaInvalida as erro:
        return _relatorio(
            conexao, contexto, carga_id=carga_id, erro=f"{erro.regra}: {erro}", status=409
        )
    return _relatorio(conexao, contexto, carga_id=carga_id, ok=t("cargas.ok_desfeita", id=carga_id))


@roteador.post("/{carga_id}/aprovar")
def aprovar(
    request: Request,
    carga_id: int,
    grupo: str = Form(""),
    contexto: Contexto = Depends(exigir_admin),
    conexao: store.Conexao = Depends(conexao_db),
):
    bd_id = _exigir_bd(contexto)
    if armazem.achar_carga(conexao, bd_id, carga_id) is None:
        raise HTTPException(status_code=404, detail=t("cargas.erro_nao_encontrada"))
    try:
        horas = motor.aprovar_extras(conexao, bd_id, carga_id, grupo, request.app.state.agora())
    except motor.CargaInvalida as erro:
        return _relatorio(
            conexao, contexto, carga_id=carga_id, erro=f"{erro.regra}: {erro}", status=409
        )
    return _relatorio(conexao, contexto, carga_id=carga_id, ok=t("cargas.ok_extras", horas=horas))
