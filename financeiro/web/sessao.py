"""Dependências de sessão: quem está logado, em qual BD, com qual papel."""

import hmac
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from financeiro import autenticacao, store
from financeiro.i18n import t
from financeiro.store import acesso

NOME_COOKIE = "financeiro_sessao"


@dataclass(frozen=True)
class Contexto:
    token: str
    usuario: acesso.Usuario
    csrf: str
    bd_id: int | None
    bd_nome: str | None
    papel: str | None


def conexao_db(request: Request) -> Iterator[store.Conexao]:
    conexao = store.abrir(request.app.state.cfg.caminho_bd)
    try:
        yield conexao
    finally:
        conexao.close()


def contexto_opcional(
    request: Request, conexao: store.Conexao = Depends(conexao_db)
) -> Contexto | None:
    """Contexto da sessão válida, ou None. Cookie adulterado ou expirado vale como sem sessão."""
    valor = request.cookies.get(NOME_COOKIE)
    if not valor:
        return None
    token = autenticacao.abrir_assinatura(valor, request.app.state.segredo)
    if token is None:
        return None
    sessao = autenticacao.sessao_do_token(conexao, token, request.app.state.agora())
    if sessao is None:
        return None
    usuario = acesso.achar_usuario(conexao, sessao.usuario_id)
    if usuario is None:
        return None
    papel = acesso.papel_do(conexao, sessao.bd_id, usuario.id) if sessao.bd_id else None
    bd_id = sessao.bd_id if papel else None  # perdeu o vínculo: volta à escolha de BD
    nome = acesso.nome_do_bd(conexao, bd_id) if bd_id else None
    return Contexto(token, usuario, sessao.csrf, bd_id, nome, papel)


def exigir_sessao(contexto: Contexto | None = Depends(contexto_opcional)) -> Contexto:
    if contexto is None:
        raise HTTPException(status_code=401, detail=t("auth.sem_sessao"))
    return contexto


async def exigir_csrf(request: Request, contexto: Contexto = Depends(exigir_sessao)) -> Contexto:
    """POST precisa do token da sessão, no campo `csrf` do formulário ou no cabeçalho do HTMX."""
    enviado = request.headers.get("x-csrf-token")
    if enviado is None:
        form = await request.form()
        enviado = str(form.get("csrf", ""))
    if not enviado or not hmac.compare_digest(enviado, contexto.csrf):
        raise HTTPException(status_code=403, detail=t("auth.erro_csrf"))
    return contexto


def _com_bd(contexto: Contexto) -> Contexto:
    if contexto.bd_id is None:
        raise HTTPException(status_code=409, detail=t("papel.sem_bd"))
    return contexto


async def exigir_edicao(contexto: Contexto = Depends(exigir_csrf)) -> Contexto:
    """Admin ou Editor do BD atual. Leitor só consulta."""
    _com_bd(contexto)
    if contexto.papel not in ("Admin", "Editor"):
        raise HTTPException(status_code=403, detail=t("papel.leitor_so_consulta"))
    return contexto


async def exigir_admin(contexto: Contexto = Depends(exigir_csrf)) -> Contexto:
    """Admin do BD atual."""
    _com_bd(contexto)
    if contexto.papel != "Admin":
        raise HTTPException(status_code=403, detail=t("papel.so_admin"))
    return contexto
