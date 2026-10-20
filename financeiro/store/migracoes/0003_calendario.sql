-- Calendário: horas de capacidade por mês (8 h × dias úteis) e feriados do BD.

CREATE TABLE calendario_mes (
    bd_id    BIGINT NOT NULL REFERENCES bd (id),
    ano      BIGINT NOT NULL,
    mes      BIGINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    horas    BIGINT NOT NULL CHECK (horas >= 0),
    ajustado BIGINT NOT NULL DEFAULT 0 CHECK (ajustado IN (0, 1)),
    PRIMARY KEY (bd_id, ano, mes)
);

CREATE TABLE feriado_bd (
    bd_id BIGINT NOT NULL REFERENCES bd (id),
    data  TEXT NOT NULL,  -- AAAA-MM-DD
    nome  TEXT NOT NULL,
    PRIMARY KEY (bd_id, data)
);
