# AGENTS.md: controle financeiro

Painel de controle financeiro por BD. Antes de mexer, leia o [`CONTEXT.md`](CONTEXT.md) (o glossário: use os termos dele em código, teste e texto) e os ADRs em [`docs/adr/`](docs/adr/). A stack está no [ADR-0001](docs/adr/0001-stack.md).

## Validar antes do PR

```bash
make db     # Postgres de teste (uma vez)
make test   # uv run pytest -q
make lint   # uv run ruff check . && uv run ruff format --check .
```

Ambiente limpo: `env -i HOME="$(mktemp -d)" PATH="$PATH" LANG=C.UTF-8 make test` (e o mesmo com `make lint`). `make format` corrige a formatação.

## Regras de dependência entre módulos

| Regra | Quem pode |
|---|---|
| SQL (`psycopg`) | só `financeiro/store/` |
| Falar com a rede (`httpx`, `urllib.request`, `socket`) | só módulos de rede próprios (nenhum ainda) |
| Ler variável de ambiente | só `financeiro/config.py` |

Conferidas pelo `make lint` (regra `TID251` do ruff, no `pyproject.toml`). Módulo novo que precise de uma exceção a pede em `per-file-ignores`, no PR que o cria.

## Dados

- Dinheiro é inteiro em centavos, nunca `float` (ADR-0001).
- Toda função de `store/` que lê tabela de dado recebe `bd_id` (ADR-0002).
- Só mês fechado é realizado (ADR-0003).

## Testes

- Sem rede externa. O banco do teste é um Postgres 17 local (`make db`, porta 55439; na CI, um service), cada teste num schema descartável (`tests/banco.py`, fixture `conexao`). Violação de restrição aborta a transação: use `recusa_do_banco(conexao)`.
- `tests/` espelha `financeiro/`, sem `__init__.py`.
- Testa-se por comportamento, em seams combinados antes (skill `oute-aidlc-build-tdd`).

## Dependências

Só as de `pyproject.toml` (inclui `psycopg[binary]` e `psycopg_pool`, aprovadas no ADR-0004). Dependência nova pede decisão do Bardi. Sem ORM.

## Git

Entrega por PR; merge só quando o Bardi pedir. Backlog nas issues do repo.

## Configuração

Só `financeiro/config.py` lê o ambiente: `FINANCEIRO_DATABASE_URL` (URL do Postgres; padrão: o `db` de desenvolvimento) e `FINANCEIRO_COMMIT` (padrão `desconhecido`). Variável nova entra lá e aqui. O app sobe sem nenhuma.

## Front

HTML no servidor (Jinja2 + HTMX), Tailwind 4 standalone compilado no `Dockerfile` a partir de `financeiro/web/styles/input.css` (tokens do Kubo). `static/app.css` não vai para o git. Texto visível vem só do catálogo `financeiro/i18n/pt-BR.toml`: um teste falha se um template tiver texto solto. Bloco pesado de tela usa a macro `bloco_lazy(url)`.

## Mapa do código

| Onde | O quê |
|---|---|
| `financeiro/store/` | Todo o SQL. Migrações em `store/migracoes/NNNN_*.sql`. Função de tabela de dado recebe `bd_id` (a guarda confere) |
| `financeiro/{autenticacao,senha,membros}.py` | Login, sessão, scrypt, papéis e pedidos de acesso |
| `financeiro/{organizacao,equipe,compras,orcamento,calendario}.py` | Regras dos cadastros, pessoas, compras (OC/OS), PDD e calendário |
| `financeiro/{consumo,fechamento,realizado,forecast,cenarios,visao_geral}.py` | Consumo do mês, fechamento (congela o realizado), realizado por dimensão, forecast e cenários |
| `financeiro/onboarding.py` | Passos de configuração de um BD (estado derivado dos dados, bloqueio pelas dependências, dispensa e abertura única); SQL em `store/onboarding.py` |
| `financeiro/cargas/` | CSV, seis layouts, validação, diário e desfazer |
| `financeiro/{treemap,graficos}.py` | Layout do treemap e gráficos em SVG (sem JavaScript) |
| `financeiro/web/` | Rotas FastAPI, templates Jinja e estáticos. Texto visível só do catálogo `i18n/pt-BR.toml` |
| `financeiro/cli.py` | `servir`, `criar-admin`, `semear` e `desativar-2fa` |

Regras que os testes conferem: dinheiro em centavos inteiros; `bd_id` obrigatório; mês fechado é
realizado e fica congelado (`realizado_linha`); texto de template só do catálogo; gap =
orçamento − total do ano, com o mesmo sinal em todas as telas.
