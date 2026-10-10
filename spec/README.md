# Especificação — App de Controle Financeiro (versão sanitizada)

Este pacote descreve um painel de controle financeiro de diretoria **sem nenhum dado real**: nomes, valores, OCs, fornecedores, consultorias e pessoas são fictícios ou descritos apenas por estrutura. Pode ser usado para reconstruir um app equivalente fora do ambiente corporativo.

## Conteúdo

- `contrato-json-schema.json` — JSON Schema do payload que o app consome (o "contrato de dados")
- `modelo-de-dados.md` — descrição das entidades e invariantes
- `mock-exemplo.json` — payload de exemplo 100% fictício que passa no schema
- `regras-de-negocio.md` — regras de apresentação/cálculo sanitizadas
- `telas-e-ux.md` — especificação funcional das seções da tela
- `arquitetura.md` — arquitetura recomendada (genérica, sem tecnologia proprietária)

## O que foi removido/intencionalmente genérico

- Nenhum valor monetário, percentual ou contagem real
- Nenhum nome de empresa, fornecedor, consultoria, pessoa, matrícula ou unidade organizacional real
- Nenhum identificador de ordem de compra, hash ou descrição de contrato real
- Nenhuma referência a sistemas, pipelines ou infraestrutura interna por nome próprio
- Nenhum código-fonte copiado — apenas estruturas e contratos descritos

## Como usar

1. Implemente um gerador/leitor que produza ou consuma `mock-exemplo.json` conforme `contrato-json-schema.json`.
2. Construa as seções da tela conforme `telas-e-ux.md`.
3. Respeite os invariantes em `modelo-de-dados.md` e `regras-de-negocio.md`.
