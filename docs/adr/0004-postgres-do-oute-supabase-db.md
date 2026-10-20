# Postgres do oute-supabase-db no lugar do SQLite

- **Estado:** aceito (substitui o ADR-0001 no ponto do banco)
- **Data:** 2026-10-19

O banco do app passa de um arquivo SQLite para um schema (`financial_control_prd`) no Postgres do
`oute-supabase-db`, a peça compartilhada de Postgres dos projetos Oute: um schema por projeto no
database `postgres`, uma role dona do schema (`app_financial_control_prd`) e uma de leitura, backup
pelo restic do `lab` (dump com donos e grants, restore testado). O restante do ADR-0001 vale
(Python, FastAPI, Jinja/HTMX, Tailwind standalone, sem ORM, dinheiro em centavos, todo o SQL em
`store/`). O ADR-0002 (isolamento por `bd_id`) não muda.

## O que muda no código

- **Driver:** `psycopg` 3 (`psycopg[binary]`, sem libpq no Dockerfile) e `psycopg_pool`. Sem ORM.
- **Conexão:** um `ConnectionPool` (1 a 5; no máximo 6 usuários) aberto no startup; uma conexão
  emprestada por requisição. Direto na porta 5433 do `oute-supabase-db`, sem o pooler do Supabase.
- **Configuração:** `FINANCEIRO_DATABASE_URL` (só em `config.py`), com a senha da role no `.env` do
  LXC, entregue do cofre. `FINANCEIRO_BD` deixa de existir.
- **Tipos:** todo `INTEGER` do esquema virou `BIGINT`: o `INTEGER` do Postgres tem 32 bits (≈ R$ 21,4
  mi em centavos) e o orçamento do PDD em milhões estoura. A soma de inteiros volta como `int`.
- **E-mail:** sem `COLLATE NOCASE` (nem `citext`, que a role do app não instala): índice único e buscas
  em `lower(email)`.
- **Vigência:** os dois triggers de sobreposição viraram funções plpgsql que levantam o SQLSTATE
  `23P01`, classe 23, então o psycopg levanta `IntegrityError` como o `RAISE(ABORT)` do SQLite.
- **Sessão:** ganhou `id` próprio (era o `rowid`).
- **Migrações:** as 13 continuam, em dialeto Postgres, aplicadas com `pg_advisory_lock`; DDL é
  transacional, então uma migração com defeito não deixa nada pela metade.

## Consequências

- **Uma violação de restrição aborta a transação** (no SQLite só o comando falhava). Quem trata
  `ErroDeIntegridade` e segue usando a conexão faz `rollback()` antes: está nos pontos que já
  tratavam (`web/cadastros._guardar`, `cenarios`, `equipe`, `organizacao`, `store.pessoas`).
- **Testes** rodam contra um Postgres 17 de verdade (`make db`, porta 55439; na CI, um service), cada
  teste num schema descartável. A regra "sem rede, SQLite em memória" acabou; o resto do `AGENTS.md`
  vale. A suíte leva ~2 min (era 20 s): o custo de migrar o esquema em cada teste.
- **Backup** deixa de ser do app: o `financeiro backup`, o `store/backup.py` e a cópia
  `.antes-da-NNNN` saíram. O dump é do `lab` (schema inteiro, com donos e grants).
- **Ordenação de texto** passa a seguir o collation do Postgres, não a ordem binária do SQLite.
- **Sem caminho de volta** ao SQLite depois do cutover: correções vão para a frente.
