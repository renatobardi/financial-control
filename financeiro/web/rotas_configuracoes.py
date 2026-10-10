from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from financeiro import membros, senha, store
from financeiro.i18n import t
from financeiro.store import acesso
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


def _pagina(
    conexao: store.Conexao,
    contexto: Contexto,
    *,
    ok: str | None = None,
    erro: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    usuario = acesso.achar_usuario(conexao, contexto.usuario.id) or contexto.usuario
    eh_admin = contexto.papel == "Admin" and contexto.bd_id is not None
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
        membros=acesso.membros_do_bd(conexao, contexto.bd_id) if eh_admin else [],
        pedidos_abertos=acesso.pedidos_abertos(conexao, contexto.bd_id) if eh_admin else [],
        temas=TEMAS,
        formatos=FORMATOS,
        telas=TELAS,
        papeis=PAPEIS,
        ok=ok,
        erro=erro,
    )


@roteador.get("")
def configuracoes(
    contexto: Contexto = Depends(exigir_sessao), conexao: store.Conexao = Depends(conexao_db)
):
    return _pagina(conexao, contexto)


@roteador.post("/perfil")
def salvar_perfil(
    nome: str = Form(""),
    contexto: Contexto = Depends(exigir_csrf),
    conexao: store.Conexao = Depends(conexao_db),
):
    if not nome.strip():
        return _pagina(conexao, contexto, erro=t("conta.erro_nome"), status=400)
    acesso.atualizar_perfil(conexao, contexto.usuario.id, nome.strip())
    return _pagina(conexao, contexto, ok=t("configuracoes.ok_perfil"))


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
        return _pagina(conexao, contexto, erro=t("configuracoes.erro_senha_atual"), status=400)
    if len(nova) < SENHA_MINIMA:
        return _pagina(conexao, contexto, erro=t("conta.erro_senha_curta"), status=400)
    if nova != confirmar:
        return _pagina(conexao, contexto, erro=t("conta.erro_senha_diferente"), status=400)
    acesso.definir_senha(conexao, usuario.id, senha.gerar_hash(nova))
    return _pagina(conexao, contexto, ok=t("configuracoes.ok_senha"))


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
        return _pagina(conexao, contexto, erro=t("configuracoes.erro_preferencia"), status=400)
    acesso.atualizar_preferencias(
        conexao, contexto.usuario.id, tema, formato_valor, tela_inicial, padrao
    )
    return _pagina(conexao, contexto, ok=t("configuracoes.ok_preferencias"))


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
        return _pagina(conexao, contexto, erro=t("configuracoes.erro_pedido"), status=400)
    agora = request.app.state.agora().strftime("%Y-%m-%dT%H:%M:%SZ")
    acesso.criar_pedido(conexao, alvo, contexto.usuario.id, motivo.strip(), agora)
    return _pagina(conexao, contexto, ok=t("configuracoes.ok_pedido"))


@roteador.post("/convites")
def convidar(
    email: str = Form(""),
    papel: str = Form(""),
    contexto: Contexto = Depends(exigir_admin),
    conexao: store.Conexao = Depends(conexao_db),
):
    email = email.strip()
    if "@" not in email or papel not in PAPEIS:
        return _pagina(conexao, contexto, erro=t("configuracoes.erro_convite"), status=400)
    acesso.convidar(conexao, contexto.bd_id, email, papel)
    return _pagina(conexao, contexto, ok=t("configuracoes.ok_convite", email=email, papel=papel))


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
        return _pagina(conexao, contexto, erro=t("configuracoes.erro_convite"), status=400)
    try:
        membros.alterar_papel(conexao, contexto.bd_id, usuario_id, papel)
    except membros.UltimoAdmin:
        return _pagina(conexao, contexto, erro=t("configuracoes.erro_ultimo_admin"), status=409)
    return _pagina(conexao, contexto, ok=t("configuracoes.ok_membro"))


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
        return _pagina(conexao, contexto, erro=t("configuracoes.erro_ultimo_admin"), status=409)
    return _pagina(conexao, contexto, ok=t("configuracoes.ok_removido"))


@roteador.post("/pedidos/{pedido_id}/aprovar")
def aprovar_pedido(
    pedido_id: int,
    papel: str = Form("Leitor"),
    contexto: Contexto = Depends(exigir_admin),
    conexao: store.Conexao = Depends(conexao_db),
):
    if papel not in PAPEIS:
        return _pagina(conexao, contexto, erro=t("configuracoes.erro_convite"), status=400)
    try:
        membros.aprovar_pedido(conexao, contexto.bd_id, pedido_id, papel)
    except membros.PedidoInexistente:
        return _pagina(
            conexao, contexto, erro=t("configuracoes.erro_pedido_inexistente"), status=404
        )
    return _pagina(conexao, contexto, ok=t("configuracoes.ok_aprovado"))


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
            conexao, contexto, erro=t("configuracoes.erro_pedido_inexistente"), status=404
        )
    return _pagina(conexao, contexto, ok=t("configuracoes.ok_recusado"))
