# Só mês fechado é realizado

- **Estado:** aceito
- **Data:** 2026-10-10

Realizado é o consumo de um mês fechado pelo fechamento. Mês aberto é forecast, mesmo com lançamento nele. Não existe mês "misto": o lançamento em mês aberto só vira realizado quando o mês fecha. Reabrir um mês devolve os lançamentos a forecast.

Isso difere da `spec/regras-de-negocio.md` (regra 2), que somava realizado e forecast no mesmo mês e o marcava como "misto". O Bardi decidiu na entrevista de intent (issue #1) que o mês não terminou, então não é realizado.

## Consequências

- Um mês só fecha se o anterior estiver fechado, e a tentativa fora de ordem é recusada.
- Uma carga de horas ou de compras em mês aberto entra como forecast. Em mês fechado, é rejeitada com `MES_FECHADO`.
- Os totais do ano somam realizado (meses fechados) e forecast (o resto), sem interseção.
