from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from financeiro import autenticacao, membros, senha, store
from financeiro.i18n import t
from financeiro.store import acesso
from financeiro.web.rotas_acesso import NOME_COOKIE
from financeiro.web.sessao import (
    Contexto,
    conexao_db,
    exigir_admin,
    exigir_csrf,
    exigir_sessao,
)
from financeiro.web.templates import renderizar

roteador = APIRouter(prefix="/configuracoes")

TEMAS = ("claro", "escuro", "sistema")
FORMATOS = ("mil", "mi")
TELAS = (
    "Visão geral",
    "Orçamento (PDD)",
    "Realizado",
    "Forecast",
    "Pessoas",
    "Compras (OC/OS)",
    "Cadastros",
    "Cargas",
    "Fechamento",
)
PAPEIS = ("Admin", "Editor", "Leitor")
SENHA_MINIMA = 8
ABAS = ("perfil", "bds", "sessoes", "membros", "conta")


def _pagina(
    conexao: store.Conexao,
    contexto: Contexto,
    *,
    aba: str = "perfil",
    agora: datetime | None = None,
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    usuario = acesso.achar_usuario(conexao, contexto.usuario.id) or contexto.usuario
    eh_admin = contexto.papel == "Admin" and contexto.bd_id is not None
    if aba not in ABAS or (aba == "membros" and not eh_admin):
        aba = "perfil"
    pedidos = [
        (acesso.nome_do_bd(conexao, p.bd_id), p.motivo, p.estado)
        for p in acesso.pedidos_do_usuario(conexao, usuario.id)
    ]
    return renderizar(
        "configuracoes.html",
        status,
        tema=usuario.tema,
        csrf=contexto.csrf,
        usuario=usuario,
        bd_nome=contexto.bd_nome,
        papel=contexto.papel,
        meus_bds=acesso.bds_do_usuario(conexao, usuario.id),
        sem_vinculo=acesso.bds_sem_vinculo(conexao, usuario.id),
        meus_pedidos=pedidos,
        eh_admin=eh_admin,
        aba=aba,
        sessoes=_sessoes(conexao, contexto, agora) if aba == "sessoes" else [],
        abas=[a for a in ABAS if a != "membros" or eh_admin],
        ultimo_admin_em=set(acesso.bds_em_que_e_ultimo_admin(conexao, usuario.id)),
        usuario_id=usuario.id,
        membros=acesso.membros_do_bd(conexao, contexto.bd_id) if eh_admin else [],
        pedidos_abertos=acesso.pedidos_abertos(conexao, contexto.bd_id) if eh_admin else [],
        temas=TEMAS,
        formatos=FORMATOS,
        telas=TELAS,
        papeis=PAPEIS,
        ok=ok,
        erro=erro,
    )


def _sessoes(conexao: store.Conexao, contexto: Contexto, agora: datetime | None) -> list[dict]:
    atual = autenticacao.hash_token(contexto.token)
    abertas = autenticacao.sessoes_abertas(conexao, contexto.usuario.id, agora or datetime.now(UTC))
    return [
        {
            "id": x.id,
            "agente": x.agente or "",
            "ip": x.ip or "",
            "criada_em": x.criada_em,
            "atual": x.token_hash == atual,
        }
        for x in abertas
    ]


@roteador.get("")
def configuracoes(
    request: Request,
    aba: str = "perfil",
    contexto: Contexto = Depends(exigir_sessao),
    conexao: store.Conexao = Depends(conexao_db),
):
    return _pagina(conexao, contexto, aba=aba, agora=request.app.state.agora())


@roteador.post("/perfil")
def salvar_perfil(
    nome: str = Form(""),
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    if not nome.strip():
        return _pagina(conexao, contexto, aba="perfil", erro=t("conta.erro_nome"), status=400)
    acesso.atualizar_perfil(conexao, contexto.usuario.id, nome.strip())
    return _pagina(conexao, contexto, aba="perfil", ok=t("configuracoes.ok_perfil"))


@roteador.post("/senha")
def alterar_senha(
    atual: str = Form(""),
    nova: str = Form(""),
    confirmar: str = Form(""),
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    usuario = acesso.achar_usuario(conexao, contexto.usuario.id)
    if usuario is None or not senha.verificar(atual, usuario.senha_hash):
        return _pagina(
            conexao, contexto, aba="perfil", erro=t("configuracoes.erro_senha_atual"), status=400
        )
    if len(nova) < SENHA_MINIMA:
        return _pagina(
            conexao, contexto, aba="perfil", erro=t("conta.erro_senha_curta"), status=400
        )
    if nova != confirmar:
        return _pagina(
            conexao, contexto, aba="perfil", erro=t("conta.erro_senha_diferente"), status=400
        )
    acesso.definir_senha(conexao, usuario.id, senha.gerar_hash(nova))
    return _pagina(conexao, contexto, aba="perfil", ok=t("configuracoes.ok_senha"))


@roteador.post("/preferencias")
def salvar_preferencias(
    tema: str = Form(""),
    formato_valor: str = Form(""),
    tela_inicial: str = Form(""),
    bd_padrao_id: str = Form(""),
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    padrao = int(bd_padrao_id) if bd_padrao_id.isdigit() else None
    valido = (
        tema in TEMAS
        and formato_valor in FORMATOS
        and tela_inicial in TELAS
        and (padrao is None or acesso.papel_do(conexao, padrao, contexto.usuario.id) is not None)
    )
    if not valido:
        return _pagina(
            conexao, contexto, aba="perfil", erro=t("configuracoes.erro_preferencia"), status=400
        )
    acesso.atualizar_preferencias(
        conexao, contexto.usuario.id, tema, formato_valor, tela_inicial, padrao
    )
    return _pagina(conexao, contexto, aba="perfil", ok=t("configuracoes.ok_preferencias"))


@roteador.post("/pedido")
def pedir_acesso(
    request: Request,
    bd_id: str = Form(""),
    motivo: str = Form(""),
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    alvo = int(bd_id) if bd_id.isdigit() else None
    permitido = {b.id for b in acesso.bds_sem_vinculo(conexao, contexto.usuario.id)}
    if alvo not in permitido or not motivo.strip():
        return _pagina(
            conexao, contexto, aba="bds", erro=t("configuracoes.erro_pedido"), status=400
        )
    agora = request.app.state.agora().strftime("%Y-%m-%dT%H:%M:%SZ")
    acesso.criar_pedido(conexao, alvo, contexto.usuario.id, motivo.strip(), agora)
    return _pagina(conexao, contexto, aba="bds", ok=t("configuracoes.ok_pedido"))


@roteador.post("/convites")
def convidar(
    email: str = Form(""),
    papel: str = Form(""),
    contexto: Contexto = Depends(exigir_admin),
    conexao: store.Conexao = Depends(conexao_db),
):
    email = email.strip()
    if "@" not in email or papel not in PAPEIS:
        return _pagina(
            conexao, contexto, aba="membros", erro=t("configuracoes.erro_convite"), status=400
        )
    acesso.convidar(conexao, contexto.bd_id, email, papel)
    return _pagina(
        conexao, contexto, aba="membros", ok=t("configuracoes.ok_convite", email=email, papel=papel)
    )


def _membro_ou_404(conexao: store.Conexao, contexto: Contexto, usuario_id: int) -> None:
    if acesso.papel_do(conexao, contexto.bd_id, usuario_id) is None:
        raise HTTPException(status_code=404, detail=t("configuracoes.erro_membro"))


@roteador.post("/membros/{usuario_id}/papel")
def alterar_papel(
    usuario_id: int,
    papel: str = Form(""),
    contexto: Contexto = Depends(exigir_admin),
    conexao: store.Conexao = Depends(conexao_db),
):
    _membro_ou_404(conexao, contexto, usuario_id)
    if papel not in PAPEIS:
        return _pagina(
            conexao, contexto, aba="membros", erro=t("configuracoes.erro_convite"), status=400
        )
    try:
        membros.alterar_papel(conexao, contexto.bd_id, usuario_id, papel)
    except membros.UltimoAdmin:
        return _pagina(
            conexao, contexto, aba="membros", erro=t("configuracoes.erro_ultimo_admin"), status=409
        )
    return _pagina(conexao, contexto, aba="membros", ok=t("configuracoes.ok_membro"))


@roteador.post("/membros/{usuario_id}/remover")
def remover_membro(
    usuario_id: int,
    contexto: Contexto = Depends(exigir_admin),
    conexao: store.Conexao = Depends(conexao_db),
):
    _membro_ou_404(conexao, contexto, usuario_id)
    try:
        membros.remover(conexao, contexto.bd_id, usuario_id)
    except membros.UltimoAdmin:
        return _pagina(
            conexao, contexto, aba="membros", erro=t("configuracoes.erro_ultimo_admin"), status=409
        )
    return _pagina(conexao, contexto, aba="membros", ok=t("configuracoes.ok_removido"))


@roteador.post("/pedidos/{pedido_id}/aprovar")
def aprovar_pedido(
    pedido_id: int,
    papel: str = Form("Leitor"),
    contexto: Contexto = Depends(exigir_admin),
    conexao: store.Conexao = Depends(conexao_db),
):
    if papel not in PAPEIS:
        return _pagina(
            conexao, contexto, aba="bds", erro=t("configuracoes.erro_convite"), status=400
        )
    try:
        membros.aprovar_pedido(conexao, contexto.bd_id, pedido_id, papel)
    except membros.PedidoInexistente:
        return _pagina(
            conexao,
            contexto,
            aba="bds",
            erro=t("configuracoes.erro_pedido_inexistente"),
            status=404,
        )
    return _pagina(conexao, contexto, aba="bds", ok=t("configuracoes.ok_aprovado"))


@roteador.post("/pedidos/{pedido_id}/recusar")
def recusar_pedido(
    pedido_id: int,
    contexto: Contexto = Depends(exigir_admin),
    conexao: store.Conexao = Depends(conexao_db),
):
    try:
        membros.recusar_pedido(conexao, contexto.bd_id, pedido_id)
    except membros.PedidoInexistente:
        return _pagina(
            conexao,
            contexto,
            aba="bds",
            erro=t("configuracoes.erro_pedido_inexistente"),
            status=404,
        )
    return _pagina(conexao, contexto, aba="bds", ok=t("configuracoes.ok_recusado"))


def _bd_do_usuario(conexao: store.Conexao, contexto: Contexto, bd_id: int) -> str:
    papel = acesso.papel_do(conexao, bd_id, contexto.usuario.id)
    if papel is None:
        raise HTTPException(status_code=404, detail=t("configuracoes.erro_membro"))
    return papel


@roteador.post("/bds/{bd_id}/padrao")
def tornar_padrao(
    bd_id: int,
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    _bd_do_usuario(conexao, contexto, bd_id)
    usuario = acesso.achar_usuario(conexao, contexto.usuario.id)
    acesso.atualizar_preferencias(
        conexao, usuario.id, usuario.tema, usuario.formato_valor, usuario.tela_inicial, bd_id
    )
    return _pagina(conexao, contexto, aba="bds", ok=t("configuracoes.ok_padrao"))


@roteador.post("/bds/{bd_id}/sair")
def sair_do_bd(
    bd_id: int,
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    _bd_do_usuario(conexao, contexto, bd_id)
    try:
        membros.remover(conexao, bd_id, contexto.usuario.id)
    except membros.UltimoAdmin:
        return _pagina(
            conexao, contexto, aba="bds", erro=t("configuracoes.erro_ultimo_admin"), status=409
        )
    usuario = acesso.achar_usuario(conexao, contexto.usuario.id)
    if usuario.bd_padrao_id == bd_id:
        acesso.atualizar_preferencias(
            conexao, usuario.id, usuario.tema, usuario.formato_valor, usuario.tela_inicial, None
        )
    if contexto.bd_id == bd_id:  # saiu do BD em uso: volta à escolha de BD
        autenticacao.escolher_bd(conexao, contexto.token, None)
        return RedirectResponse("/bds", status_code=303)
    return _pagina(conexao, contexto, aba="bds", ok=t("configuracoes.ok_saiu"))


@roteador.post("/conta/excluir")
def excluir_conta(
    confirmar: str = Form(""),
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    usuario = acesso.achar_usuario(conexao, contexto.usuario.id)
    if confirmar.strip().lower() != usuario.email.lower():
        return _pagina(
            conexao, contexto, aba="conta", erro=t("configuracoes.erro_confirmar_conta"), status=400
        )
    if acesso.bds_em_que_e_ultimo_admin(conexao, usuario.id):
        return _pagina(
            conexao,
            contexto,
            aba="conta",
            erro=t("configuracoes.erro_conta_ultimo_admin"),
            status=409,
        )
    acesso.excluir_conta(conexao, usuario.id)
    resposta = RedirectResponse("/login", status_code=303)
    resposta.delete_cookie(NOME_COOKIE, path="/")
    return resposta


@roteador.post("/sessoes/encerrar-outras")
def encerrar_outras_sessoes(
    request: Request,
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    n = autenticacao.encerrar_outras(conexao, contexto.usuario.id, contexto.token)
    return _pagina(
        conexao,
        contexto,
        aba="sessoes",
        agora=request.app.state.agora(),
        ok=t("configuracoes.ok_sessoes_encerradas", n=n),
    )


@roteador.post("/sessoes/{sessao_id}/encerrar")
def encerrar_sessao(
    request: Request,
    sessao_id: int,
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    agora = request.app.state.agora()
    abertas = autenticacao.sessoes_abertas(conexao, contexto.usuario.id, agora)
    alvo = next((x for x in abertas if x.id == sessao_id), None)
    if alvo is None:
        raise HTTPException(status_code=404, detail=t("configuracoes.erro_sessao"))
    if alvo.token_hash == autenticacao.hash_token(contexto.token):
        return _pagina(
            conexao,
            contexto,
            aba="sessoes",
            agora=agora,
            erro=t("configuracoes.erro_sessao_atual"),
            status=400,
        )
    autenticacao.encerrar_sessao(conexao, contexto.usuario.id, sessao_id)
    return _pagina(
        conexao, contexto, aba="sessoes", agora=agora, ok=t("configuracoes.ok_sessao_encerrada")
    )
