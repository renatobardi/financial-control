from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from financeiro import cenarios, forecast, graficos, i18n, orcamento, realizado, store
from financeiro.i18n import t
from financeiro.store import cenarios as armazem
from financeiro.store import organizacao, pessoas, portfolio
from financeiro.web.parametros import IntOpcional
from financeiro.web.sessao import Contexto, conexao_db, exigir_edicao, exigir_sessao
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/forecast")


def _exigir_bd(contexto: Contexto) -> int:
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    return contexto.bd_id


def _escolher(conexao: store.Conexao, bd_id: int, cenario_id: int | None):
    todos = cenarios.garantir_padrao(conexao, bd_id)
    escolhido = next((c for c in todos if c.id == cenario_id), None)
    return todos, escolhido or todos[0]


def _painel(
    request: Request,
    conexao: store.Conexao,
    contexto: Contexto,
    *,
    cenario_id: int | None = None,
    base: str = "bruto",
    rev: IntOpcional = None,
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    bd_id = contexto.bd_id
    agora = request.app.state.agora()
    ano = agora.year
    base = base if base in realizado.BASES else "bruto"
    todos, cenario = _escolher(conexao, bd_id, cenario_id)
    comp = forecast.composicao(conexao, bd_id, ano, cenario, base, agora, rev)
    resumo = forecast.resumo(conexao, bd_id, ano, cenario, base, agora, rev)
    nomes = {e.chave: e.nome for e in comp.elementos}
    nomes["__saldo"] = t("forecast.legenda_disponivel")
    svg = graficos.treemap_svg(
        comp.blocos,
        nomes,
        forecast.LARGURA_TREEMAP,
        forecast.ALTURA_TREEMAP,
        t("forecast.titulo"),
        {e.chave: e.realizado for e in comp.incluidos},
    )
    orgs = organizacao.listar_orgs(conexao, bd_id)
    if cenario.escala_tipo == "Agrupamento":
        opcoes_escala = [(a.id, a.nome) for a in portfolio.listar_agrupamentos(conexao, bd_id)]
    else:
        tipo = "Tribo" if cenario.escala_tipo == "Tribo" else "Squad"
        opcoes_escala = [(o.id, o.nome) for o in orgs if o.tipo == tipo]
    vagas = [v for v in pessoas.listar_vagas(conexao, bd_id) if v.estado == "aberta"]
    inicios = armazem.inicios_de_vaga(conexao, bd_id, cenario.id)
    return renderizar(
        "forecast/_painel.html",
        status,
        cenarios=todos,
        cenario=cenario,
        base=base,
        rev=rev,
        revisoes=orcamento.revisoes(conexao, bd_id),
        comp=comp,
        resumo=resumo,
        svg=svg,
        bandeja=[e for e in comp.elementos if e.chave not in cenario.incluidos],
        opcoes_escala=opcoes_escala,
        vagas=vagas,
        inicios=inicios,
        percentual=i18n.percentual,
        csrf=contexto.csrf,
        pode_editar=contexto.papel in ("Admin", "Editor"),
        ok=ok,
        erro=erro,
    )


@roteador.get("")
def pagina(
    cenario: IntOpcional = None,
    base: str = "bruto",
    rev: IntOpcional = None,
    contexto: Contexto = Depends(exigir_sessao),
):
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    return renderizar(
        "forecast.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        usuario=contexto.usuario,
        papel=contexto.papel,
        cenario=cenario,
        base=base,
        rev=rev,
    )


@roteador.get("/painel")
def painel(
    request: Request,
    cenario: IntOpcional = None,
    base: str = "bruto",
    rev: IntOpcional = None,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _exigir_bd(contexto)
    return _painel(request, conexao, contexto, cenario_id=cenario, base=base, rev=rev)


def _cenario_do_bd(conexao: store.Conexao, bd_id: int, cenario_id: int):
    cenario = armazem.achar(conexao, bd_id, cenario_id)
    if cenario is None:
        raise HTTPException(status_code=404)
    return cenario


@roteador.post("/cenarios")
def novo(
    request: Request,
    nome: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    cenarios.garantir_padrao(conexao, contexto.bd_id)
    existentes = len(cenarios.listar(conexao, contexto.bd_id))
    try:
        novo_id = cenarios.criar(
            conexao, contexto.bd_id, nome.strip() or f"Cenário {existentes + 1}", 10000, 10000
        )
    except cenarios.CenarioInvalido as erro:
        return _painel(request, conexao, contexto, erro=str(erro), status=400)
    return _painel(request, conexao, contexto, cenario_id=novo_id, ok=t("forecast.ok_criado"))


@roteador.post("/cenarios/{cenario_id}/duplicar")
def duplicar(
    request: Request,
    cenario_id: int,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _cenario_do_bd(conexao, contexto.bd_id, cenario_id)
    try:
        novo_id = cenarios.duplicar(conexao, contexto.bd_id, cenario_id)
    except cenarios.CenarioInvalido as erro:
        return _painel(
            request, conexao, contexto, cenario_id=cenario_id, erro=str(erro), status=400
        )
    return _painel(request, conexao, contexto, cenario_id=novo_id, ok=t("forecast.ok_duplicado"))


@roteador.post("/cenarios/{cenario_id}/remover")
def remover(
    request: Request,
    cenario_id: int,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _cenario_do_bd(conexao, contexto.bd_id, cenario_id)
    try:
        cenarios.remover(conexao, contexto.bd_id, cenario_id)
    except cenarios.CenarioInvalido as erro:
        return _painel(
            request, conexao, contexto, cenario_id=cenario_id, erro=str(erro), status=409
        )
    return _painel(request, conexao, contexto, ok=t("forecast.ok_removido"))


@roteador.post("/cenarios/{cenario_id}")
async def salvar(
    request: Request,
    cenario_id: int,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _cenario_do_bd(conexao, contexto.bd_id, cenario_id)
    form = await request.form()
    campos: dict[str, object] = {}
    try:
        campos["nome"] = str(form.get("nome", "")).strip()
        campos["fator_pessoas"] = i18n.ler_percentual(str(form.get("fator_pessoas", "")))
        campos["fator_compras"] = i18n.ler_percentual(str(form.get("fator_compras", "")))
    except ValueError:
        return _painel(
            request, conexao, contexto, cenario_id=cenario_id,
            erro=t("forecast.erro_percentual"), status=400,
        )  # fmt: skip
    trimestres = sum(1 << (int(q) - 1) for q in form.getlist("tri") if str(q) in "1234")
    campos["trimestres"] = trimestres or 15
    tipo = str(form.get("escala_tipo", "PDD"))
    campos["escala_tipo"] = tipo if tipo in ("PDD", "Agrupamento", "Tribo", "Squad") else "PDD"
    ref = str(form.get("escala_ref", ""))
    campos["escala_ref"] = int(ref) if ref.isdigit() and campos["escala_tipo"] != "PDD" else None
    valor = str(form.get("escala_valor", "")).strip()
    try:
        campos["escala_valor_centavos"] = i18n.ler_moeda(valor) if valor else None
    except ValueError:
        return _painel(
            request, conexao, contexto, cenario_id=cenario_id,
            erro=t("forecast.erro_valor"), status=400,
        )  # fmt: skip
    elemento = str(form.get("elemento_tipo", "Agrupamento"))
    campos["elemento_tipo"] = (
        elemento if elemento in ("Agrupamento", "Squad", "Tribo") else "Agrupamento"
    )
    try:
        cenarios.atualizar(conexao, contexto.bd_id, cenario_id, **campos)
    except cenarios.CenarioInvalido as erro:
        return _painel(
            request, conexao, contexto, cenario_id=cenario_id, erro=str(erro), status=400
        )
    return _painel(request, conexao, contexto, cenario_id=cenario_id, ok=t("forecast.salvo"))


@roteador.post("/cenarios/{cenario_id}/incluir")
def incluir(
    request: Request,
    cenario_id: int,
    chave: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    cenario = _cenario_do_bd(conexao, contexto.bd_id, cenario_id)
    agora = request.app.state.agora()
    try:
        forecast.incluir(conexao, contexto.bd_id, agora.year, cenario, chave, "bruto", agora)
    except cenarios.CenarioInvalido as erro:
        return _painel(
            request, conexao, contexto, cenario_id=cenario_id, erro=str(erro), status=409
        )
    return _painel(request, conexao, contexto, cenario_id=cenario_id, ok=t("forecast.ok_incluido"))


@roteador.post("/cenarios/{cenario_id}/retirar")
def retirar(
    request: Request,
    cenario_id: int,
    chave: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    cenario = _cenario_do_bd(conexao, contexto.bd_id, cenario_id)
    forecast.retirar(conexao, contexto.bd_id, cenario, chave)
    return _painel(request, conexao, contexto, cenario_id=cenario_id, ok=t("forecast.ok_retirado"))


@roteador.post("/cenarios/{cenario_id}/vagas/{vaga_id}")
def inicio_da_vaga(
    request: Request,
    cenario_id: int,
    vaga_id: int,
    mes: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _cenario_do_bd(conexao, contexto.bd_id, cenario_id)
    from financeiro import vigencia

    try:
        vigencia.validar_mes(mes)
        cenarios.definir_inicio_vaga(conexao, contexto.bd_id, cenario_id, vaga_id, mes)
    except (ValueError, cenarios.CenarioInvalido):
        return _painel(
            request, conexao, contexto, cenario_id=cenario_id,
            erro=t("forecast.erro_mes"), status=400,
        )  # fmt: skip
    return _painel(request, conexao, contexto, cenario_id=cenario_id, ok=t("forecast.ok_vaga"))
