import getpass
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from financeiro import administracao, config, doisfatores, store
from financeiro.i18n import t
from financeiro.store import acesso
from financeiro.web.app import criar_app

_COMANDOS = {
    "semear": "cli.semear",
    "criar-admin": "cli.criar_admin",
    "backup": "cli.backup",
    "desativar-2fa": "cli.desativar_2fa",
}


def _uvicorn(app: object, *, host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


def _opcao(argumentos: Sequence[str], nome: str, padrao: str) -> str:
    return argumentos[argumentos.index(nome) + 1] if nome in argumentos else padrao


def _listar_comandos() -> None:
    print(t("cli.uso"), file=sys.stderr)
    print(f"  servir       {t('cli.servir')}", file=sys.stderr)
    for nome, chave in _COMANDOS.items():
        print(f"  {nome:<12} {t(chave)}", file=sys.stderr)


def _abrir_banco(cfg: config.Config):
    cfg.caminho_bd.parent.mkdir(parents=True, exist_ok=True)
    conexao = store.abrir(cfg.caminho_bd)
    store.migrar(conexao, store.PASTA_MIGRACOES)
    return conexao


def _senha_do_admin(cfg: config.Config) -> str | None:
    """A senha vem do ambiente; sem ela, pergunta no terminal (sem eco). Nunca em arquivo."""
    if cfg.admin_senha:
        return cfg.admin_senha
    if sys.stdin.isatty():  # pragma: no cover - interativo
        return getpass.getpass(t("cli.pede_senha"))
    return None


def _criar_admin(resto: Sequence[str], cfg: config.Config) -> int:
    email, nome, bd = (_opcao(resto, f"--{o}", "") for o in ("email", "nome", "bd"))
    conexao = _abrir_banco(cfg)
    try:
        situacao = administracao.criar_admin(conexao, email, nome, bd, _senha_do_admin(cfg))
    except administracao.AdministracaoInvalida as erro:
        print(str(erro), file=sys.stderr)
        return 2
    finally:
        conexao.close()
    print(t(f"cli.admin_{situacao}", email=email, bd=bd))
    return 0


def _desativar_2fa(resto: Sequence[str], cfg: config.Config) -> int:
    """Para quem perdeu o celular e os códigos de recuperação: só quem tem acesso ao host."""
    email = _opcao(resto, "--email", "")
    conexao = _abrir_banco(cfg)
    try:
        usuario = acesso.achar_usuario_por_email(conexao, email)
        if usuario is None:
            print(t("cli.usuario_inexistente", email=email), file=sys.stderr)
            return 1
        doisfatores.desativar(conexao, usuario.id)
    finally:
        conexao.close()
    print(t("cli.dois_fatores_desativado", email=email))
    return 0


def _semear(cfg: config.Config) -> int:
    conexao = _abrir_banco(cfg)
    try:
        administracao.semear(conexao, _senha_do_admin(cfg))
    except administracao.AdministracaoInvalida as erro:
        print(str(erro), file=sys.stderr)
        return 1 if "não está vazio" in str(erro) else 2
    finally:
        conexao.close()
    print(t("cli.semeado"))
    return 0


def _backup(resto: Sequence[str], cfg: config.Config) -> int:
    destino = Path(_opcao(resto, "--destino", ""))
    if not str(destino) or str(destino) == ".":
        print(t("cli.backup_sem_destino"), file=sys.stderr)
        return 2
    if destino.exists():
        print(t("cli.backup_ja_existe", destino=destino), file=sys.stderr)
        return 1
    conexao = store.abrir(cfg.caminho_bd)
    try:
        store.backup(conexao, destino)
    finally:
        conexao.close()
    print(t("cli.backup_ok", destino=destino))
    return 0


def main(
    argv: Sequence[str],
    *,
    servidor: Callable[..., None] = _uvicorn,
    ambiente: Mapping[str, str] | None = None,
) -> int:
    """Despacha `python -m financeiro <comando>`; devolve o código de saída."""
    if not argv:
        _listar_comandos()
        return 2
    comando, *resto = argv
    cfg = config.carregar(ambiente)
    if comando == "servir":
        porta = int(_opcao(resto, "--porta", "8000"))
        host = _opcao(resto, "--host", "127.0.0.1")
        servidor(criar_app(cfg), host=host, port=porta)
        return 0
    if comando == "criar-admin":
        return _criar_admin(resto, cfg)
    if comando == "desativar-2fa":
        return _desativar_2fa(resto, cfg)
    if comando == "semear":
        return _semear(cfg)
    if comando == "backup":
        return _backup(resto, cfg)
    print(t("cli.comando_desconhecido", comando=comando), file=sys.stderr)
    _listar_comandos()
    return 2
