-- Calendário: horas de capacidade por mês (8 h × dias úteis) e feriados do BD.

CREATE TABLE calendario_mes (
    bd_id    INTEGER NOT NULL REFERENCES bd (id),
    ano      INTEGER NOT NULL,
    mes      INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    horas    INTEGER NOT NULL CHECK (horas >= 0),
    ajustado INTEGER NOT NULL DEFAULT 0 CHECK (ajustado IN (0, 1)),
    PRIMARY KEY (bd_id, ano, mes)
);

CREATE TABLE feriado_bd (
    bd_id INTEGER NOT NULL REFERENCES bd (id),
    data  TEXT NOT NULL,  -- AAAA-MM-DD
    nome  TEXT NOT NULL,
    PRIMARY KEY (bd_id, data)
);
