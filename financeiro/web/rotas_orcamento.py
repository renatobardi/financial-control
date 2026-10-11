from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from financeiro import i18n, orcamento, realizado, store
from financeiro.i18n import t
from financeiro.store import portfolio
from financeiro.web.parametros import IntOpcional
from financeiro.web.sessao import Contexto, conexao_db, exigir_edicao, exigir_sessao
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/orcamento")


def _exigir_bd(contexto: Contexto) -> int:
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    return contexto.bd_id


def _tabela(
    request: Request,
    conexao: store.Conexao,
    contexto: Contexto,
    *,
    rev: IntOpcional = None,
    base: str = "bruto",
    comparar: IntOpcional = None,
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    agora = request.app.state.agora()
    bd_id = contexto.bd_id
    todas = orcamento.revisoes(conexao, bd_id)
    base = base if base in realizado.BASES else "bruto"
    selecionada = next((r for r in todas if r.id == rev), None)
    if selecionada is None and todas:
        selecionada = orcamento.rascunho(conexao, bd_id) or orcamento.vigente(conexao, bd_id)
    vigente = orcamento.vigente(conexao, bd_id)
    linhas, anteriores = [], {}
    markup = 0
    totais_ano = {}
    if selecionada is not None:
        linhas = orcamento.linhas(conexao, bd_id, selecionada.id, agora)
        markup = orcamento.markup_da_revisao(conexao, bd_id, selecionada, agora)
        if comparar == 0:  # "sem comparação"
            base_cmp = None
        elif comparar is None:  # padrão: a revisão anterior
            posicao = next(i for i, r in enumerate(todas) if r.id == selecionada.id)
            base_cmp = todas[posicao - 1] if posicao > 0 else None
        else:
            base_cmp = next((r for r in todas if r.id == comparar), None)
        if base_cmp is not None:
            anteriores = {
                (x.iniciativa_id, x.tipo): x
                for x in orcamento.linhas(conexao, bd_id, base_cmp.id, agora)
            }
        ano = agora.year
        tabela = realizado.consultar(conexao, bd_id, ano, "iniciativa_tipo", "todas", base, agora)
        totais_ano = {linha.chave: linha.total_ano for linha in tabela.linhas}
    else:
        base_cmp = None
    valor = (lambda x: x.bruto_centavos) if base == "bruto" else (lambda x: x.liquido_centavos)
    total = sum(valor(x) for x in linhas)
    linhas_exibidas = []
    for x in linhas:
        v = valor(x)
        antes = anteriores.get((x.iniciativa_id, x.tipo))
        total_ano = totais_ano.get((x.iniciativa_id, x.tipo), 0)
        linhas_exibidas.append(
            {
                "iniciativa_id": x.iniciativa_id,
                "iniciativa": x.iniciativa,
                "tipo": x.tipo,
                "bruto": x.bruto_centavos,
                "liquido": x.liquido_centavos,
                "percentual": (i18n.percentual(v * 10_000 // total) if total else "0,00%"),
                "delta": (v - valor(antes)) if antes is not None else None,
                "total_ano": total_ano,
                "gap": orcamento.gap(v, total_ano),
            }
        )
    presentes = {(x.iniciativa_id, x.tipo) for x in linhas}
    removidas = [
        {
            "iniciativa": antes.iniciativa,
            "tipo": antes.tipo,
            "delta": -valor(antes),
        }
        for chave, antes in anteriores.items()
        if chave not in presentes
    ]
    tot_bruto = sum(x.bruto_centavos for x in linhas)
    tot_liquido = sum(x.liquido_centavos for x in linhas)
    tot_capex = sum(x.bruto_centavos for x in linhas if x.tipo == "CAPEX")
    tot_opex = sum(x.bruto_centavos for x in linhas if x.tipo == "OPEX")
    delta_total = (
        total - sum(valor(a) for a in anteriores.values()) if base_cmp is not None else None
    )
    pode_nova = (
        orcamento.rascunho(conexao, bd_id) is None and len(todas) < orcamento.LIMITE_REVISOES
    )
    return renderizar(
        "orcamento/_tabela.html",
        status,
        formato=contexto.usuario.formato_valor,
        revisoes=todas,
        selecionada=selecionada,
        vigente=vigente,
        linhas=linhas_exibidas,
        total=total,
        base=base,
        comparar=base_cmp,
        markup=markup,
        iniciativas=portfolio.listar_iniciativas(conexao, bd_id),
        tipos=orcamento.TIPOS,
        tot_bruto=tot_bruto,
        tot_liquido=tot_liquido,
        tot_capex=tot_capex,
        tot_opex=tot_opex,
        removidas=removidas,
        delta_total=delta_total,
        pode_nova=pode_nova,
        pct_capex=(tot_capex * 100 // tot_bruto) if tot_bruto else 0,
        pct_opex=(tot_opex * 100 // tot_bruto) if tot_bruto else 0,
        csrf=contexto.csrf,
        pode_editar=contexto.papel in ("Admin", "Editor"),
        ok=ok,
        erro=erro,
    )


@roteador.get("")
def pagina(
    rev: IntOpcional = None,
    base: str = "bruto",
    comparar: IntOpcional = None,
    contexto: Contexto = Depends(exigir_sessao),
):
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    return renderizar(
        "orcamento.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        usuario=contexto.usuario,
        papel=contexto.papel,
        rev=rev,
        base=base,
        comparar=comparar,
    )


@roteador.get("/tabela")
def tabela(
    request: Request,
    rev: IntOpcional = None,
    base: str = "bruto",
    comparar: IntOpcional = None,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    _exigir_bd(contexto)
    return _tabela(request, conexao, contexto, rev=rev, base=base, comparar=comparar)


def _recusa(request, conexao, contexto, erro: orcamento.OrcamentoInvalido, rev, status=409):
    return _tabela(request, conexao, contexto, rev=rev, erro=str(erro), status=status)


@roteador.post("/revisoes")
def nova_revisao(
    request: Request,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    try:
        revisao = orcamento.nova_revisao(conexao, contexto.bd_id, request.app.state.agora())
    except orcamento.OrcamentoInvalido as erro:
        return _recusa(request, conexao, contexto, erro, None)
    return _tabela(
        request, conexao, contexto, rev=revisao.id,
        ok=t("orcamento.ok_revisao", rotulo=revisao.rotulo),
    )  # fmt: skip


@roteador.post("/{rev}/linhas")
def salvar_linha(
    request: Request,
    rev: int,
    iniciativa_id: str = Form(""),
    tipo: str = Form(""),
    valor: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if not iniciativa_id.isdigit() or not tipo:
        return _tabela(
            request, conexao, contexto, rev=rev, erro=t("orcamento.erro_linha"), status=400
        )
    try:
        centavos = i18n.ler_moeda(valor)
    except ValueError:
        return _tabela(
            request, conexao, contexto, rev=rev, erro=t("orcamento.erro_valor"), status=400
        )
    try:
        orcamento.definir_linha(conexao, contexto.bd_id, rev, int(iniciativa_id), tipo, centavos)
    except orcamento.OrcamentoInvalido as erro:
        mensagem = str(erro)
        status = 409 if "só leitura" in mensagem else 400
        return _tabela(request, conexao, contexto, rev=rev, erro=mensagem, status=status)
    return _tabela(request, conexao, contexto, rev=rev, ok=t("orcamento.ok_linha"))


@roteador.post("/{rev}/linhas/remover")
def remover_linha(
    request: Request,
    rev: int,
    iniciativa_id: str = Form(""),
    tipo: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if not iniciativa_id.isdigit():
        return _tabela(
            request, conexao, contexto, rev=rev, erro=t("orcamento.erro_linha"), status=400
        )
    try:
        orcamento.remover_linha(conexao, contexto.bd_id, rev, int(iniciativa_id), tipo)
    except orcamento.OrcamentoInvalido as erro:
        return _recusa(request, conexao, contexto, erro, rev)
    return _tabela(request, conexao, contexto, rev=rev, ok=t("orcamento.ok_removida"))


@roteador.post("/{rev}/aprovar")
def aprovar(
    request: Request,
    rev: int,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    try:
        revisao = orcamento.aprovar(conexao, contexto.bd_id, rev, request.app.state.agora())
    except orcamento.OrcamentoInvalido as erro:
        return _recusa(request, conexao, contexto, erro, rev)
    aviso = t(
        "orcamento.ok_aprovada",
        rotulo=revisao.rotulo,
        markup=i18n.percentual(revisao.markup_centesimos_pct),
    )
    return _tabela(request, conexao, contexto, rev=rev, ok=aviso)


@roteador.post("/{rev}/descartar")
def descartar(
    request: Request,
    rev: int,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    try:
        orcamento.descartar(conexao, contexto.bd_id, rev)
    except orcamento.OrcamentoInvalido as erro:
        return _recusa(request, conexao, contexto, erro, rev)
    return _tabela(request, conexao, contexto, ok=t("orcamento.ok_descartada"))
