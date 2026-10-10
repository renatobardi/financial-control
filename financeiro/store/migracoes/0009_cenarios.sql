-- Cenários de forecast: fatores sobre pessoas e compras e a composição do treemap.
-- Fatores em centésimos de ponto percentual (100,00% = 10000). Até 20 por BD (regra no serviço).

CREATE TABLE cenario (
    id                    INTEGER PRIMARY KEY,
    bd_id                 INTEGER NOT NULL REFERENCES bd (id),
    nome                  TEXT NOT NULL,
    fator_pessoas         INTEGER NOT NULL DEFAULT 10000 CHECK (fator_pessoas >= 0),
    fator_compras         INTEGER NOT NULL DEFAULT 10000 CHECK (fator_compras >= 0),
    trimestres            INTEGER NOT NULL DEFAULT 15 CHECK (trimestres BETWEEN 1 AND 15),
    escala_tipo           TEXT NOT NULL DEFAULT 'PDD'
                          CHECK (escala_tipo IN ('PDD', 'Agrupamento', 'Tribo', 'Squad')),
    escala_ref            INTEGER,
    escala_valor_centavos INTEGER,
    elemento_tipo         TEXT NOT NULL DEFAULT 'Agrupamento'
                          CHECK (elemento_tipo IN ('Agrupamento', 'Squad', 'Tribo')),
    incluidos             TEXT NOT NULL DEFAULT '[]',
    UNIQUE (bd_id, nome),
    UNIQUE (bd_id, id)
);

-- A vaga passa a poder ser referenciada por (bd_id, id).
CREATE UNIQUE INDEX vaga_bd_id_id ON vaga (bd_id, id);

-- Mês em que cada vaga aberta começa a custar, por cenário.
CREATE TABLE vaga_inicio (
    bd_id       INTEGER NOT NULL REFERENCES bd (id),
    cenario_id  INTEGER NOT NULL,
    vaga_id     INTEGER NOT NULL,
    mes         TEXT NOT NULL,
    PRIMARY KEY (bd_id, cenario_id, vaga_id),
    FOREIGN KEY (bd_id, cenario_id) REFERENCES cenario (bd_id, id),
    FOREIGN KEY (bd_id, vaga_id) REFERENCES vaga (bd_id, id)
);
