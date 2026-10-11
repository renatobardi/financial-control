"""Verificação em duas etapas: ativar, conferir no login e desativar.

Sem SQL: usa `store.segundo_fator`.
"""

import hashlib
import secrets
from datetime import datetime

from financeiro import totp
from financeiro.store import Conexao, segundo_fator

QUANTIDADE_CODIGOS = 8


class CodigoInvalido(Exception):
    """O código digitado não confere (ou já foi usado)."""


def _hash(codigo: str) -> str:
    return hashlib.sha256("".join(codigo.split()).lower().encode()).hexdigest()


def _novo_codigo() -> str:
    cru = secrets.token_hex(5)
    return f"{cru[:5]}-{cru[5:]}"


def ativo(conexao: Conexao, usuario_id: int) -> bool:
    atual = segundo_fator.obter(conexao, usuario_id)
    return bool(atual and atual.ativo)


def iniciar_ativacao(conexao: Conexao, usuario_id: int) -> str:
    """Um segredo novo, ainda sem valer: só passa a valer com um código certo."""
    segredo = totp.gerar_segredo()
    segundo_fator.iniciar(conexao, usuario_id, segredo)
    return segredo


def confirmar_ativacao(
    conexao: Conexao, usuario_id: int, digitado: str, agora: datetime
) -> list[str]:
    """Liga o 2FA e devolve os códigos de recuperação, que só aparecem agora."""
    pendente = segundo_fator.obter(conexao, usuario_id)
    if pendente is None or pendente.ativo:
        raise CodigoInvalido
    passo = totp.verificar(pendente.segredo, digitado, agora, pendente.ultimo_passo)
    if passo is None:
        raise CodigoInvalido
    codigos = [_novo_codigo() for _ in range(QUANTIDADE_CODIGOS)]
    segundo_fator.ativar(conexao, usuario_id, passo, [_hash(c) for c in codigos])
    return codigos


def conferir_login(conexao: Conexao, usuario_id: int, digitado: str, agora: datetime) -> bool:
    """Código do aplicativo (uma vez por passo) ou código de recuperação (uma vez só)."""
    atual = segundo_fator.obter(conexao, usuario_id)
    if atual is None or not atual.ativo:
        return False
    passo = totp.verificar(atual.segredo, digitado, agora, atual.ultimo_passo)
    if passo is not None:
        segundo_fator.registrar_passo(conexao, usuario_id, passo)
        return True
    return segundo_fator.consumir_codigo(conexao, usuario_id, _hash(digitado))


def desativar(conexao: Conexao, usuario_id: int) -> None:
    segundo_fator.desativar(conexao, usuario_id)


def codigos_restantes(conexao: Conexao, usuario_id: int) -> int:
    return segundo_fator.codigos_restantes(conexao, usuario_id)
