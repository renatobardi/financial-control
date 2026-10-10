"""Login, sessão e cookie assinado. Sem SQL: tudo passa por `store.sessao` e `store.acesso`."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from financeiro import senha
from financeiro.store import Conexao, acesso, sessao
from financeiro.store.sessao import Sessao

DURACAO_SESSAO = timedelta(hours=8)
JANELA_TENTATIVAS = timedelta(minutes=15)
MAX_TENTATIVAS = 5

# Hash de uma senha qualquer, para gastar o mesmo tempo quando o e-mail não existe.
_HASH_FALSO = senha.gerar_hash("nao-e-uma-senha")


class CredenciaisInvalidas(Exception):
    """E-mail ou senha não conferem. A mesma exceção vale para e-mail inexistente."""


class LimiteExcedido(Exception):
    """Tentativas demais na janela: o login fica bloqueado até a janela passar."""


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def assinar(token: str, segredo: bytes) -> str:
    """Valor do cookie: `token.assinatura`."""
    assinatura = hmac.new(segredo, token.encode(), hashlib.sha256).hexdigest()
    return f"{token}.{assinatura}"


def abrir_assinatura(valor: str, segredo: bytes) -> str | None:
    token, ponto, assinatura = valor.rpartition(".")
    if not ponto:
        return None
    esperada = hmac.new(segredo, token.encode(), hashlib.sha256).hexdigest()
    return token if hmac.compare_digest(esperada, assinatura) else None


def entrar(
    conexao: Conexao,
    email: str,
    senha_digitada: str,
    agora: datetime,
    max_tentativas: int = MAX_TENTATIVAS,
) -> tuple[str, Sessao]:
    """Valida as credenciais e abre a sessão. Devolve o token (vai assinado no cookie)."""
    email = email.strip()
    desde = _iso(agora - JANELA_TENTATIVAS)
    if sessao.contar_tentativas(conexao, email, desde) >= max_tentativas:
        raise LimiteExcedido(email)
    usuario = acesso.achar_usuario_por_email(conexao, email)
    hash_guardado = usuario.senha_hash if usuario else _HASH_FALSO
    confere = senha.verificar(senha_digitada, hash_guardado)
    if usuario is None or not confere:
        sessao.registrar_tentativa(conexao, email, _iso(agora))
        raise CredenciaisInvalidas(email)
    sessao.limpar_tentativas(conexao, email)
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    sessao.criar(
        conexao, hash_token(token), usuario.id, csrf, _iso(agora), _iso(agora + DURACAO_SESSAO)
    )
    return token, Sessao(usuario.id, None, csrf)


def sessao_do_token(conexao: Conexao, token: str, agora: datetime) -> Sessao | None:
    return sessao.achar(conexao, hash_token(token), _iso(agora))


def escolher_bd(conexao: Conexao, token: str, bd_id: int | None) -> None:
    sessao.definir_bd(conexao, hash_token(token), bd_id)


def sair(conexao: Conexao, token: str) -> None:
    sessao.apagar(conexao, hash_token(token))
