import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from financeiro import store
from financeiro.config import Config
from financeiro.web import (
    rotas_acesso,
    rotas_cadastros,
    rotas_cargas,
    rotas_compras,
    rotas_configuracoes,
    rotas_fechamento,
    rotas_forecast,
    rotas_orcamento,
    rotas_pessoas,
    rotas_realizado,
    rotas_visao,
)


def _agora() -> datetime:
    return datetime.now(UTC)


def criar_app(cfg: Config, agora: Callable[[], datetime] = _agora) -> FastAPI:
    """Monta a app: abre o banco, migra e serve `/healthz` e as rotas de acesso.

    `agora` é o relógio; os testes passam um fixo.
    """

    @asynccontextmanager
    async def ciclo(app: FastAPI) -> AsyncIterator[None]:
        cfg.caminho_bd.parent.mkdir(parents=True, exist_ok=True)
        conexao = store.abrir(cfg.caminho_bd)
        store.migrar(conexao, store.PASTA_MIGRACOES)
        conexao.close()
        yield

    app = FastAPI(lifespan=ciclo)
    app.state.cfg = cfg
    app.state.agora = agora
    app.state.segredo = cfg.segredo or secrets.token_bytes(32)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    app.include_router(rotas_acesso.roteador)
    app.include_router(rotas_configuracoes.roteador)
    app.include_router(rotas_cadastros.roteador)
    app.include_router(rotas_cargas.roteador)
    app.include_router(rotas_fechamento.roteador)
    app.include_router(rotas_orcamento.roteador)
    app.include_router(rotas_realizado.roteador)
    app.include_router(rotas_pessoas.roteador)
    app.include_router(rotas_compras.roteador)
    app.include_router(rotas_forecast.roteador)
    app.include_router(rotas_visao.roteador)

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        conexao = store.abrir(cfg.caminho_bd)
        try:
            return {"commit": cfg.commit, "esquema": store.versao_atual(conexao)}
        finally:
            conexao.close()

    return app
