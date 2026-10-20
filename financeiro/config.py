"""Única leitura de variável de ambiente do app (AGENTS.md)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

# Só para desenvolvimento local (o `db` do perfil `dev` do compose: `make db`).
# Em produção vem do .env.
URL_BD_PADRAO = "postgresql://postgres:teste@127.0.0.1:55439/postgres"


@dataclass(frozen=True)
class Config:
    # URL do Postgres (oute-supabase-db). Contém a senha da role do app: nunca no repr nem em log.
    url_bd: str = field(repr=False)
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
        url_bd=ambiente.get("FINANCEIRO_DATABASE_URL", URL_BD_PADRAO),
        commit=ambiente.get("FINANCEIRO_COMMIT", "desconhecido"),
        segredo=segredo.encode() if segredo else None,
        cookie_seguro=ambiente.get("FINANCEIRO_COOKIE_SEGURO", "1") != "0",
        max_tentativas=int(ambiente.get("FINANCEIRO_MAX_TENTATIVAS", "5")),
        admin_senha=ambiente.get("FINANCEIRO_ADMIN_SENHA") or None,
    )
