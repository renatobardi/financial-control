# Controle financeiro

Painel de controle financeiro por BD: orçamento (PDD), realizado, forecast, pessoas, compras, cadastros, cargas e fechamento mensal. Este arquivo é o glossário: use estes termos em código, teste e texto.

## Language

### Organização e acesso

**BD**:
A unidade que isola os dados. Cada BD tem a sua organização, os seus cadastros e o seu fechamento, e é o tenant do app.
_Avoid_: tenant (no texto de produto), cliente, empresa

**Organização**:
A árvore BD → Tribo → Squad, com vigência e gestor em cada nível.
_Avoid_: estrutura, hierarquia

**Tribo**:
Agrupamento de squads dentro de um BD, com gestor.
_Avoid_: área, diretoria

**Squad**:
O menor nível da organização, ligado a uma tribo. É a unidade a que as pessoas e as demandas se vinculam.
_Avoid_: time, equipe

**Papel**:
O que um usuário pode fazer num BD: Admin, Editor ou Leitor. O mesmo usuário pode ter papéis diferentes em BDs diferentes.
_Avoid_: perfil, permissão

**Pedido de acesso**:
A solicitação de um usuário para entrar num BD, que um Admin aprova ou recusa.
_Avoid_: convite (convite parte do Admin)

**Convite**:
O chamado que um Admin faz a um e-mail para entrar num BD, com um papel.
_Avoid_: pedido de acesso

### Configuração do BD

**Onboarding**:
O roteiro guiado que leva um BD novo do vazio até estar pronto para uso, na ordem em que os cadastros dependem uns dos outros. Abre sozinho uma vez, para o primeiro Admin do BD, e depois sob demanda; Admin e Editor o veem.
_Avoid_: wizard, setup, tutorial, assistente

**Passo**:
Uma etapa do onboarding, ligada a um cadastro ou a uma carga. Está feito, pendente, bloqueado (falta uma etapa da qual depende) ou não se aplica (etapa opcional dispensada).
_Avoid_: tarefa, fase, item

### Pessoas e custo

**Empresa**:
Quem emprega a pessoa: a própria ou uma consultoria.
_Avoid_: fornecedor (fornecedor é de compra), terceiro

**Cargo**:
Uma função de uma empresa, com um nível. A tarifa é do par cargo + empresa.
_Avoid_: função

**Nível**:
O degrau do cargo, de E6 a N12.
_Avoid_: senioridade, faixa

**Tarifa**:
O valor líquido por hora de um cargo numa empresa, com vigência. É um valor exato, nunca faixa nem média.
_Avoid_: custo-hora, valor-hora, faixa

**Markup**:
O percentual que, aplicado à tarifa líquida, dá o valor bruto: bruto = líquido × (1 + markup). Tem vigência.
_Avoid_: margem, acréscimo

**Vigência**:
O período em que um valor de cadastro (organização, tarifa, markup, cargo) vale.
_Avoid_: validade, histórico

**Pessoa**:
Quem trabalha para o BD, com matrícula, organização, cargo e tema, admissão e desligamento.
_Avoid_: funcionário, recurso, colaborador

**Vaga**:
A posição aberta para uma pessoa, com organização, tema e cargo. Fica aberta, preenchida por uma pessoa ou cancelada.
_Avoid_: requisição, posição

### Portfólio e orçamento

**Iniciativa**:
O agrupamento mais alto do portfólio, que reúne demandas.
_Avoid_: projeto, programa

**Demanda**:
O trabalho de uma iniciativa, classificado como CAPEX ou OPEX.
_Avoid_: épico, item, tarefa

**Tema**:
O agrupamento fixo de uma demanda, onde as horas das pessoas são alocadas.
_Avoid_: tag

**Agrupamento**:
A classe que reúne temas para análise (por exemplo, Regulatório, RTB, Gravity, Recuperação).
_Avoid_: categoria

**PDD**:
O orçamento bruto por iniciativa e por tipo (CAPEX ou OPEX), que muda por revisão. Valor bruto.
_Avoid_: budget (no texto de produto), plano

**Revisão**:
Uma versão trimestral do PDD, com o markup congelado do momento. A original é a primeira.
_Avoid_: versão, ajuste

**Gap**:
A diferença entre o orçamento e o total do ano (realizado + forecast). Positivo é saldo, negativo é estouro.
_Avoid_: desvio, variação, delta

### Consumo

**Alocação**:
As horas de uma pessoa num tema, num mês.
_Avoid_: apontamento, lançamento de horas

**Compra**:
Uma OC (ordem de compra) ou OS (ordem de serviço) ligada a uma só demanda, com status prevista, emitida ou cancelada.
_Avoid_: pedido, contrato

**Fornecedor**:
Quem vende a compra ao BD.
_Avoid_: empresa (empresa é de pessoa)

**Calendário**:
Os dias úteis de cada mês, que dão as horas de capacidade (8 h por dia útil).
_Avoid_: agenda

### Realizado, forecast e fechamento

**Realizado**:
O consumo de um mês fechado. Só mês fechado é realizado.
_Avoid_: gasto, executado

**Forecast**:
A projeção de consumo: tudo que está em mês aberto, mesmo com lançamento nele, e os meses futuros.
_Avoid_: previsão, projeção

**Cenário**:
Um conjunto salvo de fatores sobre pessoas e compras, aplicado ao forecast.
_Avoid_: simulação, versão

**Fechamento**:
O ato manual, mensal e reversível de tornar um mês realizado. Exige o mês anterior fechado e deixa um log.
_Avoid_: encerramento, consolidação

**Mês fechado / mês aberto**:
Mês fechado passou pelo fechamento e é realizado. Mês aberto ainda não, e vale como forecast.
_Avoid_: mês corrente (pode estar aberto ou fechado)

### Cargas

**Carga**:
A entrada de um arquivo de um layout, validada antes de gravar, com relatório e desfazer.
_Avoid_: import, upload, importação

**Layout**:
O formato de colunas de um tipo de carga: Horas realizadas, Compras realizadas, Orçamento PDD, Pessoas, Tarifas ou Portfólio.
_Avoid_: modelo, template

**Rejeição**:
Linha de uma carga que não entrou, com a regra violada e a mensagem.
_Avoid_: erro, falha

**Nota de reconciliação**:
O aviso, numa tela, de que uma tabela não fecha com o total e de quanto ficou de fora, por exemplo por rejeição ou mês fora do fechamento.
_Avoid_: ressalva, observação
