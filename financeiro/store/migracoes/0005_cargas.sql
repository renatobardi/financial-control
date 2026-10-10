-- Cargas: códigos para os layouts, mês fechado, o que as cargas gravam (alocação, compra,
-- PDD) e o diário que permite desfazer. As telas de PDD, Pessoas e Compras vêm nas fatias
-- seguintes; aqui entra só o que a carga precisa.

ALTER TABLE empresa ADD COLUMN codigo TEXT;
ALTER TABLE cargo ADD COLUMN codigo TEXT;
ALTER TABLE org ADD COLUMN codigo TEXT;
CREATE UNIQUE INDEX empresa_codigo ON empresa (bd_id, codigo) WHERE codigo IS NOT NULL;
CREATE UNIQUE INDEX cargo_codigo ON cargo (bd_id, codigo) WHERE codigo IS NOT NULL;
CREATE UNIQUE INDEX org_codigo ON org (bd_id, codigo) WHERE codigo IS NOT NULL;

-- Só mês fechado é realizado (ADR-0003). O fechamento (log, ordem, reabrir) vem na #6.
CREATE TABLE mes_fechado (
    bd_id      INTEGER NOT NULL REFERENCES bd (id),
    mes        TEXT NOT NULL,  -- AAAA-MM
    fechado_em TEXT NOT NULL,
    PRIMARY KEY (bd_id, mes)
);

CREATE TABLE carga (
    id           INTEGER PRIMARY KEY,
    bd_id        INTEGER NOT NULL REFERENCES bd (id),
    layout       TEXT NOT NULL,
    arquivo      TEXT NOT NULL,
    usuario_id   INTEGER NOT NULL REFERENCES usuario (id),
    em           TEXT NOT NULL,
    lidas        INTEGER NOT NULL DEFAULT 0,
    inseridas    INTEGER NOT NULL DEFAULT 0,
    atualizadas  INTEGER NOT NULL DEFAULT 0,
    iguais       INTEGER NOT NULL DEFAULT 0,
    rejeitadas   INTEGER NOT NULL DEFAULT 0,
    horas        INTEGER NOT NULL DEFAULT 0,
    valor_centavos INTEGER NOT NULL DEFAULT 0,
    estado       TEXT NOT NULL DEFAULT 'ativa' CHECK (estado IN ('ativa', 'desfeita')),
    desfeita_em  TEXT,
    UNIQUE (bd_id, id)
);

CREATE TABLE carga_rejeicao (
    id         INTEGER PRIMARY KEY,
    bd_id      INTEGER NOT NULL REFERENCES bd (id),
    carga_id   INTEGER NOT NULL,
    linha      INTEGER NOT NULL,
    regra      TEXT NOT NULL,
    mensagem   TEXT NOT NULL,
    dados_json TEXT NOT NULL,
    aprovavel  INTEGER NOT NULL DEFAULT 0 CHECK (aprovavel IN (0, 1)),
    grupo      TEXT,
    aprovada   INTEGER NOT NULL DEFAULT 0 CHECK (aprovada IN (0, 1)),
    FOREIGN KEY (bd_id, carga_id) REFERENCES carga (bd_id, id)
);

CREATE TABLE carga_mudanca (
    id          INTEGER PRIMARY KEY,
    bd_id       INTEGER NOT NULL REFERENCES bd (id),
    carga_id    INTEGER NOT NULL,
    tabela      TEXT NOT NULL,
    registro_id INTEGER NOT NULL,
    antes_json  TEXT,  -- NULL: o registro foi inserido pela carga
    FOREIGN KEY (bd_id, carga_id) REFERENCES carga (bd_id, id)
);

CREATE TABLE alocacao (
    id        INTEGER PRIMARY KEY,
    bd_id     INTEGER NOT NULL REFERENCES bd (id),
    pessoa_id INTEGER NOT NULL,
    tema_id   INTEGER NOT NULL,
    mes       TEXT NOT NULL,
    horas     INTEGER NOT NULL CHECK (horas >= 0),
    extra     INTEGER NOT NULL DEFAULT 0 CHECK (extra IN (0, 1)),  -- hora extra aprovada
    UNIQUE (bd_id, pessoa_id, tema_id, mes),
    FOREIGN KEY (bd_id, pessoa_id) REFERENCES pessoa (bd_id, id),
    FOREIGN KEY (bd_id, tema_id) REFERENCES tema (bd_id, id)
);

CREATE TABLE compra (
    id            INTEGER PRIMARY KEY,
    bd_id         INTEGER NOT NULL REFERENCES bd (id),
    numero        TEXT NOT NULL,
    tipo          TEXT NOT NULL CHECK (tipo IN ('OC', 'OS')),
    fornecedor_id INTEGER,
    demanda_id    INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'prevista'
                  CHECK (status IN ('prevista', 'emitida', 'cancelada')),
    descricao     TEXT NOT NULL DEFAULT '',
    UNIQUE (bd_id, numero),
    UNIQUE (bd_id, id),
    FOREIGN KEY (bd_id, fornecedor_id) REFERENCES fornecedor (bd_id, id),
    FOREIGN KEY (bd_id, demanda_id) REFERENCES demanda (bd_id, id)
);

CREATE TABLE compra_mes (
    id                     INTEGER PRIMARY KEY,
    bd_id                  INTEGER NOT NULL REFERENCES bd (id),
    compra_id              INTEGER NOT NULL,
    mes                    TEXT NOT NULL,
    valor_liquido_centavos INTEGER NOT NULL CHECK (valor_liquido_centavos >= 0),
    UNIQUE (bd_id, compra_id, mes),
    FOREIGN KEY (bd_id, compra_id) REFERENCES compra (bd_id, id)
);

CREATE TABLE pdd_revisao (
    id                   INTEGER PRIMARY KEY,
    bd_id                INTEGER NOT NULL REFERENCES bd (id),
    rotulo               TEXT NOT NULL,
    estado               TEXT NOT NULL DEFAULT 'rascunho' CHECK (estado IN ('rascunho', 'aprovada')),
    markup_centesimos_pct INTEGER,  -- congelado na aprovação (#7)
    criada_em            TEXT NOT NULL,
    UNIQUE (bd_id, rotulo),
    UNIQUE (bd_id, id)
);

CREATE TABLE pdd_linha (
    id                   INTEGER PRIMARY KEY,
    bd_id                INTEGER NOT NULL REFERENCES bd (id),
    revisao_id           INTEGER NOT NULL,
    iniciativa_id        INTEGER NOT NULL,
    tipo                 TEXT NOT NULL CHECK (tipo IN ('CAPEX', 'OPEX')),
    valor_bruto_centavos INTEGER NOT NULL CHECK (valor_bruto_centavos >= 0),
    UNIQUE (bd_id, revisao_id, iniciativa_id, tipo),
    FOREIGN KEY (bd_id, revisao_id) REFERENCES pdd_revisao (bd_id, id),
    FOREIGN KEY (bd_id, iniciativa_id) REFERENCES iniciativa (bd_id, id)
);
