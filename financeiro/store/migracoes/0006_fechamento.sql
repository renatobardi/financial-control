-- Fechamento mensal: o mês fechado guarda o que congelou, e cada fechar e reabrir vai ao log.

ALTER TABLE mes_fechado ADD COLUMN horas INTEGER NOT NULL DEFAULT 0;
ALTER TABLE mes_fechado ADD COLUMN pessoas_centavos INTEGER NOT NULL DEFAULT 0;
ALTER TABLE mes_fechado ADD COLUMN compras_centavos INTEGER NOT NULL DEFAULT 0;

CREATE TABLE fechamento_log (
    id         INTEGER PRIMARY KEY,
    bd_id      INTEGER NOT NULL REFERENCES bd (id),
    mes        TEXT NOT NULL,
    acao       TEXT NOT NULL CHECK (acao IN ('fechou', 'reabriu')),
    usuario_id INTEGER NOT NULL REFERENCES usuario (id),
    em         TEXT NOT NULL,
    motivo     TEXT NOT NULL DEFAULT ''
);
