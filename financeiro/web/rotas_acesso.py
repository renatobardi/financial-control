from datetime import timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from financeiro import administracao, autenticacao, cenarios, onboarding, orcamento, store
from financeiro import senha as senhas
from financeiro.i18n import t
from financeiro.store import acesso
from financeiro.web.parametros import IntOpcional
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

# Tela inicial escolhida em Configurações → rota. "Visão geral" é a raiz.
TELAS_INICIAIS = {
    "Orçamento (PDD)": "/orcamento",
    "Realizado": "/realizado",
    "Forecast": "/forecast",
    "Pessoas": "/pessoas",
    "Compras (OC/OS)": "/compras",
    "Cadastros": "/cadastros",
    "Cargas": "/cargas",
    "Fechamento": "/fechamento",
}


DURACAO_DESAFIO = timedelta(minutes=5)


def _desafio(request: Request, usuario_id: int) -> str:
    """Prova assinada de que a senha conferiu, válida por 5 min, para o passo do código."""
    expira = int((request.app.state.agora() + DURACAO_DESAFIO).timestamp())
    return autenticacao.assinar(f"2fa:{usuario_id}:{expira}", request.app.state.segredo)


def _usuario_do_desafio(request: Request, valor: str) -> int | None:
    payload = autenticacao.abrir_assinatura(valor, request.app.state.segredo)
    partes = (payload or "").split(":")
    if len(partes) != 3 or partes[0] != "2fa" or not (partes[1] + partes[2]).isdigit():
        return None
    if int(partes[2]) < int(request.app.state.agora().timestamp()):
        return None
    return int(partes[1])


def _origem(request: Request) -> str | None:
    # o nginx do host sempre sobrescreve X-Real-IP com o IP de origem
    return request.headers.get("x-real-ip") or (request.client.host if request.client else None)


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
            conexao,
            email,
            senha,
            app.state.agora(),
            app.state.cfg.max_tentativas,
            agente=request.headers.get("user-agent"),
            ip=_origem(request),
        )
    except autenticacao.SegundoFatorNecessario as precisa:
        return renderizar(
            "login_2fa.html",
            tema="sistema",
            csrf=None,
            erro=None,
            desafio=_desafio(request, precisa.usuario_id),
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
    return _concluir_login(request, conexao, token, sessao)


@roteador.post("/login/2fa")
def entrar_com_codigo(
    request: Request,
    desafio: str = Form(...),
    codigo: str = Form(...),
    conexao: store.Conexao = Depends(conexao_db),
):
    app = request.app
    usuario_id = _usuario_do_desafio(request, desafio)
    if usuario_id is None:
        return renderizar(
            "login.html", 400, tema="sistema", csrf=None, email="", erro=t("auth.erro_desafio")
        )
    try:
        token, sessao = autenticacao.concluir_segundo_fator(
            conexao,
            usuario_id,
            codigo,
            app.state.agora(),
            app.state.cfg.max_tentativas,
            agente=request.headers.get("user-agent"),
            ip=_origem(request),
        )
    except autenticacao.CredenciaisInvalidas:
        return renderizar(
            "login_2fa.html",
            401,
            tema="sistema",
            csrf=None,
            desafio=desafio,
            erro=t("auth.erro_codigo"),
        )
    except autenticacao.LimiteExcedido:
        return renderizar(
            "login.html", 429, tema="sistema", csrf=None, email="", erro=t("auth.erro_limite")
        )
    return _concluir_login(request, conexao, token, sessao)


def _concluir_login(request: Request, conexao: store.Conexao, token: str, sessao):
    app = request.app
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
        usuario = acesso.achar_usuario(conexao, sessao.usuario_id)
        destino = TELAS_INICIAIS.get(usuario.tela_inicial, "/") if usuario else "/"
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
def inicio(
    cenario: IntOpcional = None,
    base: str = "bruto",
    rev: IntOpcional = None,
    contexto: Contexto | None = Depends(contexto_opcional),
    conexao: store.Conexao = Depends(conexao_db),
):
    """Visão geral: a casca primeiro, os blocos por fragmento (lazy)."""
    if contexto is None:
        return RedirectResponse("/login", status_code=303)
    if contexto.bd_id is None:
        return RedirectResponse("/bds", status_code=303)
    if contexto.papel == "Admin" and onboarding.abrir_primeira_vez(conexao, contexto.bd_id):
        return RedirectResponse("/onboarding", status_code=303)
    todos = cenarios.garantir_padrao(conexao, contexto.bd_id)
    escolhido = next((c for c in todos if c.id == cenario), todos[0])
    return renderizar(
        "visao_geral.html",
        tema=contexto.usuario.tema,
        csrf=contexto.csrf,
        usuario=contexto.usuario,
        bd_nome=contexto.bd_nome,
        papel=contexto.papel,
        cenarios=todos,
        cenario_id=escolhido.id,
        revisoes=orcamento.revisoes(conexao, contexto.bd_id),
        base=base if base in ("bruto", "liquido") else "bruto",
        rev=rev,
    )


def _pagina_bds(
    contexto: Contexto,
    conexao: store.Conexao,
    *,
    status: int = 200,
    erro: str | None = None,
    nome: str = "",
):
    return renderizar(
        "bds.html",
        status,
        usuario=contexto.usuario,
        tema=_tema(contexto),
        csrf=contexto.csrf,
        bds=acesso.bds_do_usuario(conexao, contexto.usuario.id),
        erro=erro,
        nome=nome,
    )


@roteador.get("/bds")
def escolher_bd(
    contexto: Contexto = Depends(exigir_sessao), conexao: store.Conexao = Depends(conexao_db)
):
    return _pagina_bds(contexto, conexao)


@roteador.post("/bds")
def criar_bd(
    nome: str = Form(""),
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    """Qualquer usuário logado cria um BD, vira Admin dele e passa a usá-lo."""
    try:
        bd_id = administracao.criar_bd_do_usuario(conexao, contexto.usuario.id, nome)
    except administracao.NomeDeBdInvalido:
        return _pagina_bds(contexto, conexao, status=400, erro=t("bds.nome_invalido"), nome=nome)
    except administracao.NomeDeBdRepetido:
        return _pagina_bds(contexto, conexao, status=409, erro=t("bds.nome_repetido"), nome=nome)
    autenticacao.escolher_bd(conexao, contexto.token, bd_id)
    return RedirectResponse("/", status_code=303)


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
