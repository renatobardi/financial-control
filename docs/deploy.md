# Deploy no oute-server

Roteiro do deploy da #10. Segue as convenções do host: o LXC e o proxy nascem no repositório `lab`
(issue, inventário, script, PR); o deploy de uma versão já mergeada e os ajustes pontuais vão pelo
canal de aprovação (`oute-propose`, aprovado pelo Bardi com `oute approve`). Nada aqui roda por fora
dele, e nenhum segredo entra em arquivo, comando, issue ou PR.

## O que vai ao ar

Um serviço (`app`) e um volume (`dados`), pelo `docker-compose.yml`, dentro do LXC
`financial-control-prd`. O SQLite fica em `/data/financeiro.db`, no volume. O compose publica a
porta em `FINANCEIRO_PUBLICAR` (o endereço e a porta que o `lab` aloca), nunca em `0.0.0.0`.
Primeiro só na tailnet; internet e TLS pelo nginx do host entram numa segunda etapa.

## Segredos: vault

| Segredo | Onde fica | Como chega ao app |
|---|---|---|
| `FINANCEIRO_SEGREDO` (assina o cookie de sessão) | Vaultwarden, item `financial-control-prd FINANCEIRO_SEGREDO` (o Bardi cria) | `/opt/app/.env` no LXC, root, `0600`, entregue por stdin pelo auxiliar interativo do `lab` |
| Senha do primeiro Admin | Não fica em arquivo: o `criar-admin` pergunta no terminal, sem eco | Só no hash scrypt do banco |
| Chave de deploy do repositório (privado) | Nasce dentro do LXC; só a metade pública sai | Registrada pelo Bardi como chave **só de leitura** em Settings → Deploy keys |

Sem `FINANCEIRO_SEGREDO` o app sobe e as sessões caem a cada reinício.

## Passos

1. **Issue e PR no `lab`** (instalação do LXC, inventário e `PORTS.md`). Antes do merge, o auxiliar de
   instalação roda em `--check` pelo canal (só lê). Depois do merge e do `oute approve`, instala o
   LXC, clona este repositório em `/opt/app` com a chave de deploy e grava `/opt/app/.env` só com
   `FINANCEIRO_PUBLICAR`.
2. **Chave de deploy**: o auxiliar imprime a metade pública; o Bardi a registra no GitHub como chave
   só de leitura e roda de novo.
3. **Segredo**: o Bardi cria o item no Vaultwarden e roda, no terminal do host, o auxiliar de segredos
   do `lab` (`--check` e depois `--apply`). Ele não roda pelo canal.
4. **Deploy da versão**, pelo canal: `scripts/deploy.sh <sha>` (entra no LXC, confere que o commit
   está na `main`, faz o checkout, sobe o compose e espera o `/healthz` devolver esse commit).
5. **Primeiro Admin**, sem senha em arquivo (o comando pergunta no terminal):

   ```bash
   lxc exec financial-control-prd --cwd /opt/app -- \
     docker compose exec app python -m financeiro criar-admin \
       --email <e-mail> --nome "<nome>" --bd "<nome do BD>"
   ```

   Repetir não muda a senha nem duplica.
6. **Backup**: o SQLite é copiado com `.backup`, não copiando o arquivo com o app escrevendo:

   ```bash
   docker compose exec app python -m financeiro backup --destino /data/backup/AAAA-MM-DD.db
   ```

   O comando não sobrescreve arquivo existente. A estratégia no inventário do host precisa incluir
   o volume do LXC.
7. **nginx e TLS** (segunda etapa, no `lab`): vhost, certificado do `certbot` e, se for o caso, a
   exposição na internet.

## Verificação pós-deploy

- `GET /healthz` devolve `{"commit": "<sha da release>", "esquema": <n>}`.
- Rota sem sessão devolve 401 (ou leva ao login) e nenhuma devolve dado.
- Restaurar um backup num arquivo de teste e conferir:
  `sqlite3 teste.db "PRAGMA integrity_check"` devolve `ok`.
- O banco de produção não tem usuário nem dado da semente: `semear` recusa banco com usuário e
  **não** roda em produção.

## Reverter

O volume fica. Para voltar uma versão, rode `scripts/deploy.sh <sha anterior>` pelo canal. Migrações
só avançam: se a versão nova aplicou uma migração, o `.antes-da-NNNN` ao lado do banco é a cópia de
antes dela.
