# Arquitetura recomendada — app pessoal (sanitizado)

## Opção simples (recomendada)

- **Frontend**: SPA (Angular/React/Vue) lendo um JSON local em `assets/data/painel.json` — mesma estrutura do schema.
- **Gerador de dados**: script Python/Node que produz o JSON a partir de planilhas CSV/XLSX que você controla.
- **Sem backend** no MVP: troque depois para `GET /api/v1/financeiro/{unidade}` quando quiser persistência.

## Estrutura de pastas sugerida

```
app/
  src/
    models/painel.model.ts      # interfaces do contrato (gerar do JSON Schema)
    services/painel.service.ts  # carrega JSON, valida versaoContrato/escopo
    components/
      secao/                    # seção colapsável reutilizável
      card-kpi/                 # card de valor monetário
      barra-progresso/
      tabela-expansivel/
    pages/painel/
  assets/data/painel.json       # payload gerado
  assets/i18n/{pt-BR,en-US,es}.json
gerador/
  ler_fontes.py                 # lê CSV/XLSX de entrada
  montar_payload.py             # aplica regras e invariantes
  validar.py                    # valida contra contrato-json-schema.json
fontes/
  realizado.csv, censo.csv, capacity.csv, vagas.csv, temas.csv, ordens_compra.csv
```

## Serviço de dados (comportamento)

- `carregar()`: GET do JSON → valida `meta.versaoContrato` e `meta.escopoEvolucao` → publica via signal/store → erro 'naoCarregou' ou 'contratoIncompativel'
- `recarregar()`: limpa cache e recarrega
- Manter a fonte em constante única para trocar arquivo→API sem mexer na tela

## Gerador de dados (responsabilidades)

- Ler fontes tabulares; aplicar regra de fechamento (quais meses contam como realizado)
- Calcular derivados: totalAno, gap, pct, misto, totais por mês, descartadas
- Garantir invariantes do modelo-de-dados.md
- Emitir `meta` completo (geradoEm, mesesRealizado/Forecast, versaoContrato=3)
- Validar saída contra o JSON Schema antes de publicar

## Privacidade no app pessoal

- Use dados fictícios (ver mock-exemplo.json)
- Se um dia usar dados reais fora do ambiente autorizado, **não** inclua campos de `horasAcimaPrevisto` com identificadores — anonimize
