# AGENTS.md: controle financeiro

Painel de controle financeiro por BD. Antes de mexer, leia o [`CONTEXT.md`](CONTEXT.md) (o glossário: use os termos dele em código, teste e texto) e os ADRs em [`docs/adr/`](docs/adr/). A stack está no [ADR-0001](docs/adr/0001-stack.md).

## Validar antes do PR

```bash
make test   # uv run pytest -q
make lint   # uv run ruff check . && uv run ruff format --check .
```

Ambiente limpo: `env -i HOME="$(mktemp -d)" PATH="$PATH" LANG=C.UTF-8 make test` (e o mesmo com `make lint`). `make format` corrige a formatação.

## Regras de dependência entre módulos

| Regra | Quem pode |
|---|---|
| SQL (`sqlite3`) | só `financeiro/store/` |
| Falar com a rede (`httpx`, `urllib.request`, `socket`) | só módulos de rede próprios (nenhum ainda) |
| Ler variável de ambiente | só `financeiro/config.py` |

Conferidas pelo `make lint` (regra `TID251` do ruff, no `pyproject.toml`). Módulo novo que precise de uma exceção a pede em `per-file-ignores`, no PR que o cria.

## Dados

- Dinheiro é inteiro em centavos, nunca `float` (ADR-0001).
- Toda função de `store/` que lê tabela de dado recebe `bd_id` (ADR-0002).
- Só mês fechado é realizado (ADR-0003).

## Testes

- Sem rede. Banco do teste é SQLite em memória ou arquivo em `tmp_path`.
- `tests/` espelha `financeiro/`, sem `__init__.py`.
- Testa-se por comportamento, em seams combinados antes (skill `oute-aidlc-build-tdd`).

## Dependências

Só as de `pyproject.toml`. Dependência nova pede decisão do Bardi. Sem ORM.

## Git

Entrega por PR; merge só quando o Bardi pedir. Backlog nas issues do repo.
