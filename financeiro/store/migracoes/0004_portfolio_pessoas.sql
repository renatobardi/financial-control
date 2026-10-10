-- Portfólio (iniciativa → demanda → tema), agrupamentos, fornecedores, pessoas e vagas.

CREATE TABLE agrupamento (
    id    INTEGER PRIMARY KEY,
    bd_id INTEGER NOT NULL REFERENCES bd (id),
    nome  TEXT NOT NULL,
    UNIQUE (bd_id, nome),
    UNIQUE (bd_id, id)
);

CREATE TABLE fornecedor (
    id    INTEGER PRIMARY KEY,
    bd_id INTEGER NOT NULL REFERENCES bd (id),
    nome  TEXT NOT NULL,
    UNIQUE (bd_id, nome),
    UNIQUE (bd_id, id)
);

CREATE TABLE iniciativa (
    id     INTEGER PRIMARY KEY,
    bd_id  INTEGER NOT NULL REFERENCES bd (id),
    codigo TEXT NOT NULL,
    nome   TEXT NOT NULL,
    UNIQUE (bd_id, codigo),
    UNIQUE (bd_id, id)
);

CREATE TABLE demanda (
    id            INTEGER PRIMARY KEY,
    bd_id         INTEGER NOT NULL REFERENCES bd (id),
    codigo        TEXT NOT NULL,
    iniciativa_id INTEGER NOT NULL,
    nome          TEXT NOT NULL,
    tipo          TEXT NOT NULL CHECK (tipo IN ('CAPEX', 'OPEX')),
    squad_id      INTEGER,
    UNIQUE (bd_id, codigo),
    UNIQUE (bd_id, id),
    FOREIGN KEY (bd_id, iniciativa_id) REFERENCES iniciativa (bd_id, id),
    FOREIGN KEY (bd_id, squad_id) REFERENCES org (bd_id, id)
);

CREATE TABLE tema (
    id             INTEGER PRIMARY KEY,
    bd_id          INTEGER NOT NULL REFERENCES bd (id),
    codigo         TEXT NOT NULL,
    demanda_id     INTEGER NOT NULL,
    nome           TEXT NOT NULL,
    agrupamento_id INTEGER NOT NULL,
    UNIQUE (bd_id, codigo),
    UNIQUE (bd_id, id),
    FOREIGN KEY (bd_id, demanda_id) REFERENCES demanda (bd_id, id),
    FOREIGN KEY (bd_id, agrupamento_id) REFERENCES agrupamento (bd_id, id)
);

CREATE TABLE pessoa (
    id           INTEGER PRIMARY KEY,
    bd_id        INTEGER NOT NULL REFERENCES bd (id),
    matricula    TEXT NOT NULL,
    nome         TEXT NOT NULL,
    org_id       INTEGER NOT NULL,
    cargo_id     INTEGER NOT NULL,
    tema_id      INTEGER NOT NULL,
    admissao     TEXT NOT NULL,  -- AAAA-MM
    desligamento TEXT,           -- AAAA-MM
    UNIQUE (bd_id, matricula),
    UNIQUE (bd_id, id),
    CHECK (desligamento IS NULL OR desligamento >= admissao),
    FOREIGN KEY (bd_id, org_id) REFERENCES org (bd_id, id),
    FOREIGN KEY (bd_id, cargo_id) REFERENCES cargo (bd_id, id),
    FOREIGN KEY (bd_id, tema_id) REFERENCES tema (bd_id, id)
);

CREATE TABLE vaga (
    id        INTEGER PRIMARY KEY,
    bd_id     INTEGER NOT NULL REFERENCES bd (id),
    codigo    TEXT NOT NULL,
    org_id    INTEGER NOT NULL,
    tema_id   INTEGER NOT NULL,
    cargo_id  INTEGER NOT NULL,
    aberta_em TEXT NOT NULL,  -- AAAA-MM
    estado    TEXT NOT NULL DEFAULT 'aberta' CHECK (estado IN ('aberta', 'preenchida', 'cancelada')),
    pessoa_id INTEGER,
    UNIQUE (bd_id, codigo),
    CHECK ((estado = 'preenchida') = (pessoa_id IS NOT NULL)),
    FOREIGN KEY (bd_id, org_id) REFERENCES org (bd_id, id),
    FOREIGN KEY (bd_id, tema_id) REFERENCES tema (bd_id, id),
    FOREIGN KEY (bd_id, cargo_id) REFERENCES cargo (bd_id, id),
    FOREIGN KEY (bd_id, pessoa_id) REFERENCES pessoa (bd_id, id)
);
