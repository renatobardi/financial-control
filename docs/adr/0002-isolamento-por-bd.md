# Os BDs ficam num só arquivo SQLite, isolados por `bd_id`

- **Estado:** aceito
- **Data:** 2026-10-10

Todas as tabelas de dado têm `bd_id`, e toda função de `store/` recebe o `bd_id` como parâmetro obrigatório. Um teste falha se alguma consulta de tabela de dado não filtrar por ele. Usuários e papéis ficam no mesmo banco.

## Alternativas

- **Um arquivo SQLite por BD** isolaria fisicamente e facilitaria restaurar um BD, mas multiplica migrações e backups por N arquivos e liga a abertura da conexão à sessão. Com 3 BDs e no máximo 6 usuários, o custo não se paga.

## Consequências

- Uma falha de filtro vaza dado entre BDs: por isso o `bd_id` obrigatório na assinatura e o teste que confere.
- Mudar depois para um arquivo por BD exige migrar todos os dados, o que torna esta decisão cara de desfazer.
