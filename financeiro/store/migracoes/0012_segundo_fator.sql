-- Verificação em duas etapas (TOTP): o segredo do usuário e os códigos de recuperação.
-- Do usuário, não de um BD (ADR-0002): sem bd_id.
CREATE TABLE segundo_fator (
    usuario_id   INTEGER PRIMARY KEY REFERENCES usuario (id),
    segredo      TEXT NOT NULL,
    ativo        INTEGER NOT NULL DEFAULT 0 CHECK (ativo IN (0, 1)),
    ultimo_passo INTEGER NOT NULL DEFAULT 0  -- passo TOTP já usado: o mesmo código não vale duas vezes
);

CREATE TABLE codigo_recuperacao (
    usuario_id  INTEGER NOT NULL REFERENCES usuario (id),
    codigo_hash TEXT NOT NULL,  -- SHA-256 do código; o código em si não é guardado
    PRIMARY KEY (usuario_id, codigo_hash)
);
