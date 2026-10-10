# Telas e UX — Painel Financeiro (sanitizado)

## Estrutura

Uma página única, longa, organizada em seções recolhíveis/expansíveis (`<app-secao>`-like). Navegação lateral fixa com âncoras e KPIs principais no topo. Todo o texto via i18n (pt-BR, en-US, es).

## Seções (ordem exibida)

1. **Header/nav** — eyebrow "Operação", título da unidade, âncoras por grupo (Orçamento / Iniciativas / Pessoas / Evolução / Análises / Detalhamento)
2. **Orçamento Total** — 5 cards (Orçamento, Realizado, Forecast, Total Ano, Gap) + barra de progresso orçado×consumido
3. **Capacity (Pessoas)** — mesmos 5 cards restritos a pessoas+INFRA
4. **Projeto Fechado** — bloco PF com split CAPEX/OPEX, flag de divergência de saldo, e detalhamento expansível por fornecedor → OCs (base, markup, realizado, capex/opex, escopo completo da OC)
5. **CAPEX vs OPEX** — dois lados com orçamento/consumo/saldo e split capacity×PF; nota da parcela INFRA
6. **Divisão do consumo** — gráfico proporcional pessoas × compras
7. **Iniciativas CAPEX / OPEX** — tabelas por mês com % de participação; iniciativas expansíveis mostrando demandas; nota de reconciliação (descartadas)
8. **Headcount** — cards func/terc × ativos/vagas + total (inclui vagas)
9. **Histórico de Headcount** — tabela/gráfico mensal
10. **Evolução Mensal** — 12 barras/linhas empilhadas realizado+forecast; meses mistos destacados
11. **Análise RTB** — categorias × meses
12. **Análise Gravity** — consumo, pessoas e horas por mês (nota: pessoas não somável)
13. **Top 10 Temas CTB** — ranking por consumo com horas/pessoas/custo médio
14. **Gastos por Consultoria** — qtd pessoas, faixa tarifa, realizado/forecast/total (colapsável, fechada por padrão)
15. **Gastos por Nível** — idem por nível Nx (colapsável)
16. **Vagas em Aberto** — tipo, posição, nível/empresa, custo/hora, forecast (colapsável)
17. **Horas Acima do Previsto** — pessoas, horas vs previsto, excedente (colapsável; dado sensível)
18. **Tribo/Squad e Funções** — análises do censo com reconciliação contra o total do ano (resíduo exibido)

## Estados

- Loading: esqueleto/spinner
- Erro de carga: mensagem genérica
- Erro de contrato: mensagem específica de incompatibilidade de versão/escopo
- Vazio: cada lista tem mensagem própria (ex.: "nenhuma OC com realizado neste recorte")

## Componentes visuais

- Cards KPI com valor monetário formatado (BRL, abreviação MM/M quando aplicável)
- Barras de progresso para % consumido
- Tabelas com linhas expansíveis (fornecedor→OC, iniciativa→demanda)
- Badge/estilo diferenciado para valores negativos (gap) e meses mistos
- Notas de rodapé explicativas por seção (critérios de cálculo)
