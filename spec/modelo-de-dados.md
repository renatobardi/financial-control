# Modelo de Dados — Painel Financeiro (sanitizado)

## Visão geral

O app consome **um único documento JSON** (documental, desnormalizado). A raiz é `PainelFinanceiro` com ~18 blocos. Não há banco relacional obrigatório — se persistir, um documento por unidade organizacional/ano basta.

## Entidades principais

- **Meta** — metadados e controle de compatibilidade do contrato
- **BlocoOrcamento** — quíntuplo `orcamento / realizado / forecast / totalAno / gap` reutilizado em várias seções
- **OrcamentoTotal** — BlocoOrcamento + decomposição `capacity* / pf*` (realizado e forecast)
- **ProjetoFechado** — BlocoOrcamento + split `capex`/`opex` (`{orcamento, realizado, saldo}`) + `saldoDiverge` + `detalhamento` opcional por fornecedor → ordens de compra (`base`, `markup`, `realizado`, `capex`, `opex`)
- **CapexOpex** — lados `capex`/`opex` (`orcamento`, `orcamentoCapacity`, `orcamentoPf`, `consumo`, `consumoPessoas`, `consumoCompras`, `saldo`) + `infra` (parcela sem tipo)
- **Headcount / HeadcountMes** — contagens atuais e histórico (`func`/`terc` × ativos/vagas)
- **MesValor** — mês decomposto `realizado + forecast = valor`, `tipo`, `misto`
- **Rtb** — categorias × `porMes`, `totalPorMes`, `total`
- **Gravity** — `consumoPorMes`, `pessoasPorMes` (não somável), `horasPorMes`, totais
- **Consultoria / NivelFuncionario** — `tarifaMin/tarifaMax` (faixa), `realizado`, `forecast`, `totalAno`
- **VagaAberta** — `tipo`, `posicao`, `nivelEmpresa`, `custoHora`, `forecastAno`
- **HorasAcimaPrevisto** — `matricula`, `nome`, `tipo`, `empresa`, `tarifa`, `horas`, `previsto`, `excedente` (**dado pessoal — tratar como confidencial**)
- **TemaCtb / TriboSquad / Funcao** — linhas analíticas `valor/horas/pessoas` ou `qtd + realizado/forecast/totalAno`
- **Iniciativas** — listas `capex`/`opex` de iniciativas (`porMes`, `total`, `pct`, `demandas?`), `totais`, `descartadas`

## Relacionamentos

- Raiz → 1:1 com Meta, blocos orçamentários e análises; 1:N com todas as listas
- ProjetoFechado → 1:N Fornecedor → 1:N OrdemCompra
- Iniciativas → 1:N Iniciativa → 0..N Demanda

## Invariantes (o gerador/validador deve garantir)

1. `meta.versaoContrato === 3` e `meta.escopoEvolucao === 'total'`
2. `evolucaoMensal[].valor = realizado + forecast`; soma dos valores = totalAno da evolução
3. `capexOpex.capex.consumo + capexOpex.opex.consumo + capexOpex.infra = orcamentoTotal.realizado`
4. `orcamentoTotal.realizado = capacityRealizado + pfRealizado` (idem forecast)
5. `fornecedor.base + markup = fornecedor.realizado` (por OC também)
6. `totalAno ≈ realizado + forecast` em todo BlocoOrcamento; `gap = orcamento - totalAno`
7. `pessoasPorMes` do Gravity **não** é somável no ano
8. Mês com `tipo='forecast'` pode ter `realizado > 0` (misto) — some por parcelas
9. `consultorias/niveis`: `tarifaMin ≤ tarifaMax`; nunca média
10. `iniciativas.descartadas` reconcilia as diferenças entre tabelas e totais

## Classificação sugerida

- `publico`: meses, moeda, versão, nomes de seções
- `interno`: todos os valores agregados, headcount, iniciativas
- `confidencial`: tarifas, custo/hora, valores por fornecedor/OC
- `restrito`: `horasAcimaPrevisto` (matrícula + nome identificam pessoa)
