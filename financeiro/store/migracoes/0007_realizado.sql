-- Realizado congelado por linha: ao fechar o mês, cada lançamento (horas de uma pessoa num
-- tema, valor de uma compra) guarda o valor e a classificação daquele momento (ADR-0003).
-- Reorganizar ou mudar tarifa depois não altera o mês fechado.

CREATE TABLE realizado_linha (
    id                INTEGER PRIMARY KEY,
    bd_id             INTEGER NOT NULL REFERENCES bd (id),
    mes               TEXT NOT NULL,
    origem            TEXT NOT NULL CHECK (origem IN ('pessoas', 'compras')),
    pessoa_id         INTEGER,
    compra_id         INTEGER,
    tema_id           INTEGER,
    demanda_id        INTEGER NOT NULL,
    iniciativa_id     INTEGER NOT NULL,
    tipo              TEXT NOT NULL CHECK (tipo IN ('CAPEX', 'OPEX')),
    agrupamento_id    INTEGER,
    org_id            INTEGER,
    empresa_id        INTEGER,
    cargo_id          INTEGER,
    horas             INTEGER NOT NULL DEFAULT 0,
    liquido_centavos  INTEGER NOT NULL,
    bruto_centavos    INTEGER NOT NULL,
    FOREIGN KEY (bd_id, mes) REFERENCES mes_fechado (bd_id, mes)
);
CREATE INDEX realizado_linha_mes ON realizado_linha (bd_id, mes);

ALTER TABLE pdd_revisao ADD COLUMN aprovada_em TEXT;
