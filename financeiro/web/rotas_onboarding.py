from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from financeiro import onboarding, store
from financeiro.i18n import t
from financeiro.web.sessao import Contexto, conexao_db, exigir_edicao, exigir_sessao
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/onboarding")

# Para cada passo: os links de cadastro por tela (chave do rótulo, caminho) e, quando a carga
# cobre o passo, o layout. O Portfólio cobre os passos de iniciativas a temas.
_TELAS = {
    "organizacao": [("organizacao", "/cadastros?aba=organizacao")],
    "iniciativas": [("iniciativas", "/cadastros?aba=iniciativas")],
    "demandas": [("demandas", "/cadastros?aba=demandas")],
    "agrupamentos": [("agrupamentos", "/cadastros?aba=agrupamentos")],
    "temas": [("temas", "/cadastros?aba=temas")],
    "cargos": [("empresas", "/cadastros?aba=empresas"), ("cargos", "/cadastros?aba=cargos")],
    "tarifas": [("cargos", "/cadastros?aba=cargos"), ("markup", "/cadastros?aba=markup")],
    "pessoas": [("pessoas", "/pessoas")],
    "orcamento": [("orcamento", "/orcamento")],
    "compras": [("compras", "/compras")],
    "calendario": [("calendario", "/cadastros?aba=calendario")],
}
_LAYOUTS = {
    "iniciativas": "portfolio",
    "demandas": "portfolio",
    "agrupamentos": "portfolio",
    "temas": "portfolio",
    "tarifas": "tarifas",
    "pessoas": "pessoas",
    "orcamento": "pdd",
    "compras": "compras",
}


def _exigir_bd_e_papel(contexto: Contexto) -> None:
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    if contexto.papel not in ("Admin", "Editor"):
        raise HTTPException(status_code=403, detail=t("onboarding.so_admin_editor"))


@roteador.get("")
def pagina(
    contexto: Contexto = Depends(exigir_sessao), conexao: store.Conexao = Depends(conexao_db)
):
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    _exigir_bd_e_papel(contexto)
    situacao = onboarding.situacao(conexao, contexto.bd_id)
    tarifas_feitas = any(p.chave == "tarifas" and p.estado == "feito" for p in situacao.passos)
    return renderizar(
        "onboarding.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        bd_nome=contexto.bd_nome,
        usuario=contexto.usuario,
        papel=contexto.papel,
        situacao=situacao,
        tarifas_feitas=tarifas_feitas,
        telas=_TELAS,
        layouts=_LAYOUTS,
    )


@roteador.get("/progresso")
def progresso(
    ativo: int = 0,
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    """O item do menu lateral: carregado por fragmento para a casca não contar a cada tela."""
    _exigir_bd_e_papel(contexto)
    return renderizar(
        "_onboarding_item.html",
        situacao=onboarding.situacao(conexao, contexto.bd_id),
        ativo=bool(ativo),
    )


def _dispensar(
    chave: str, contexto: Contexto, conexao: store.Conexao, *, desfazer: bool
) -> RedirectResponse:
    try:
        onboarding.dispensar(conexao, contexto.bd_id, chave, desfazer=desfazer)
    except onboarding.PassoDesconhecido:
        raise HTTPException(status_code=404) from None
    except onboarding.PassoObrigatorio:
        raise HTTPException(
            status_code=400, detail=t("onboarding.erro_passo_obrigatorio")
        ) from None
    return RedirectResponse("/onboarding", status_code=303)


@roteador.post("/{chave}/dispensar")
def dispensar(
    chave: str,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    return _dispensar(chave, contexto, conexao, desfazer=False)


@roteador.post("/{chave}/desfazer")
def desfazer(
    chave: str,
    contexto: Contexto = Depends(exigir_edicao),
    conexao: store.Conexao = Depends(conexao_db),
):
    return _dispensar(chave, contexto, conexao, desfazer=True)
