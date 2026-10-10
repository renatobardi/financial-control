-- Acesso: BDs (tenants), usuários, papéis por BD, sessões e tentativas de login.
-- `bd` e `usuario` não são tabelas de dado (ADR-0002): não têm bd_id.

CREATE TABLE bd (
    id    INTEGER PRIMARY KEY,
    nome  TEXT NOT NULL UNIQUE,
    sigla TEXT NOT NULL
);

CREATE TABLE usuario (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nome          TEXT NOT NULL,
    senha_hash    TEXT,  -- NULL: convite pendente, a conta ainda não foi criada
    tema          TEXT NOT NULL DEFAULT 'sistema' CHECK (tema IN ('claro', 'escuro', 'sistema')),
    formato_valor TEXT NOT NULL DEFAULT 'mil' CHECK (formato_valor IN ('mi', 'mil')),
    tela_inicial  TEXT NOT NULL DEFAULT 'Visão geral',
    bd_padrao_id  INTEGER REFERENCES bd (id)
);

CREATE TABLE membro (
    bd_id      INTEGER NOT NULL REFERENCES bd (id),
    usuario_id INTEGER NOT NULL REFERENCES usuario (id),
    papel      TEXT NOT NULL CHECK (papel IN ('Admin', 'Editor', 'Leitor')),
    PRIMARY KEY (bd_id, usuario_id)
);

CREATE TABLE pedido_acesso (
    id         INTEGER PRIMARY KEY,
    bd_id      INTEGER NOT NULL REFERENCES bd (id),
    usuario_id INTEGER NOT NULL REFERENCES usuario (id),
    motivo     TEXT NOT NULL,
    estado     TEXT NOT NULL DEFAULT 'aberto' CHECK (estado IN ('aberto', 'aprovado', 'recusado')),
    criado_em  TEXT NOT NULL
);

CREATE TABLE sessao (
    token_hash TEXT PRIMARY KEY,  -- SHA-256 do token do cookie; o token não é guardado
    usuario_id INTEGER NOT NULL REFERENCES usuario (id),
    bd_id      INTEGER REFERENCES bd (id),
    csrf       TEXT NOT NULL,
    criada_em  TEXT NOT NULL,
    expira_em  TEXT NOT NULL
);

CREATE TABLE tentativa_login (
    id    INTEGER PRIMARY KEY,
    email TEXT NOT NULL COLLATE NOCASE,
    em    TEXT NOT NULL
);
CREATE INDEX tentativa_login_email_em ON tentativa_login (email, em);
