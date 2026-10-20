from decimal import Decimal

import psycopg
from psycopg import adapt
from psycopg_pool import ConnectionPool

# Pool do app: 6 usuários no máximo (ADR-0001); uma conexão emprestada por requisição.
TAMANHO_MIN = 1
TAMANHO_MAX = 5


class _InteiroSeExato(adapt.Loader):
    """`SUM` de inteiros volta como `numeric` (Decimal); o app só usa inteiros (centavos, horas)."""

    def load(self, data):
        valor = Decimal(bytes(data).decode())
        return int(valor) if valor == valor.to_integral_value() else valor


def _opcoes(schema: str | None) -> str | None:
    return f"-c search_path={schema}" if schema else None


def _preparar(conexao: psycopg.Connection) -> None:
    conexao.adapters.register_loader("numeric", _InteiroSeExato)


def abrir(url: str, schema: str | None = None) -> psycopg.Connection:
    """Abre uma conexão (CLI, migração, testes). `schema` fixa o `search_path`; em produção a
    role do app já tem o schema dela como `search_path`."""
    conexao = psycopg.connect(url, options=_opcoes(schema))
    _preparar(conexao)
    return conexao


def criar_pool(url: str, schema: str | None = None) -> ConnectionPool:
    """Pool do app, fechado até `pool.open()` (o ciclo de vida da app abre e fecha)."""
    return ConnectionPool(
        url,
        min_size=TAMANHO_MIN,
        max_size=TAMANHO_MAX,
        kwargs={"options": _opcoes(schema)},
        configure=_preparar,
        open=False,
    )
