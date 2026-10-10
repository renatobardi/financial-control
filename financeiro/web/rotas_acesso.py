from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from financeiro import autenticacao, store
from financeiro import senha as senhas
from financeiro.i18n import t
from financeiro.store import acesso
from financeiro.web.sessao import (
    NOME_COOKIE,
    Contexto,
    conexao_db,
    contexto_opcional,
    exigir_csrf,
    exigir_sessao,
)
from financeiro.web.templates import renderizar

roteador = APIRouter()


def _tema(contexto: Contexto | None) -> str:
    return contexto.usuario.tema if contexto else "sistema"


@roteador.get("/login")
def pagina_login(contexto: Contexto | None = Depends(contexto_opcional)):
    if contexto:
        return RedirectResponse("/", status_code=303)
    return renderizar("login.html", tema="sistema", csrf=None, erro=None, email="")


@roteador.post("/login")
def entrar(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    conexao: store.Conexao = Depends(conexao_db),
):
    app = request.app
    try:
        token, sessao = autenticacao.entrar(
            conexao, email, senha, app.state.agora(), app.state.cfg.max_tentativas
        )
    except autenticacao.CredenciaisInvalidas:
        return renderizar(
            "login.html",
            401,
            tema="sistema",
            csrf=None,
            email=email,
            erro=t("auth.erro_credenciais"),
        )
    except autenticacao.LimiteExcedido:
        erro = t("auth.erro_limite")
        return renderizar("login.html", 429, tema="sistema", csrf=None, email=email, erro=erro)
    bds = acesso.bds_do_usuario(conexao, sessao.usuario_id)
    destino = "/"
    escolhido = None
    if len(bds) == 1:
        escolhido = bds[0].id
    elif bds:
        usuario = acesso.achar_usuario(conexao, sessao.usuario_id)
        padrao = usuario.bd_padrao_id if usuario else None
        if padrao in {b.id for b in bds}:
            escolhido = padrao
        else:
            destino = "/bds"
    if escolhido is not None:
        autenticacao.escolher_bd(conexao, token, escolhido)
    resposta = RedirectResponse(destino, status_code=303)
    resposta.set_cookie(
        NOME_COOKIE,
        autenticacao.assinar(token, app.state.segredo),
        max_age=int(autenticacao.DURACAO_SESSAO.total_seconds()),
        httponly=True,
        secure=app.state.cfg.cookie_seguro,
        samesite="lax",
        path="/",
    )
    return resposta


_SENHA_MINIMA = 8


@roteador.get("/conta")
def pagina_conta():
    return renderizar("conta.html", tema="sistema", csrf=None, erro=None, nome="", email="")


@roteador.post("/conta")
def criar_conta(
    nome: str = Form(""),
    email: str = Form(""),
    senha: str = Form(""),
    confirmar: str = Form(""),
    conexao: store.Conexao = Depends(conexao_db),
):
    """Cria a conta, ou ativa a conta pendente de um convite (mesmo e-mail)."""

    def recusar(status: int, chave: str):
        return renderizar(
            "conta.html", status, tema="sistema", csrf=None, erro=t(chave), nome=nome, email=email
        )

    email = email.strip()
    if not nome.strip() or "@" not in email:
        return recusar(400, "conta.erro_nome")
    if len(senha) < _SENHA_MINIMA:
        return recusar(400, "conta.erro_senha_curta")
    if senha != confirmar:
        return recusar(400, "conta.erro_senha_diferente")
    existente = acesso.achar_usuario_por_email(conexao, email)
    if existente is not None and existente.senha_hash is not None:
        return recusar(409, "conta.erro_ja_ativa")
    hash_novo = senhas.gerar_hash(senha)
    if existente is None:
        acesso.criar_usuario(conexao, email, nome.strip(), hash_novo)
    else:
        acesso.atualizar_perfil(conexao, existente.id, nome.strip())
        acesso.definir_senha(conexao, existente.id, hash_novo)
    return RedirectResponse("/login", status_code=303)


@roteador.get("/")
def inicio(contexto: Contexto | None = Depends(contexto_opcional)):
    if contexto is None:
        return RedirectResponse("/login", status_code=303)
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    return renderizar(
        "inicio.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        usuario=contexto.usuario,
        bd_nome=contexto.bd_nome,
        papel=contexto.papel,
    )


@roteador.get("/bds")
def escolher_bd(
    contexto: Contexto = Depends(exigir_sessao), conexao: store.Conexao = Depends(conexao_db)
):
    return renderizar(
        "bds.html",
        tema=_tema(contexto),
        csrf=contexto.csrf,
        bds=acesso.bds_do_usuario(conexao, contexto.usuario.id),
    )


@roteador.post("/bds/{bd_id}")
def trocar_bd(
    bd_id: int,
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    if acesso.papel_do(conexao, bd_id, contexto.usuario.id) is None:
        raise HTTPException(status_code=403, detail=t("bds.nao_e_membro"))
    autenticacao.escolher_bd(conexao, contexto.token, bd_id)
    return RedirectResponse("/", status_code=303)


@roteador.post("/sair")
def sair(contexto: Contexto = Depends(exigir_csrf), conexao: store.Conexao = Depends(conexao_db)):
    autenticacao.sair(conexao, contexto.token)
    resposta = RedirectResponse("/login", status_code=303)
    resposta.delete_cookie(NOME_COOKIE, path="/")
    return resposta
