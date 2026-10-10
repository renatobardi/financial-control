-- Cadastros base: organização, empresas, cargos, tarifas e markup.
-- Vigência é mensal ("AAAA-MM"), início e fim inclusivos, fim NULL = vigente.
-- Dinheiro em centavos inteiros; markup em centésimos de ponto percentual (10,5% = 1050).

ALTER TABLE bd ADD COLUMN gestor TEXT NOT NULL DEFAULT '';

CREATE TABLE org (
    id           INTEGER PRIMARY KEY,
    bd_id        INTEGER NOT NULL REFERENCES bd (id),
    tipo         TEXT NOT NULL CHECK (tipo IN ('Tribo', 'Squad')),
    nome         TEXT NOT NULL,
    pai_id       INTEGER,  -- Squad: a Tribo; Tribo: NULL (o pai é o BD)
    gestor       TEXT NOT NULL DEFAULT '',
    vigencia_ini TEXT NOT NULL,
    vigencia_fim TEXT,
    UNIQUE (bd_id, nome),
    UNIQUE (bd_id, id),
    FOREIGN KEY (bd_id, pai_id) REFERENCES org (bd_id, id)
);

CREATE TABLE org_historico (
    id     INTEGER PRIMARY KEY,
    bd_id  INTEGER NOT NULL REFERENCES bd (id),
    org_id INTEGER NOT NULL,
    em     TEXT NOT NULL,  -- mês AAAA-MM
    texto  TEXT NOT NULL,
    FOREIGN KEY (bd_id, org_id) REFERENCES org (bd_id, id)
);

CREATE TABLE empresa (
    id    INTEGER PRIMARY KEY,
    bd_id INTEGER NOT NULL REFERENCES bd (id),
    nome  TEXT NOT NULL,
    tipo  TEXT NOT NULL CHECK (tipo IN ('propria', 'consultoria')),
    UNIQUE (bd_id, nome),
    UNIQUE (bd_id, id)
);

CREATE TABLE cargo (
    id         INTEGER PRIMARY KEY,
    bd_id      INTEGER NOT NULL REFERENCES bd (id),
    empresa_id INTEGER NOT NULL,
    nome       TEXT NOT NULL,
    nivel      TEXT NOT NULL CHECK (nivel IN ('E6', 'N7', 'N8', 'N9', 'N10', 'N11', 'N12')),
    UNIQUE (bd_id, empresa_id, nome),
    UNIQUE (bd_id, id),
    FOREIGN KEY (bd_id, empresa_id) REFERENCES empresa (bd_id, id)
);

CREATE TABLE tarifa (
    id               INTEGER PRIMARY KEY,
    bd_id            INTEGER NOT NULL REFERENCES bd (id),
    cargo_id         INTEGER NOT NULL,
    liquida_centavos INTEGER NOT NULL CHECK (liquida_centavos >= 0),
    vigencia_ini     TEXT NOT NULL,
    vigencia_fim     TEXT,
    FOREIGN KEY (bd_id, cargo_id) REFERENCES cargo (bd_id, id)
);

CREATE TABLE markup (
    id             INTEGER PRIMARY KEY,
    bd_id          INTEGER NOT NULL REFERENCES bd (id),
    centesimos_pct INTEGER NOT NULL CHECK (centesimos_pct >= 0),
    vigencia_ini   TEXT NOT NULL,
    vigencia_fim   TEXT
);

-- O banco recusa vigências sobrepostas para a mesma chave, mesmo por fora do store.
CREATE TRIGGER tarifa_sem_sobreposicao BEFORE INSERT ON tarifa
BEGIN
    SELECT RAISE(ABORT, 'vigencia sobreposta')
    WHERE EXISTS (
        SELECT 1 FROM tarifa
        WHERE bd_id = NEW.bd_id AND cargo_id = NEW.cargo_id
          AND NEW.vigencia_ini <= COALESCE(vigencia_fim, '9999-12')
          AND vigencia_ini <= COALESCE(NEW.vigencia_fim, '9999-12')
    );
END;

CREATE TRIGGER markup_sem_sobreposicao BEFORE INSERT ON markup
BEGIN
    SELECT RAISE(ABORT, 'vigencia sobreposta')
    WHERE EXISTS (
        SELECT 1 FROM markup
        WHERE bd_id = NEW.bd_id
          AND NEW.vigencia_ini <= COALESCE(vigencia_fim, '9999-12')
          AND vigencia_ini <= COALESCE(NEW.vigencia_fim, '9999-12')
    );
END;
