# Controle financeiro

Protótipo navegável **v1.0** do painel de controle financeiro (PDD, realizado, forecast, pessoas, compras, cadastros, cargas e fechamento), construído sobre o Kubo Design System.

## Estrutura

- `prototipo/App.dc.html`: protótipo v1.0 (canvas Claude Design, arquivo único e interativo)
- `prototipo/Main.dc.html`: shell de referência do Kubo DS
- `prototipo/canvas.json`: índice do canvas (boards e design system)
- `spec/`: spec de origem (modelo de dados, regras de negócio, telas e UX, arquitetura)

## Acesso ao protótipo (simulado)

| Usuário | Senha | Papel |
|---|---|---|
| renato.bardi@empresa.com | 123456 | Admin (BD o1), Leitor (bd2) |
| analista@empresa.com | 123456 | Editor (BD o1) |

O tenant é a BD.

## Modelo de dados v1 (resumo)

- **Organização:** BD → Tribo → Squad, com vigência e gestor.
- **Cadastros:** pessoa, empresa (própria ou consultoria), cargo (E6..N12) e tarifa líquida por cargo, todos com vigência.
- **Markup:** tem vigência. Bruto = líquido × (1 + markup).
- **Demanda:** iniciativa → demanda (CAPEX/OPEX) → tema (agrupamento fixo).
- **PDD:** budget bruto por iniciativa × tipo, com revisões trimestrais. O markup fica congelado em cada revisão.
- **Alocação:** horas por pessoa × tema × mês.
- **Compras:** OC/OS vinculada a 1 demanda (prevista/emitida/cancelada).
- **Forecast:** cenários e vagas, apresentados em treemap com escala e elementos.
- **Calendário:** 8 h × dias úteis.
- **Fechamento:** mensal, manual e reversível, com log.
- **Cargas:** CSV com relatório sintético e analítico. Horas extras precisam de aprovação.
