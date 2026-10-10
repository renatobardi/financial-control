from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from financeiro import store
from financeiro.config import Config


def criar_app(cfg: Config) -> FastAPI:
    """Monta a app: abre o banco, migra e serve `/healthz`."""

    @asynccontextmanager
    async def ciclo(app: FastAPI) -> AsyncIterator[None]:
        cfg.caminho_bd.parent.mkdir(parents=True, exist_ok=True)
        conexao = store.abrir(cfg.caminho_bd)
        store.migrar(conexao, store.PASTA_MIGRACOES)
        conexao.close()
        yield

    app = FastAPI(lifespan=ciclo)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        conexao = store.abrir(cfg.caminho_bd)
        try:
            return {"commit": cfg.commit, "esquema": store.versao_atual(conexao)}
        finally:
            conexao.close()

    return app
