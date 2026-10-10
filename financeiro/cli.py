import sys
from collections.abc import Callable, Sequence

from financeiro import config
from financeiro.i18n import t
from financeiro.web.app import criar_app

_PLANEJADOS = {"semear": "cli.semear", "criar-admin": "cli.criar_admin"}


def _uvicorn(app: object, *, host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


def _opcao(argumentos: Sequence[str], nome: str, padrao: str) -> str:
    return argumentos[argumentos.index(nome) + 1] if nome in argumentos else padrao


def _listar_comandos() -> None:
    print(t("cli.uso"), file=sys.stderr)
    print(f"  servir       {t('cli.servir')}", file=sys.stderr)
    for nome, chave in _PLANEJADOS.items():
        print(f"  {nome:<12} {t(chave)}", file=sys.stderr)


def main(argv: Sequence[str], *, servidor: Callable[..., None] = _uvicorn) -> int:
    """Despacha `python -m financeiro <comando>`; devolve o código de saída."""
    if not argv:
        _listar_comandos()
        return 2
    comando, *resto = argv
    if comando == "servir":
        porta = int(_opcao(resto, "--porta", "8000"))
        host = _opcao(resto, "--host", "127.0.0.1")
        servidor(criar_app(config.carregar()), host=host, port=porta)
        return 0
    if comando in _PLANEJADOS:
        print(t("cli.nao_implementado", comando=comando), file=sys.stderr)
        return 2
    print(t("cli.comando_desconhecido", comando=comando), file=sys.stderr)
    _listar_comandos()
    return 2
