# Stack: Python, FastAPI, HTML no servidor com HTMX, SQLite e Tailwind standalone

- **Estado:** aceito
- **Data:** 2026-10-10

O app usa o mesmo stack do [frentes-engenharia](https://github.com/renatobardi/frentes-engenharia/blob/main/docs/adr/0001-stack.md): Python 3.12 com `uv`, FastAPI com um worker, Jinja2 com HTMX, SQLite da biblioteca padrão em modo WAL e sem ORM, com todo o SQL em `store/`. O volume é pequeno (no máximo 6 usuários, cerca de 200 pessoas por mês, 30 temas, 20 demandas, 10 iniciativas e 20 cenários), então um arquivo SQLite e um processo bastam.

## Desvios do frentes

- **Tailwind 4 com binário standalone, sem Node**, copiado do Kubo, no lugar de "um CSS à mão". Motivo: o Kubo DS já está escrito assim (`kubo/api/styles/input.css`), e os componentes do protótipo viram macros Jinja com as mesmas classes.
- **Login local, migrações e backup consistente.** O frentes não tem login e regrava o snapshot. Aqui o dado é digitado e não se regenera.
- **Lazy loading em toda tela:** a casca vem primeiro e os blocos pesados chegam por fragmento HTMX.

## Consequências

- Dinheiro é inteiro em centavos, nunca `float`.
- Backup do SQLite é feito com `sqlite3 .backup`, não copiando o arquivo com o app escrevendo.
- Trocar o SQLite por outro banco só é barato porque o SQL fica isolado em `store/`.
- O app roda num LXC do oute-server, acessível pela tailnet e pela internet, com tudo atrás de login.
