# Regras de Negócio — Painel Financeiro (sanitizado)

1. **Contrato obrigatório**: o app rejeita o payload se `meta.versaoContrato !== 3` ou `meta.escopoEvolucao !== 'total'`, exibindo erro de incompatibilidade.
2. **Evolução mensal por parcelas**: some `realizado` e `forecast` separadamente — nunca pelo rótulo `tipo`. Mês `forecast` com `realizado > 0` é "misto" (ex.: valor já empenhado via ordem de compra) e deve ser sinalizado visualmente.
3. **Gap/saldo com sinal único**: `gap = orcamento - totalAno`; positivo = saldo, negativo = estouro. `saldoDiverge` indica que CAPEX e OPEX divergem do saldo total (um estourou, outro sobrou).
4. **INFRA declarada à parte**: realizado sem tipo de despesa é mostrado como parcela própria, nunca alocado artificialmente em CAPEX ou OPEX.
5. **Tarifa é faixa**: exibir `tarifaMin–tarifaMax`; nunca média.
6. **Base + markup = realizado**: a abertura por fornecedor/OC não acrescenta custo; exibir nota explicativa ("não é confirmação de liquidação").
7. **pessoasPorMes não soma**: no bloco de horas/alocações, o total anual de pessoas não é a soma da coluna.
8. **Horas acima do previsto é piso**: estimativa derivada de `valor/tarifa` no período fechado; exibir ressalva.
9. **Descartadas reconciliam**: quando tabelas detalhadas não fecham com o total (linhas sem tipo/mês, meses fora do fechamento), exibir nota com `descartadas.consumoForaDoFechamento`.
10. **Contagem única de headcount**: `total` inclui vagas em aberto — sinalizar na UI.
11. **Dado pessoal restringido**: a lista de horas acima do previsto contém identificadores de pessoa — esconder por padrão ou proteger por permissão.
12. **Meses realizado vs forecast**: definidos por `meta.mesesRealizado`/`meta.mesesForecast` + `meta.regraFechamento`; o rótulo e o período fechado vêm do payload, não de data local do cliente.
