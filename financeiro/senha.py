"""Hash de senha com scrypt da biblioteca padrão. Formato: scrypt$n$r$p$sal$hash (base64)."""

import base64
import hashlib
import hmac
import secrets

_N, _R, _P = 2**14, 8, 1
_TAMANHO = 32


def _b64(dado: bytes) -> str:
    return base64.b64encode(dado).decode("ascii")


def gerar_hash(senha: str) -> str:
    sal = secrets.token_bytes(16)
    derivado = hashlib.scrypt(senha.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=_TAMANHO)
    return f"scrypt${_N}${_R}${_P}${_b64(sal)}${_b64(derivado)}"


def verificar(senha: str, hash_guardado: str | None) -> bool:
    """False para senha errada, hash malformado ou conta sem senha (convite pendente)."""
    if not hash_guardado:
        return False
    try:
        nome, n, r, p, sal, esperado = hash_guardado.split("$")
        if nome != "scrypt":
            return False
        derivado = hashlib.scrypt(
            senha.encode(),
            salt=base64.b64decode(sal),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=_TAMANHO,
        )
        return hmac.compare_digest(_b64(derivado), esperado)
    except ValueError:
        return False
