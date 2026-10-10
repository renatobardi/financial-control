"""Única leitura de variável de ambiente do app (AGENTS.md)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    caminho_bd: Path
    commit: str
    # Segredo do cookie de sessão. Sem ele, o app gera um por processo (sessões não
    # sobrevivem a reinício).
    segredo: bytes | None = None
    # Cookie com `Secure`: o app roda atrás de TLS (ADR-0001). Só se desliga em dev local.
    cookie_seguro: bool = True
    max_tentativas: int = 5
    # Senha do primeiro Admin, só para `criar-admin` e `semear`. Nunca em arquivo nem no repr.
    admin_senha: str | None = field(default=None, repr=False)


def carregar(ambiente: Mapping[str, str] | None = None) -> Config:
    """Lê a configuração do ambiente (ou do mapa passado, nos testes)."""
    ambiente = os.environ if ambiente is None else ambiente
    segredo = ambiente.get("FINANCEIRO_SEGREDO")
    return Config(
        caminho_bd=Path(ambiente.get("FINANCEIRO_BD", "dados/financeiro.db")),
        commit=ambiente.get("FINANCEIRO_COMMIT", "desconhecido"),
        segredo=segredo.encode() if segredo else None,
        cookie_seguro=ambiente.get("FINANCEIRO_COOKIE_SEGURO", "1") != "0",
        max_tentativas=int(ambiente.get("FINANCEIRO_MAX_TENTATIVAS", "5")),
        admin_senha=ambiente.get("FINANCEIRO_ADMIN_SENHA") or None,
    )
