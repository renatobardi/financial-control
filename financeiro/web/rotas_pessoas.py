from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from financeiro import equipe, store
from financeiro.i18n import t
from financeiro.store import cadastros, organizacao, pessoas, portfolio
from financeiro.web.sessao import Contexto, conexao_db, exigir_edicao, exigir_sessao
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/pessoas")


def _periodo(request: Request, de: str | None, ate: str | None) -> tuple[str, str]:
    ano = request.app.state.agora().year
    return (de or f"{ano}-01"), (ate or f"{ano}-12")


def _lista(
    request: Request,
    conexao: store.Conexao,
    contexto: Contexto,
    *,
    de: str | None = None,
    ate: str | None = None,
    unidade: str = "",
    busca: str = "",
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    de, ate = _periodo(request, de, ate)
    bd_id = contexto.bd_id
    agora = request.app.state.agora()
    unidade_id = int(unidade) if unidade.isdigit() else None
    try:
        linhas = equipe.listar(conexao, bd_id, de, ate, agora, unidade_id, busca)
    except ValueError:
        linhas, erro, status = [], t("cadastros.erro_mes"), 400
    ano = int(de[:4]) if de[:4].isdigit() else agora.year
    ativos = equipe.ativos_por_ano(conexao, bd_id, ano)
    orgs = organizacao.listar_orgs(conexao, bd_id)
    squads = [o for o in orgs if o.tipo == "Squad"]
    vagas = [v for v in pessoas.listar_vagas(conexao, bd_id) if v.estado == "aberta"]
    return renderizar(
        "pessoas/_lista.html",
        status,
        linhas=linhas,
        de=de,
        ate=ate,
        unidade=unidade,
        busca=busca,
        ano=ano,
        ativos_por_mes=ativos.por_mes,
        distintos=ativos.distintos,
        n_funcionarios=sum(x.vinculo == "propria" for x in linhas),
        n_terceiros=sum(x.vinculo == "consultoria" for x in linhas),
        vagas_abertas=len(vagas),
        custo_total=sum(x.custo_centavos for x in linhas),
        horas_total=sum(x.horas for x in linhas),
        unidades=orgs,
        squads=squads,
        cargos=cadastros.listar_cargos(conexao, bd_id),
        temas=portfolio.listar_temas(conexao, bd_id),
        csrf=contexto.csrf,
        pode_editar=contexto.papel in ("Admin", "Editor"),
        ok=ok,
        erro=erro,
    )


@roteador.get("")
def pagina(
    request: Request,
    de: str | None = None,
    ate: str | None = None,
    unidade: str = "",
    busca: str = "",
    contexto: Contexto = Depends(exigir_sessao),
):
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    de, ate = _periodo(request, de, ate)
    return renderizar(
        "pessoas.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        papel=contexto.papel,
        de=de,
        ate=ate,
        unidade=unidade,
        busca=busca,
    )


@roteador.get("/lista")
def lista(
    request: Request,
    de: str | None = None,
    ate: str | None = None,
    unidade: str = "",
    busca: str = "",
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    return _lista(request, conexao, contexto, de=de, ate=ate, unidade=unidade, busca=busca)


@roteador.post("")
def nova(
    request: Request,
    matricula: str = Form(""),
    nome: str = Form(""),
    org_id: str = Form(""),
    cargo_id: str = Form(""),
    tema_id: str = Form(""),
    admissao: str = Form(""),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    if not (org_id.isdigit() and cargo_id.isdigit() and tema_id.isdigit()):
        return _lista(request, conexao, contexto, erro=t("pessoas.erro_campos"), status=400)
    try:
        equipe.nova_pessoa(
            conexao, contexto.bd_id, matricula, nome, int(org_id), int(cargo_id), int(tema_id),
            admissao,
        )  # fmt: skip
    except equipe.EquipeInvalida as erro:
        return _lista(request, conexao, contexto, erro=str(erro), status=400)
    return _lista(request, conexao, contexto, ok=t("pessoas.ok_criada"))


@roteador.post("/{pessoa_id}")
def editar(
    request: Request,
    pessoa_id: int,
    org_id: str = Form(""),
    cargo_id: str = Form(""),
    tema_id: str = Form(""),
    desligamento: str | None = Form(None),
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    try:
        equipe.editar(
            conexao,
            contexto.bd_id,
            pessoa_id,
            org_id=int(org_id) if org_id.isdigit() else None,
            cargo_id=int(cargo_id) if cargo_id.isdigit() else None,
            tema_id=int(tema_id) if tema_id.isdigit() else None,
            desligamento=desligamento,
        )
    except equipe.EquipeInvalida as erro:
        status = 404 if "não encontrada" in str(erro) else 400
        return _lista(request, conexao, contexto, erro=str(erro), status=status)
    return _lista(request, conexao, contexto, ok=t("pessoas.ok_editada"))
