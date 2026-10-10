# Deploy no oute-server

Roteiro do deploy da #10. Todo passo no host vai pelo canal de aprovação (`oute-propose`, aprovado
por você com `oute approve`); nada aqui roda por fora dele.

## O que vai ao ar

Um serviço (`app`) e um volume (`dados`), pelo `docker-compose.yml`. O SQLite fica em
`/data/financeiro.db` no volume. TLS fica no nginx do host; o app escuta em `127.0.0.1:8000`.

## Antes do deploy (no repositório)

1. A imagem constrói na CI (job `imagem`) e `GET /healthz` devolve o commit e a versão do esquema.
2. Release: o commit da `main` que vai ao ar.

## Passos no host (cada um é uma proposta no canal)

1. **LXC**: criar o contêiner, instalar Docker e `docker compose`, copiar o repositório na versão
   da release. `FINANCEIRO_COMMIT=<sha>` no `docker compose build`.
2. **Segredo**: criar o `.env` (root, 0600) com `FINANCEIRO_SEGREDO`. Gerar com
   `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Nunca no git nem na proposta.
3. **Subir**: `docker compose up -d --build`.
4. **nginx e TLS** (host): `proxy_pass http://127.0.0.1:8000;`, certificado pelo `certbot`, acesso
   pela tailnet e pela internet. Conferir com `nginx -t` antes do reload.
5. **Primeiro Admin**, sem senha em arquivo (o comando pergunta no terminal, sem eco):

   ```bash
   docker compose exec app python -m financeiro criar-admin \
     --email <e-mail> --nome "<nome>" --bd "<nome do BD>"
   ```

   Repetir não muda a senha nem duplica.
6. **Backup**: o SQLite é copiado com `.backup` (consistente com o app escrevendo), não copiando o
   arquivo:

   ```bash
   docker compose exec app python -m financeiro backup --destino /data/backup/AAAA-MM-DD.db
   ```

   O volume `dados` entra no backup que o host já faz. O comando não sobrescreve arquivo existente.

## Verificação pós-deploy

- `curl -fsS https://<host>/healthz` devolve `{"commit": "<sha da release>", "esquema": <n>}`.
- Rota sem sessão pela internet devolve 401 (ou leva ao login), e nenhuma devolve dado.
- Restaurar um backup num arquivo de teste e conferir:
  `sqlite3 teste.db "PRAGMA integrity_check"` devolve `ok`.
- O banco de produção não tem usuário nem dado da semente: `semear` recusa banco com usuário e
  **não** deve ser rodado em produção.

## Reverter

O compose guarda o volume. Para voltar uma versão: `git checkout <sha anterior>` e
`docker compose up -d --build`. Migrações só avançam: se a versão nova aplicou uma migração, o
`.antes-da-NNNN` ao lado do banco é a cópia de antes dela.
