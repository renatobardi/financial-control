"""Senha de uso único por tempo (TOTP, RFC 6238): SHA-1, 6 dígitos, passo de 30 s.

É o que os aplicativos autenticadores (Google Authenticator, Authy, 1Password…) implementam.
Só biblioteca padrão. O passo já usado é guardado por quem chama, para um código não valer duas
vezes.
"""

import base64
import hashlib
import hmac
import secrets
import struct
from datetime import datetime
from urllib.parse import quote

PASSO_SEGUNDOS = 30
DIGITOS = 6
_TOLERANCIA = 1  # aceita o passo anterior e o seguinte, para o relógio do celular desajustado


def gerar_segredo() -> str:
    """160 bits em base32, sem preenchimento: o que o aplicativo pede para digitar."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def passo_de(agora: datetime) -> int:
    return int(agora.timestamp()) // PASSO_SEGUNDOS


def codigo(segredo: str, passo: int) -> str:
    chave = base64.b32decode(segredo + "=" * (-len(segredo) % 8), casefold=True)
    resumo = hmac.new(chave, struct.pack(">Q", passo), hashlib.sha1).digest()
    posicao = resumo[-1] & 0x0F
    numero = struct.unpack(">I", resumo[posicao : posicao + 4])[0] & 0x7FFFFFFF
    return str(numero % 10**DIGITOS).zfill(DIGITOS)


def verificar(segredo: str, digitado: str, agora: datetime, ultimo_passo: int) -> int | None:
    """O passo em que o código vale (maior que `ultimo_passo`), ou None."""
    limpo = "".join(digitado.split())
    if len(limpo) != DIGITOS or not limpo.isdigit():
        return None
    atual = passo_de(agora)
    for passo in range(atual - _TOLERANCIA, atual + _TOLERANCIA + 1):
        if passo > ultimo_passo and hmac.compare_digest(codigo(segredo, passo), limpo):
            return passo
    return None


def uri(email: str, segredo: str, emissor: str = "Controle financeiro") -> str:
    rotulo = quote(f"{emissor}:{email}", safe="")
    return f"otpauth://totp/{rotulo}?secret={segredo}&issuer={quote(emissor, safe='')}"
